# filename: kimi_coding_agent_v5.py
import argparse
import json
import logging
import os
import sys
import subprocess
import compileall
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

# Disable OpenAI tracing and other external services
os.environ["OPENAI_AGENTS_TRACING"] = "false"
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

# ---- OpenAI Agents SDK (configured for Kimi / Moonshot) ------------------
try:
    from agents import (
        Agent,
        Runner,
        function_tool,
        enable_verbose_stdout_logging,
        set_default_openai_client,
        set_default_openai_api,
        ModelSettings,
        CodeInterpreterTool,  # NEW: sandboxed code execution
    )
    from agents.run_context import RunContextWrapper
    from openai import AsyncOpenAI
except Exception as e:
    raise RuntimeError(
        "The OpenAI Agents SDK and openai client are required. "
        "Install with: pip install openai-agents openai"
    ) from e


# ----------------------------------------------------------------------------
# Context object passed to every tool
# ----------------------------------------------------------------------------
@dataclass
class AgentContext:
    base_dir: Path
    requirements_path: Optional[Path] = None
    dry_run: bool = False  # if True, tools won't write, just log


# ----------------------------------------------------------------------------
# Utility: filesystem helpers
# ----------------------------------------------------------------------------
def _resolve_safe(base: Path, target: str | Path) -> Path:
    base = base.resolve()
    p = (base / target).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError(f"Refusing to write outside base_dir: {p}")
    return p


def _ensure_artifacts_dir(base: Path) -> Path:
    ad = (base / "artifacts").resolve()
    ad.mkdir(parents=True, exist_ok=True)
    return ad


# ----------------------------------------------------------------------------
# Pydantic Models with OpenAI-compatible schemas
# ----------------------------------------------------------------------------
class FileItem(BaseModel):
    """Represents a single file with path and content"""
    path: str = Field(..., description="Relative file path")
    content: str = Field(..., description="File content")


class FileMap(BaseModel):
    """Mapping of relative_path -> text_content in OpenAI-compatible format"""
    files: List[FileItem] = Field(..., description="List of files to create")

    model_config = ConfigDict(extra='forbid')  # Explicitly forbid extra properties


class WebSearchResult(BaseModel):
    """Single search hit returned to the agent."""

    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(..., description="Short description or snippet")


class WebSearchResponse(BaseModel):
    """Structured response from the web_search tool."""

    ok: bool = Field(True, description="Whether the lookup succeeded")
    query: str = Field(..., description="Query that was executed")
    results: List[WebSearchResult] = Field(default_factory=list, description="List of search hits")
    error: Optional[str] = Field(default=None, description="Error message if the lookup failed")


class ValidationResult(BaseModel):
    """Structured validation result persisted to artifacts/validation.json"""
    sandbox_ok: bool
    sandbox_stdout: str = ""
    sandbox_stderr: str = ""
    compiled_ok: bool
    compile_errors: List[str] = []
    pytest_ok: bool
    pytest_stdout: str = ""
    pytest_stderr: str = ""

def build_file_map(files: dict[str, str]) -> FileMap:
    """Convert plain dict into the FileMap schema the SDK requires."""
    return FileMap(files=[FileItem(path=k, content=v) for k, v in files.items()])


def _coerce_text_content(content: Any) -> str:
    """Normalize diverse content payloads into a UTF-8 string."""

    if isinstance(content, str):
        return content
    if isinstance(content, bytes):
        return content.decode("utf-8")
    if isinstance(content, Iterable) and not isinstance(content, (dict, set)):
        try:
            return "\n".join(str(item) for item in content)
        except Exception as exc:  # pragma: no cover - fallback path
            raise ValueError(f"Unable to join iterable content: {exc}") from exc
    try:
        # As a last resort, serialize to JSON for deterministic output
        return json.dumps(content, ensure_ascii=False, indent=2)
    except TypeError as exc:
        raise ValueError(f"Unsupported content type: {type(content)!r}") from exc


def _normalize_file_map_input(files_input: Any) -> FileMap:
    """Accept several payload styles and convert them into FileMap."""

    if isinstance(files_input, FileMap):
        return files_input

    if isinstance(files_input, str):
        try:
            parsed = json.loads(files_input)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"files argument is not valid JSON: {exc}") from exc
        return _normalize_file_map_input(parsed)

    if isinstance(files_input, dict):
        # Allow either {"files": [...]} shape or {"path": "content"} mapping
        if "files" in files_input and isinstance(files_input["files"], list):
            items = [FileItem.model_validate(item) for item in files_input["files"]]
            return FileMap(files=items)
        if all(isinstance(k, str) for k in files_input.keys()):
            if all(isinstance(v, (str, bytes)) for v in files_input.values()):
                return build_file_map({k: _coerce_text_content(v) for k, v in files_input.items()})
        raise ValueError(
            "Unsupported dict format for files. Provide {path: content} or {'files': [...]}"
        )

    if isinstance(files_input, Iterable):
        try:
            items = [FileItem.model_validate(item) for item in files_input]
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid list format for files: {exc}") from exc
        return FileMap(files=items)

    raise ValueError(f"Unsupported files payload type: {type(files_input)!r}")

# ----------------------------------------------------------------------------
# Core Implementation Functions (testable without decorators)
# ----------------------------------------------------------------------------
def create_directory_impl(base_dir: Path, rel_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for creating directories."""
    path = _resolve_safe(base_dir, rel_path)
    if dry_run:
        logging.info(f"[dry-run] Would create: {path}")
        return {"ok": True, "path": str(path), "dry_run": True}
    path.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(path), "created": True}


def write_text_file_impl(base_dir: Path, rel_path: str, content: str, overwrite: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for writing text files."""
    path = _resolve_safe(base_dir, rel_path)
    if path.exists() and not overwrite:
        return {"ok": False, "error": "File exists and overwrite=False", "path": str(path)}
    if dry_run:
        logging.info(f"[dry-run] Would write {len(content)} bytes to: {path}")
        return {"ok": True, "path": str(path), "bytes": len(content), "dry_run": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": len(content)}


def read_requirements_impl(requirements_path: Optional[Path]) -> Dict[str, Any]:
    """Core implementation for reading requirements."""
    if not requirements_path:
        return {"ok": False, "error": "No requirements path provided"}
    if not requirements_path.exists():
        return {"ok": False, "error": f"Requirements file not found: {requirements_path}"}
    try:
        data = json.loads(requirements_path.read_text(encoding="utf-8"))
        return {"ok": True, "requirements": data, "path": str(requirements_path)}
    except Exception as e:
        return {"ok": False, "error": f"Failed to parse JSON: {e}", "path": str(requirements_path)}


def write_many_impl(base_dir: Path, files: FileMap, overwrite: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for writing multiple files."""
    results = {}
    for file_item in files.files:
        try:
            # Use the write_text_file_impl for consistent behavior
            res = write_text_file_impl(base_dir, file_item.path, file_item.content, overwrite, dry_run)
            results[file_item.path] = res
        except Exception as e:
            results[file_item.path] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results}


def py_compile_all_impl(base_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for compiling Python files."""
    if dry_run:
        return {"ok": True, "compiled": True, "dry_run": True}

    # compileall returns bool but we also surface per-file failures
    compiled_ok = compileall.compile_dir(str(base_dir), quiet=1, force=False, maxlevels=10)
    # simple pass/fail; detailed errors can be gleaned from stderr if run via py_compile
    return {"ok": True, "compiled": bool(compiled_ok)}


def run_pytest_impl(base_dir: Path, args: List[str] | None = None, timeout_sec: int = 180, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for running pytest."""
    if dry_run:
        return {"ok": True, "pytest": "dry-run", "stdout": "", "stderr": ""}

    cmd = [sys.executable, "-m", "pytest", "-q"]
    if args:
        cmd.extend(args)

    code, out, err = _run_subprocess(cmd, cwd=base_dir, timeout=timeout_sec)
    return {
        "ok": code == 0,
        "returncode": code,
        "stdout": out,
        "stderr": err,
    }


def record_validation_impl(base_dir: Path, validation: ValidationResult, dry_run: bool = False) -> Dict[str, Any]:
    """Core implementation for recording validation results."""
    if dry_run:
        return {"ok": True, "dry_run": True}

    artifacts_dir = _ensure_artifacts_dir(base_dir)
    path = artifacts_dir / "validation.json"
    path.write_text(validation.model_dump_json(indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path)}


# ----------------------------------------------------------------------------
# Function tools (wrappers around core implementations)
# ----------------------------------------------------------------------------
@function_tool(description_override="Create a directory relative to base_dir if it does not exist.")
def create_directory(ctx: RunContextWrapper[AgentContext], rel_path: str) -> Dict[str, Any]:
    return create_directory_impl(ctx.context.base_dir, rel_path, ctx.context.dry_run)


@function_tool(description_override="Write text to a file (UTF-8). Creates parent folders if needed.")
def write_text_file(
    ctx: RunContextWrapper[AgentContext],
    rel_path: str,
    content: Any,
    overwrite: bool = True,
) -> Dict[str, Any]:
    normalized = _coerce_text_content(content)
    return write_text_file_impl(ctx.context.base_dir, rel_path, normalized, overwrite, ctx.context.dry_run)


@function_tool(description_override="Read and return a JSON object from requirements_path or a provided path.")
def read_requirements(ctx: RunContextWrapper[AgentContext], rel_path: Optional[str] = None) -> Dict[str, Any]:
    req_path = Path(rel_path) if rel_path else ctx.context.requirements_path
    return read_requirements_impl(req_path)


@function_tool(description_override="Create multiple files at once using structured input.")
def write_many(
    ctx: RunContextWrapper[AgentContext],
    files: Any,
    overwrite: bool = True,
) -> Dict[str, Any]:
    file_map = _normalize_file_map_input(files)
    return write_many_impl(ctx.context.base_dir, file_map, overwrite, ctx.context.dry_run)


@function_tool(description_override="Compile all Python files under base_dir to check syntax. Returns a report.")
def py_compile_all(ctx: RunContextWrapper[AgentContext]) -> Dict[str, Any]:
    return py_compile_all_impl(ctx.context.base_dir, ctx.context.dry_run)


@function_tool(description_override="Run pytest -q inside base_dir (if available) with a safety timeout. Returns stdout/stderr.")
def run_pytest(
    ctx: RunContextWrapper[AgentContext],
    args: List[str] | None = None,
    timeout_sec: int = 180,
) -> Dict[str, Any]:
    return run_pytest_impl(ctx.context.base_dir, args, timeout_sec, ctx.context.dry_run)


@function_tool(description_override="Persist a JSON validation summary to artifacts/validation.json for auditing.")
def record_validation(ctx: RunContextWrapper[AgentContext], validation: ValidationResult) -> Dict[str, Any]:
    return record_validation_impl(ctx.context.base_dir, validation, ctx.context.dry_run)


@function_tool(description_override="Lookup current best practices or SDK documentation snippets via the public web.")
def web_search(
    ctx: RunContextWrapper[AgentContext],
    query: str,
    max_results: int = 5,
    region: str = "us-en",
) -> Dict[str, Any]:
    # The context is unused for now but kept for parity with other tools
    _ = ctx
    return web_search_impl(query=query, max_results=max_results, region=region)


# ----------------------------------------------------------------------------
# Subprocess helper (used by run_pytest_impl)
# ----------------------------------------------------------------------------
def _run_subprocess(
    cmd: List[str],
    cwd: Path,
    timeout: int,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Run a subprocess and capture output."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **(env or {})},
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return 124, out, f"Timed out after {timeout}s\n{err}"
    return proc.returncode, out, err


# ----------------------------------------------------------------------------
# Web search helper
# ----------------------------------------------------------------------------
def _extract_ddg_results(payload: Dict[str, Any]) -> List[WebSearchResult]:
    """Flatten DuckDuckGo instant answer payload into WebSearchResult list."""

    results: List[WebSearchResult] = []

    def _add(title: str, url: str, snippet: str) -> None:
        snippet_clean = " ".join(snippet.split())
        results.append(
            WebSearchResult(
                title=title.strip() or url,
                url=url,
                snippet=textwrap.shorten(snippet_clean, width=220, placeholder="…"),
            )
        )

    abstract = payload.get("AbstractText") or payload.get("Abstract")
    abstract_url = payload.get("AbstractURL")
    abstract_source = payload.get("Heading")
    if abstract and abstract_url:
        title = abstract_source or abstract_url
        _add(title, abstract_url, abstract)

    related_topics = payload.get("RelatedTopics", [])
    for topic in related_topics:
        if isinstance(topic, dict):
            if "FirstURL" in topic and "Text" in topic:
                _add(topic.get("Text", ""), topic.get("FirstURL", ""), topic.get("Text", ""))
            elif "Topics" in topic and isinstance(topic["Topics"], list):
                for sub in topic["Topics"]:
                    if isinstance(sub, dict) and "FirstURL" in sub and "Text" in sub:
                        _add(sub.get("Text", ""), sub.get("FirstURL", ""), sub.get("Text", ""))

    results.extend(
        WebSearchResult(
            title=item.get("Text", item.get("FirstURL", "")),
            url=item.get("FirstURL", ""),
            snippet=textwrap.shorten(" ".join(item.get("Snippet", "").split()), width=220, placeholder="…"),
        )
        for item in payload.get("Results", [])
        if isinstance(item, dict) and item.get("FirstURL")
    )

    # Deduplicate by URL while preserving order
    seen: set[str] = set()
    deduped: List[WebSearchResult] = []
    for item in results:
        if item.url and item.url not in seen:
            deduped.append(item)
            seen.add(item.url)
    return deduped


def web_search_impl(query: str, max_results: int = 5, region: str = "us-en") -> Dict[str, Any]:
    """Perform a lightweight DuckDuckGo lookup for documentation/best practices."""

    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "no_redirect": "1",
            "t": "kimi-coding-agent",
            "kl": region,
        }
    )
    url = f"https://api.duckduckgo.com/?{params}"

    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; KimiAgent/5.0)"})

    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        logging.warning("Web search failed for '%s': %s", query, exc)
        return WebSearchResponse(ok=False, query=query, results=[], error=str(exc)).model_dump()

    results = _extract_ddg_results(payload)[:max_results]
    return WebSearchResponse(ok=True, query=query, results=results).model_dump()


# ----------------------------------------------------------------------------
# Kimi client wiring (OpenAI-compatible) - COMPLETELY ISOLATED
# ----------------------------------------------------------------------------
def _configure_kimi_client() -> None:
    # First, clear any OpenAI environment variables that might interfere
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_BASE_URL", None)

    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing KIMI_API_KEY (or MOONSHOT_API_KEY).")

    base_url = os.getenv("KIMI_API_BASE") or os.getenv("MOONSHOT_API_BASE") or "https://api.moonshot.ai/v1"

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    set_default_openai_client(client)
    # Prefer Responses if/when you switch; keep ChatCompletions for Kimi compatibility
    set_default_openai_api("chat_completions")

    logging.info(f"Configured Kimi client with base URL: {base_url}")


# ----------------------------------------------------------------------------
# Agent & run logic
# ----------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("KIMI_MODEL") or os.getenv("MOONSHOT_MODEL") or "kimi-k2-0905-preview"


def build_agent(verbose: bool) -> Agent[AgentContext]:
    if verbose:
        enable_verbose_stdout_logging()

    instructions = """
    You are a coding agent that SCAFFOLDS REAL PROJECTS ON DISK using provided tools only.

    ## Mission
    Build complete, runnable solutions (frontend + backend + data layer) with minimal setup.

    ## Research Phase (MANDATORY before coding)
    - Call the `web_search` tool for at least one query on best practices or current SDK documentation that is relevant to the assignment.
    - Summarize how the findings influence your plan before you start writing files.
    - Re-run `web_search` whenever you introduce unfamiliar frameworks or need updated docs.

    ## Tooling & IO Rules
    - You can transform dictionaries with `build_file_map` if you need to, but `write_many` also accepts:
        • a list of `{ "path": "...", "content": "..." }` dictionaries, or
        • a JSON string with the same structure.
    - `write_text_file` automatically normalizes list/dict payloads into strings—prefer plain strings when possible.
    - You MUST write files using `write_many` (preferred) or `write_text_file`. Do NOT print full files unless explicitly asked.
    - Before claiming success, LIST the files you wrote and then VERIFY their existence by reading them back via tools.
    - All writes are relative to the provided base directory. Never write outside it.
    - Writes must be idempotent.

    ## Validation Workflow (MANDATORY)
    1) **Sandbox checks**: Use CodeInterpreter to:
        - attempt `python -m py_compile` on the created tree,
        - if a `tests/` folder exists, run `pytest -q` and capture results,
        - summarize pass/fail/errors briefly.
    2) **Local checks** (host-side tools):
        - call `py_compile_all` and confirm `compiled=True`,
        - call `run_pytest` (if pytest available); if pytest missing, add to requirements and regenerate tests minimally.
    3) Persist a structured summary via `record_validation(validation=...)` to `artifacts/validation.json`.
    4) Only after the above pass, produce a short final summary with exact run/test commands.

    ## Architecture & Integration
    - Wire frontend ↔ backend ↔ database. Provide a minimal persistence layer.
    - Include `README.md` with quickstart, env, and test instructions.
    - Include at least one runnable test and a simple command to run it.

    ## Output Policy
    - Default to a concise summary: plan → file list → validation results → next steps.
    - Only output full code when explicitly requested; otherwise, write code to disk and summarize.

    ## Success Criteria
    - [ ] Files written and verified
    - [ ] Sandbox checks pass
    - [ ] Local compile (py_compile_all) passes
    - [ ] Pytest passes (or a clear reason + remediation applied)
    - [ ] README covers run/test
    """

    tools = [
        create_directory,
        write_text_file,
        read_requirements,
        write_many,
        py_compile_all,         # NEW: host-side compile
        run_pytest,             # NEW: host-side pytest
        record_validation,      # NEW: persist results
        web_search,             # NEW: lightweight docs lookup
    ]

    agent = Agent[AgentContext](
        name="Kimi Coding Agent",
        instructions=instructions,
        tools=tools,
        model=DEFAULT_MODEL,
        model_settings=ModelSettings(temperature=0.2),
    )
    return agent


# ----------------------------------------------------------------------------
# Deterministic bootstrap (no LLM) for smoke testing writes
# ----------------------------------------------------------------------------


def bootstrap_project(base_dir: Path, requirements_path: Optional[Path]) -> None:
    # ensure directories exist
    (base_dir / "src").mkdir(parents=True, exist_ok=True)
    (base_dir / "tests").mkdir(parents=True, exist_ok=True)

    # write the starter files
    (base_dir / "README.md").write_text(
        "# Project\n\nGenerated by bootstrap.\n\n## Tests\n\n```bash\npython -m pytest -q\n```\n",
        encoding="utf-8",
    )
    (base_dir / "src" / "__init__.py").touch()
    (base_dir / "src" / "app.py").write_text(
        "def add(a, b):\n    return a + b\n\nif __name__ == '__main__':\n    print('hello from bootstrap')\n",
        encoding="utf-8",
    )
    (base_dir / "tests" / "test_smoke.py").write_text(
        "from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    (base_dir / ".gitignore").write_text("__pycache__/\n.env\n", encoding="utf-8")
    (base_dir / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools", "wheel"]\n'
        '[tool.pytest.ini_options]\npythonpath = ["."]\n',
        encoding="utf-8",
    )


# ----------------------------------------------------------------------------
# Pre-run research helpers
# ----------------------------------------------------------------------------
def _extract_keywords(data: Any) -> List[str]:
    """Heuristically collect interesting keywords from requirements data."""

    keywords: List[str] = []
    if isinstance(data, dict):
        for value in data.values():
            keywords.extend(_extract_keywords(value))
    elif isinstance(data, list):
        for item in data:
            keywords.extend(_extract_keywords(item))
    elif isinstance(data, str):
        for token in data.replace("/", " ").replace("-", " ").split():
            token_clean = token.strip().strip(",.()[]{}")
            if len(token_clean) >= 4 and token_clean.lower() not in {"project", "build", "stack"}:
                keywords.append(token_clean)
    return keywords


def _derive_research_queries(prompt: str, requirements_data: Optional[Dict[str, Any]]) -> List[str]:
    """Craft a short list of web search queries."""

    queries: List[str] = ["OpenAI Agents SDK latest documentation", "OpenAI function_tool best practices"]

    if DEFAULT_MODEL:
        queries.append(f"{DEFAULT_MODEL} API updates")

    if requirements_data:
        keywords = _extract_keywords(requirements_data)
        unique_keywords: List[str] = []
        seen_lower: set[str] = set()
        for kw in keywords:
            lowered = kw.lower()
            if lowered not in seen_lower:
                unique_keywords.append(kw)
                seen_lower.add(lowered)
        for kw in unique_keywords[:3]:
            queries.append(f"{kw} best practices 2024")

    prompt_keywords = _extract_keywords(prompt)
    for kw in prompt_keywords[:2]:
        queries.append(f"{kw} documentation")

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: List[str] = []
    for q in queries:
        q_lower = q.lower()
        if q_lower not in seen:
            ordered.append(q)
            seen.add(q_lower)
    return ordered[:6]


def perform_pre_run_research(
    base_dir: Path,
    prompt: str,
    requirements_path: Optional[Path],
    dry_run: bool = False,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Run lightweight web lookups and persist the findings for later review."""

    requirements_data: Optional[Dict[str, Any]] = None
    if requirements_path and requirements_path.exists():
        try:
            requirements_data = json.loads(requirements_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Unable to parse requirements for research: %s", exc)

    queries = _derive_research_queries(prompt, requirements_data)
    if not queries:
        return "", []

    aggregated: List[Dict[str, Any]] = []
    summary_lines: List[str] = []
    for query in queries:
        result = web_search_impl(query)
        aggregated.append(result)
        if result.get("ok") and result.get("results"):
            for item in result["results"][:2]:
                summary_lines.append(f"- {query}: {item['title']} → {item['url']}")
        else:
            summary_lines.append(f"- {query}: no results (error: {result.get('error', 'unknown')})")

    summary_text = "\n".join(summary_lines)

    if aggregated and not dry_run:
        artifacts_dir = _ensure_artifacts_dir(base_dir)
        research_path = artifacts_dir / "research.json"
        research_path.write_text(json.dumps(aggregated, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("Stored research findings at %s", research_path)

    return summary_text, aggregated


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Kimi Coding Agent (Kimi-only configuration with validation gates)")
    parser.add_argument("--requirements", type=str, default=None, help="Path to requirements JSON")
    parser.add_argument("--base-dir", type=str, required=True, help="Project output directory")
    parser.add_argument("--bootstrap", action="store_true", help="Write a minimal project without the LLM (smoke test)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just log what would happen")
    parser.add_argument("--verbose", action="store_true", help="Verbose agent logs")
    parser.add_argument("--prompt", type=str, default="Scaffold the project described in the requirements.json.")
    parser.add_argument("--skip-research", action="store_true", help="Skip automatic documentation web search")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    req_path = Path(args.requirements).expanduser().resolve() if args.requirements else None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not base_dir.exists() and not args.dry_run:
        base_dir.mkdir(parents=True, exist_ok=True)

    if args.bootstrap:
        bootstrap_project(base_dir, req_path)
        print(f"Bootstrapped project at: {base_dir}")
        return

    research_summary = ""
    if not args.skip_research:
        research_summary, _ = perform_pre_run_research(base_dir, args.prompt, req_path, dry_run=args.dry_run)
        if research_summary:
            logging.info("Pre-run research summary:\n%s", research_summary)

    # Configure Kimi client for Agents SDK - DO THIS FIRST
    _configure_kimi_client()

    # Build agent & context
    agent = build_agent(verbose=args.verbose)
    ctx = AgentContext(base_dir=base_dir, requirements_path=req_path, dry_run=args.dry_run)

    prompt_input = args.prompt
    if research_summary:
        prompt_input = f"{args.prompt}\n\n# Research Notes\n{research_summary}"

    # Kick off a single run
    result = Runner.run_sync(
        agent,
        input=prompt_input,
        context=ctx,
        max_turns=1000,
    )

    print("\n==== FINAL OUTPUT ====\n")
    if hasattr(result, "final_output") and result.final_output is not None:
        print(result.final_output)
    else:
        print("(No final_output)")


if __name__ == "__main__":
    main()
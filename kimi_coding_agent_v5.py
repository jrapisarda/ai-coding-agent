# filename: kimi_coding_agent_v5.py
import argparse
import json
import logging
import os
import sys
import subprocess
import compileall
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
def write_text_file(ctx: RunContextWrapper[AgentContext], rel_path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    return write_text_file_impl(ctx.context.base_dir, rel_path, content, overwrite, ctx.context.dry_run)


@function_tool(description_override="Read and return a JSON object from requirements_path or a provided path.")
def read_requirements(ctx: RunContextWrapper[AgentContext], rel_path: Optional[str] = None) -> Dict[str, Any]:
    req_path = Path(rel_path) if rel_path else ctx.context.requirements_path
    return read_requirements_impl(req_path)


@function_tool(description_override="Create multiple files at once using structured input.")
def write_many(
    ctx: RunContextWrapper[AgentContext],
    files: FileMap,
    overwrite: bool = True,
) -> Dict[str, Any]:
    return write_many_impl(ctx.context.base_dir, files, overwrite, ctx.context.dry_run)


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

    ## Tooling & IO Rules
    You have an extra helper function available:

        def build_file_map(files: dict[str, str]) -> FileMap:
            \"\"\"Convert plain dict into the FileMap schema the SDK requires.\"\"\"
            return FileMap(files=[FileItem(path=k, content=v) for k, v in files.items()])

        Use it every time you call write_many, e.g.:
        write_many(ctx, build_file_map({"src/App.tsx": "...", "public/index.html": "..."}), overwrite=True)
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
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    req_path = Path(args.requirements).expanduser().resolve() if args.requirements else None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if args.bootstrap:
        bootstrap_project(base_dir, req_path)
        print(f"Bootstrapped project at: {base_dir}")
        return

    # Configure Kimi client for Agents SDK - DO THIS FIRST
    _configure_kimi_client()

    # Build agent & context
    agent = build_agent(verbose=args.verbose)
    ctx = AgentContext(base_dir=base_dir, requirements_path=req_path, dry_run=args.dry_run)

    # Kick off a single run
    result = Runner.run_sync(
        agent,
        input=args.prompt,
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
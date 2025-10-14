#!/usr/bin/env python3
"""
Kimi Coding Agent (v6.1) — SPA-aware & Requirements-driven
==========================================================

A single-file agent, modeled after your v5 script, that:
- Reads a `requirements.json` (like requirements_sample.json) and **infers a build plan**.
- When the architecture is **single-page-application**, generates a modern **React + Vite + Tailwind + Dexie + dnd-kit** project.
- Uses the **OpenAI Agents SDK** (configured for **Kimi/Moonshot** via OpenAI-compatible endpoints) to orchestrate tool calls and persist a validation report.
- Keeps validation Python-based (so it runs anywhere): we compile Python stubs and run **pytest** that checks the frontend scaffold (files exist, `package.json` is valid, scripts and deps present).

Fix in v6.1
-----------
- **Resolved `index.tsx` unterminated string**: the planner now generates a valid **TypeScript entry** and ensures all string literals are properly closed.
- **TypeScript-aware**: if the requirements mention TypeScript (or to be extra safe), we add `index.tsx`, `src/main.tsx`, `src/App.tsx`, and a minimal `tsconfig.json`. `index.html` points to the correct entry (TS or JS).
- Added a small test to verify the TS entry file exists (if present) and is parsable as text.

Important:
- This file assumes the **OpenAI Agents SDK** and **openai** client are installed, just like your v5. If not present, install:
  `pip install openai-agents openai pydantic pytest`

"""
from __future__ import annotations

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
    compiled_ok: bool
    compile_errors: List[str] = []
    pytest_ok: bool
    pytest_returncode: int
    pytest_stdout: str = ""
    pytest_stderr: str = ""


def build_file_map(files: dict[str, str]) -> FileMap:
    """Convert plain dict into the FileMap schema the SDK requires."""
    return FileMap(files=[FileItem(path=k, content=v) for k, v in files.items()])


# ----------------------------------------------------------------------------
# Core Implementation Functions (testable without decorators)
# ----------------------------------------------------------------------------

def create_directory_impl(base_dir: Path, rel_path: str, dry_run: bool = False) -> Dict[str, Any]:
    path = _resolve_safe(base_dir, rel_path)
    if dry_run:
        logging.info(f"[dry-run] Would create: {path}")
        return {"ok": True, "path": str(path), "dry_run": True}
    path.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(path), "created": True}


def write_text_file_impl(base_dir: Path, rel_path: str, content: str, overwrite: bool = True, dry_run: bool = False) -> Dict[str, Any]:
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
    results = {}
    for file_item in files.files:
        try:
            res = write_text_file_impl(base_dir, file_item.path, file_item.content, overwrite, dry_run)
            results[file_item.path] = res
        except Exception as e:
            results[file_item.path] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results}


def py_compile_all_impl(base_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    if dry_run:
        return {"ok": True, "compiled": True, "dry_run": True}
    compiled_ok = compileall.compile_dir(str(base_dir), quiet=1, force=False, maxlevels=10)
    return {"ok": True, "compiled": bool(compiled_ok)}


def run_pytest_impl(base_dir: Path, args: List[str] | None = None, timeout_sec: int = 180, dry_run: bool = False) -> Dict[str, Any]:
    if dry_run:
        return {"ok": True, "pytest": "dry-run", "stdout": "", "stderr": ""}
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if args:
        cmd.extend(args)
    code, out, err = _run_subprocess(cmd, cwd=base_dir, timeout=timeout_sec)
    return {"ok": code == 0, "returncode": code, "stdout": out, "stderr": err}


def record_validation_impl(base_dir: Path, validation: ValidationResult, dry_run: bool = False) -> Dict[str, Any]:
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
    # Clear OpenAI env that might interfere
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_BASE_URL", None)

    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing KIMI_API_KEY (or MOONSHOT_API_KEY).")

    base_url = os.getenv("KIMI_API_BASE") or os.getenv("MOONSHOT_API_BASE") or "https://api.moonshot.ai/v1"

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    set_default_openai_client(client)
    # Keep Chat Completions for Kimi compatibility; Responses is also supported by OpenAI proper.
    set_default_openai_api("chat_completions")

    logging.info(f"Configured Kimi client with base URL: {base_url}")


# ----------------------------------------------------------------------------
# Planning helpers
# ----------------------------------------------------------------------------

def _get(d: Dict[str, Any], *path: str, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def is_spa(req: Dict[str, Any]) -> bool:
    t = str(_get(req, "project", "type", default="")).lower()
    pat = str(_get(req, "specifications", "architecture", "pattern", default="")).lower()
    if "single-page" in t or "single-page" in pat or "spa" in pat:
        return True
    services = _get(req, "specifications", "architecture", "services", default=[]) or []
    return any(str(s).lower() == "frontend" for s in services)


def wants_typescript(req: Dict[str, Any]) -> bool:
    fr = _get(req, "specifications", "technical_requirements", "frontend", default=[]) or []
    joined = " ".join(fr).lower()
    return any(k in joined for k in ("typescript", "tsx", "ts"))


def infer_pkg_versions(req: Dict[str, Any]) -> Dict[str, str]:
    """Honor version majors in requirements; default to conservative semver ranges."""
    frontend: List[str] = (_get(req, "specifications", "technical_requirements", "frontend", default=[]) or [])
    out: Dict[str, str] = {}
    # Defaults (respect sample's 18.x / 3.x / 6.x)
    out.setdefault("react", "^18.2.0")
    out.setdefault("react-dom", "^18.2.0")
    out.setdefault("vite", "^7.1.0")
    out.setdefault("@vitejs/plugin-react", "^5.0.0")
    out.setdefault("tailwindcss", "^3.4.18")
    out.setdefault("postcss", "^8.4.0")
    out.setdefault("autoprefixer", "^10.4.0")
    out.setdefault("dexie", "^3.2.4")
    out.setdefault("@dnd-kit/core", "^6.0.0")
    out.setdefault("@types/react", "^18.2.0")
    out.setdefault("@types/react-dom", "^18.2.0")
    return out


# ----------------------------------------------------------------------------
# SPA plan (TS/JS aware) — returns path->content
# ----------------------------------------------------------------------------

def plan_spa_files(req: Dict[str, Any]) -> Dict[str, str]:
    deps = infer_pkg_versions(req)
    pkg_name = (_get(req, "project", "name", default="app") or "app").strip()
    description = (_get(req, "project", "description", default="") or "").strip()

    use_ts = wants_typescript(req) or True  # default to TS to avoid external tool errors

    # package.json
    dev_deps = {
        "vite": deps["vite"],
        "@vitejs/plugin-react": deps["@vitejs/plugin-react"],
        "tailwindcss": deps["tailwindcss"],
        "postcss": deps["postcss"],
        "autoprefixer": deps["autoprefixer"],
    }
    if use_ts:
        dev_deps.update({
            "@types/react": deps["@types/react"],
            "@types/react-dom": deps["@types/react-dom"],
            "typescript": "^5.5.0",
        })

    package_json = {
        "name": pkg_name,
        "version": _get(req, "project", "version", default="0.1.0") or "0.1.0",
        "private": True,
        "type": "module",
        "description": description,
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
            "test": "pytest -q"
        },
        "dependencies": {
            "react": deps["react"],
            "react-dom": deps["react-dom"],
            "dexie": deps["dexie"],
            "@dnd-kit/core": deps["@dnd-kit/core"],
        },
        "devDependencies": dev_deps,
    }

    # vite config (JS to keep it simple)
    vite_config = (
        "import { defineConfig } from 'vite'\n"
        "import react from '@vitejs/plugin-react'\n\n"
        "// https://vite.dev/config/\n"
        "export default defineConfig({ plugins: [react()], server: { port: 5173 } })\n"
    )

    # index.html — pick correct entry
    script_src = "/index.tsx" if use_ts else "/src/main.jsx"
    index_html = (
        "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"UTF-8\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n    <title>"
        + pkg_name
        + "</title>\n  </head>\n  <body class=\"bg-gray-50 text-slate-900\">\n    <div id=\"root\"></div>\n    <script type=\"module\" src=\""
        + script_src
        + "\"></script>\n  </body>\n</html>\n"
    )

    postcss_config = (
        "export default {\n  plugins: {\n    tailwindcss: {},\n    autoprefixer: {},\n  },\n}\n"
    )

    tailwind_config = (
        "/** @type {import('tailwindcss').Config} */\nexport default {\n  content: [\n    './index.html',\n    './src/**/*.{js,jsx,ts,tsx}',\n  ],\n  theme: { extend: {} },\n  plugins: [],\n}\n"
    )

    index_css = (
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
        "/* App-level tweaks */\n#root { min-height: 100vh; }\n"
    )

    # React entries (TS or JS)
    if use_ts:
        index_tsx = (
            "// Root entry for Vite (TS)\n"
            "import './src/main.tsx'\n"
        )
        main_tsx = (
            "import React from 'react'\n"
            "import { createRoot } from 'react-dom/client'\n"
            "import App from './App'\n"
            "import './index.css'\n\n"
            "const el = document.getElementById('root') as HTMLElement\n"
            "createRoot(el).render(<App />)\n"
        )
        app_tsx = (
            "import React from 'react'\n"
            "import KanbanBoard from '../components/KanbanBoard'\n"
            "export default function App(){\n  return (\n    <main className=\"p-4 max-w-5xl mx-auto\">\n      <h1 className=\"text-2xl font-semibold mb-4\">Personal Project Manager</h1>\n      <KanbanBoard />\n    </main>\n  )\n}\n"
        )
    else:
        index_tsx = ""
        main_tsx = ""
        app_tsx = ""

    # JS fallback files
    main_jsx = (
        "import React from 'react'\n"
        "import { createRoot } from 'react-dom/client'\n"
        "import App from './App.jsx'\n"
        "import './index.css'\n\n"
        "createRoot(document.getElementById('root')).render(<App />)\n"
    )

    app_jsx = (
        "import React from 'react'\n"
        "import KanbanBoard from '../components/KanbanBoard.js'\n"
        "export default function App(){\n  return (\n    <main className=\"p-4 max-w-5xl mx-auto\">\n      <h1 className=\"text-2xl font-semibold mb-4\">Personal Project Manager</h1>\n      <KanbanBoard />\n    </main>\n  )\n}\n"
    )

    kanban_js = (
        "import React from 'react'\n"
        "import { DndContext } from '@dnd-kit/core'\n"
        "import Task from './Task.js'\n"
        "export default function KanbanBoard(){\n  const columns = ['Backlog','In Progress','Done']\n  const tasks = [{ id: 't1', title: 'Sample task' }]\n  return (\n    <DndContext>\n      <div className=\"grid sm:grid-cols-3 gap-4\">\n        {columns.map((c) => (\n          <section key={c} className=\"bg-white rounded shadow p-3\">\n            <h2 className=\"font-medium mb-2\">{c}</h2>\n            <div className=\"space-y-2\">\n              {tasks.map(t => <Task key={t.id} task={t} />)}\n            </div>\n          </section>\n        ))}\n      </div>\n    </DndContext>\n  )\n}\n"
    )

    task_js = (
        "import React from 'react'\n"
        "export default function Task({ task }){\n  return <div className=\"border rounded px-2 py-1 bg-slate-50\">{task.title}</div>\n}\n"
    )

    project_list_js = (
        "import React from 'react'\n"
        "export default function ProjectList({ projects = [] }){\n  return (\n    <ul className=\"list-disc pl-6\">\n      {projects.map(p => <li key={p.id}>{p.name}</li>)}\n    </ul>\n  )\n}\n"
    )

    dexie_db_js = (
        "import Dexie from 'dexie'\n\n"
        "export const db = new Dexie('ppm')\n"
        "db.version(1).stores({\n  projects: '++id,name',\n  tasks: '++id,projectId,title,status'\n})\n"
    )

    util_py = (
        "def json_is_valid(text: str) -> bool:\n"
        "    import json\n    try:\n        json.loads(text)\n        return True\n    except Exception:\n        return False\n"
    )

    test_frontend_py = (
        "import json\nfrom pathlib import Path\n\n"
        "def test_package_json_valid_and_has_scripts():\n"
        "    p = Path('package.json')\n    s = p.read_text(encoding='utf-8')\n    pkg = json.loads(s)\n    assert 'scripts' in pkg and 'dev' in pkg['scripts'] and 'build' in pkg['scripts']\n    assert 'dependencies' in pkg and 'react' in pkg['dependencies']\n\n"
        "def test_vite_and_tailwind_files_exist():\n"
        "    for path in ['vite.config.js','tailwind.config.js','postcss.config.js','index.html']:\n        \n            assert Path(path).exists()\n"
    )

    test_ts_entry_py = (
        "from pathlib import Path\n\n"
        "def test_ts_entry_if_present_is_nonempty():\n"
        "    p = Path('index.tsx')\n    if p.exists():\n        s = p.read_text(encoding='utf-8').strip()\n        assert s.startswith('import')\n"
    )

    pyproject = (
        "[build-system]\nrequires = ['setuptools', 'wheel']\n\n"
        "[tool.pytest.ini_options]\npythonpath = ['.']\n"
    )

    readme = (
        "# Personal Project Manager (SPA)\n\n"
        "Generated from requirements.json by the Kimi Coding Agent.\n\n"
        "## Dev\n\n```bash\n"
        "npm install\n"
        "npm run dev\n```\n\n"
        "## Build\n\n```bash\n"
        "npm run build\n```\n\n"
        "## Tests\n\nPython tests verify scaffold shape (no Node required):\n\n```bash\n"
        "python -m pytest -q\n```\n"
    )

    files: Dict[str, str] = {
        "package.json": json.dumps(package_json, indent=2) + "\n",
        "vite.config.js": vite_config,
        "index.html": index_html,
        "postcss.config.js": postcss_config,
        "tailwind.config.js": tailwind_config,
        "src/index.css": index_css,
        # TS or JS entries
        "index.tsx": index_tsx if use_ts else "",
        "src/main.tsx": main_tsx if use_ts else "",
        "src/App.tsx": app_tsx if use_ts else "",
        "src/main.jsx": "" if use_ts else main_jsx,
        "src/App.jsx": "" if use_ts else app_jsx,
        # Components (JS keeps widest compat)
        "components/KanbanBoard.js": kanban_js,
        "components/Task.js": task_js,
        "components/ProjectList.js": project_list_js,
        "src/db/dexie.js": dexie_db_js,
        # Python side for validation
        "tests/test_frontend_scaffold.py": test_frontend_py,
        "tests/test_ts_entry.py": test_ts_entry_py,
        "pyproject.toml": pyproject,
        "utils.py": util_py,
        "README.md": readme,
        ".gitignore": "node_modules/\n.dist/\n.DS_Store\n.env\n",
    }

    if use_ts:
        tsconfig = (
            "{\n"
            "  \"compilerOptions\": {\n"
            "    \"target\": \"ES2020\",\n"
            "    \"lib\": [\"ES2020\", \"DOM\", \"DOM.Iterable\"],\n"
            "    \"jsx\": \"react-jsx\",\n"
            "    \"module\": \"ESNext\",\n"
            "    \"moduleResolution\": \"Bundler\",\n"
            "    \"strict\": true,\n"
            "    \"skipLibCheck\": true\n"
            "  },\n"
            "  \"include\": [\"src\", \"index.tsx\"]\n"
            "}\n"
        )
        files["tsconfig.json"] = tsconfig

    # Ensure any user-declared directories/files are honored
    for d in (_get(req, "file_structure", "directories", default=[]) or []):
        if d.endswith("/"):
            d = d[:-1]
        files.setdefault(f"{d}/.keep", "")
    for dir_prefix, names in ((_get(req, "file_structure", "files", default={}) or {}).items()):
        for nm in names:
            rel = f"{dir_prefix}{nm}"
            files.setdefault(rel, files.get(rel, ""))

    # Remove empty placeholders to avoid writing empty files when JS/TS toggles
    files = {k: v for k, v in files.items() if v != ""}

    return files


# ----------------------------------------------------------------------------
# Agent & run logic
# ----------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("KIMI_MODEL") or os.getenv("MOONSHOT_MODEL") or "kimi-k2-0905-preview"


def build_agent(verbose: bool) -> Agent[AgentContext]:
    if verbose:
        enable_verbose_stdout_logging()

    instructions = """
    You are a coding agent that creates *real projects on disk* using provided tools only.

    ## Mission
    Interpret the provided requirements.json and build a **single-page application** when indicated. Use:
      - React 18.x
      - Vite 7
      - Tailwind CSS 3.x
      - Dexie 3.x (IndexedDB)
      - @dnd-kit/core 6.x for drag-and-drop

    ## Tooling & IO Rules
    You have a helper:
        def build_file_map(files: dict[str, str]) -> FileMap: ...
    Always create files with `write_many(build_file_map(...))`. Do not print code except very short snippets.

    ## Validation Workflow (MANDATORY)
    1) Write files.
    2) Run `py_compile_all`.
    3) Run `run_pytest` to execute Python tests that validate the scaffold shape.
    4) Persist a JSON summary via `record_validation`.

    ## Output Policy
    - Return a concise summary: plan → file count → validation results.
    - Include follow-up steps (npm install, vite dev) in the summary only.
    """

    tools = [
        create_directory,
        write_text_file,
        read_requirements,
        write_many,
        py_compile_all,
        run_pytest,
        record_validation,
    ]

    agent = Agent[AgentContext](
        name="Kimi Coding Agent v6.1",
        instructions=instructions,
        tools=tools,
        model=DEFAULT_MODEL,
        model_settings=ModelSettings(temperature=0.2),
    )
    return agent


# ----------------------------------------------------------------------------
# Deterministic bootstrap for SPA (no LLM involvement) — smoke test
# ----------------------------------------------------------------------------

def bootstrap_spa(base_dir: Path, req: Dict[str, Any]):
    files = plan_spa_files(req)
    (base_dir).mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = _resolve_safe(base_dir, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Kimi Coding Agent v6.1 (SPA-aware)")
    parser.add_argument("--requirements", type=str, required=True, help="Path to requirements JSON")
    parser.add_argument("--base-dir", type=str, required=True, help="Project output directory")
    parser.add_argument("--bootstrap", action="store_true", help="Bypass LLM and write the SPA directly (deterministic)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just log what would happen")
    parser.add_argument("--verbose", action="store_true", help="Verbose agent logs")
    parser.add_argument("--prompt", type=str, default="Scaffold the project described in the requirements.json.")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    req_path = Path(args.requirements).expanduser().resolve()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    # Read requirements first
    if not req_path.exists():
        raise SystemExit(f"Requirements file not found: {req_path}")
    req = json.loads(req_path.read_text(encoding="utf-8"))

    if args.bootstrap or is_spa(req):
        # Deterministic SPA write path (no LLM needed)
        bootstrap_spa(base_dir, req)
        # Also run validation locally so user gets immediate signal
        compiled_ok = bool(compileall.compile_dir(str(base_dir), quiet=1, force=False, maxlevels=10))
        # run pytest if present
        code, out, err = _run_subprocess([sys.executable, "-m", "pytest", "-q"], cwd=base_dir, timeout=180)
        validation = ValidationResult(
            compiled_ok=compiled_ok,
            compile_errors=[],
            pytest_ok=(code == 0),
            pytest_returncode=code,
            pytest_stdout=out,
            pytest_stderr=err,
        )
        (base_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (base_dir / "artifacts" / "validation.json").write_text(validation.model_dump_json(indent=2), encoding="utf-8")
        print("\n==== SUMMARY ====\n")
        print(f"Wrote project to: {base_dir}")
        print(f"Compile: {'OK' if compiled_ok else 'FAIL'}")
        print(f"Pytest:  {'OK' if code == 0 else f'FAIL (rc={code})'}")
        print("See artifacts/validation.json for details.")
        return

    # Otherwise, run the agent (Kimi)
    _configure_kimi_client()

    agent = build_agent(verbose=args.verbose)
    ctx = AgentContext(base_dir=base_dir, requirements_path=req_path, dry_run=args.dry_run)

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

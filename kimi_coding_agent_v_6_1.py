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

import re
import textwrap
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator
import shutil

# Disable OpenAI tracing and other external services
os.environ["OPENAI_AGENTS_TRACING"] = "false"
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

# ---- OpenAI Agents SDK (configured for Kimi / Moonshot) ------------------
AGENTS_AVAILABLE = True
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
    from openai import AsyncOpenAI, RateLimitError
except Exception:  # pragma: no cover - exercised via unit tests
    AGENTS_AVAILABLE = False

    class _MissingDependency:
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(
                "The OpenAI Agents SDK and openai client are required. "
                "Install with: pip install openai-agents openai"
            )

    def function_tool(*d_args: Any, **d_kwargs: Any):  # type: ignore
        def decorator(func):
            return func

        return decorator

    Agent = Runner = ModelSettings = _MissingDependency()  # type: ignore
    enable_verbose_stdout_logging = set_default_openai_client = _MissingDependency()  # type: ignore
    set_default_openai_api = _MissingDependency()  # type: ignore
    AsyncOpenAI = RateLimitError = object  # type: ignore

    class RunContextWrapper:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "The OpenAI Agents SDK is required to construct a RunContextWrapper."
            )
import asyncio 
import time 

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

def _normalize_text_content(value: Any) -> str:
    """Best-effort conversion of arbitrary JSON payloads into text content."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, dict):
        # Common alternate shapes produced by LLMs
        for key in ("text", "content", "value", "body"):
            if key in value:
                return _normalize_text_content(value[key])
        if "lines" in value:
            return "\n".join(str(line) for line in value["lines"])
        if "chunks" in value:
            return "\n".join(_normalize_text_content(chunk) for chunk in value["chunks"])
        return json.dumps(value, indent=2)
    # Fallback to repr for unexpected primitives (e.g. numbers, bool)
    return str(value)


class FileItem(BaseModel):
    """Represents a single file with path and content"""

    path: str = Field(..., description="Relative file path")
    content: str = Field(..., description="File content")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        if isinstance(data, FileItem):
            return data
        if isinstance(data, dict):
            data = dict(data)
            if "path" not in data:
                raise ValueError("Each file requires a 'path' field")
            content = data.get("content")
            if content is None and "contents" in data:
                content = data["contents"]
            data["content"] = _normalize_text_content(content)
            return data
        raise TypeError(f"Unsupported file payload: {type(data)!r}")


class FileMap(BaseModel):
    """Mapping of relative_path -> text_content in OpenAI-compatible format"""

    files: List[FileItem] = Field(..., description="List of files to create")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        if isinstance(data, FileMap):
            return data
        if isinstance(data, dict):
            if "files" in data:
                return {
                    "files": data["files"],
                }
            # Accept plain mapping of path -> content
            return {
                "files": [
                    {"path": path, "content": content}
                    for path, content in data.items()
                ]
            }
        if isinstance(data, list):
            return {"files": data}
        raise TypeError(f"Unsupported file map payload: {type(data)!r}")


class ValidationResult(BaseModel):
    """Structured validation result persisted to artifacts/validation.json"""
    compiled_ok: bool
    compile_errors: List[str] = []
    pytest_ok: bool
    pytest_returncode: int
    pytest_stdout: str = ""
    pytest_stderr: str = ""

class LintResult(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""

def build_file_map(files: dict[str, str]) -> FileMap:
    """
    Convert a plain dict returned by the LLM into the strict FileMap schema.
    Any unexpected keys inside the items are silently ignored.
    """
    return FileMap(files=files)


# ----------------------------------------------------------------------------
# Core Implementation Functions (testable without decorators)
# ----------------------------------------------------------------------------

# ----------  eslint + prettier  ----------
def _run_npm_script(
    base_dir: Path, script: str, timeout: int = 60, dry_run: bool = False
) -> Tuple[int, str, str]:
    if dry_run:
        return 0, "", ""
    return _run_subprocess(["npm", "run", script], cwd=base_dir, timeout=timeout)

def lint_and_fix_impl(base_dir: Path, dry_run: bool = False) -> LintResult:
    if dry_run:
        return LintResult(ok=True)

    # 1. install if node_modules missing
    if not (base_dir / "node_modules").is_dir():
        code, _, err = _run_subprocess(
            ["npm", "install"], cwd=base_dir, timeout=120
        )
        if code != 0:                       # install failed → don’t bother linting
            return LintResult(ok=False, stderr=err)

    # 2. lint --fix
    code, out, err = _run_subprocess(
        ["npm", "run", "lint:fix"], cwd=base_dir, timeout=60
    )
    return LintResult(ok=code == 0, stdout=out, stderr=err)


@function_tool(description_override="Run ESLint --fix inside the project.")
def lint_and_fix(ctx: RunContextWrapper[AgentContext]) -> LintResult:
    return lint_and_fix_impl(ctx.context.base_dir, ctx.context.dry_run)


def create_directory_impl(base_dir: Path, rel_path: str, dry_run: bool = False) -> Dict[str, Any]:
    path = _resolve_safe(base_dir, rel_path)
    if dry_run:
        logging.info(f"[dry-run] Would create: {path}")
        return {"ok": True, "path": str(path), "dry_run": True}
    path.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(path), "created": True}


def write_text_file_impl(
    base_dir: Path,
    rel_path: str,
    content: Any,
    overwrite: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    path = _resolve_safe(base_dir, rel_path)
    if path.exists() and not overwrite:
        return {"ok": False, "error": "File exists and overwrite=False", "path": str(path)}
    normalized_content = _normalize_text_content(content)
    if dry_run:
        logging.info(f"[dry-run] Would write {len(normalized_content)} bytes to: {path}")
        return {"ok": True, "path": str(path), "bytes": len(normalized_content), "dry_run": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized_content, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": len(normalized_content)}


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


def read_text_file_impl(base_dir: Path, rel_path: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
    path = _resolve_safe(base_dir, rel_path)
    if not path.exists():
        return {"ok": False, "error": "File not found", "path": str(path)}
    data = path.read_bytes()
    if max_bytes is not None and len(data) > max_bytes:
        return {
            "ok": False,
            "error": f"File exceeds max_bytes ({len(data)} > {max_bytes})",
            "path": str(path),
        }
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "ok": False,
            "error": "File is not valid UTF-8",
            "path": str(path),
        }
    return {"ok": True, "path": str(path), "content": text, "bytes": len(data)}


def list_directory_impl(base_dir: Path, rel_path: str = ".") -> Dict[str, Any]:
    path = _resolve_safe(base_dir, rel_path)
    if not path.exists():
        return {"ok": False, "error": "Directory not found", "path": str(path)}
    if not path.is_dir():
        return {"ok": False, "error": "Not a directory", "path": str(path)}
    entries = []
    for child in sorted(path.iterdir()):
        info = {
            "name": child.name,
            "is_dir": child.is_dir(),
            "is_file": child.is_file(),
        }
        entries.append(info)
    return {"ok": True, "path": str(path), "entries": entries}


def write_many_impl(base_dir: Path, files: FileMap, overwrite: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    results = {}
    overall_ok = True
    for file_item in files.files:
        try:
            res = write_text_file_impl(base_dir, file_item.path, file_item.content, overwrite, dry_run)
            results[file_item.path] = res
            if not res.get("ok", False):
                overall_ok = False
        except Exception as e:
            results[file_item.path] = {"ok": False, "error": str(e)}
            overall_ok = False
    return {"ok": overall_ok, "results": results}


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
def write_text_file(
    ctx: RunContextWrapper[AgentContext],
    rel_path: str,
    content: Any,
    overwrite: bool = True,
) -> Dict[str, Any]:
    return write_text_file_impl(
        ctx.context.base_dir, rel_path, content, overwrite, ctx.context.dry_run
    )


@function_tool(description_override="Read and return a JSON object from requirements_path or a provided path.")
def read_requirements(ctx: RunContextWrapper[AgentContext], rel_path: Optional[str] = None) -> Dict[str, Any]:
    req_path = Path(rel_path) if rel_path else ctx.context.requirements_path
    return read_requirements_impl(req_path)


@function_tool(description_override="Read a UTF-8 text file relative to base_dir.")
def read_text_file(
    ctx: RunContextWrapper[AgentContext],
    rel_path: str,
    max_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    return read_text_file_impl(ctx.context.base_dir, rel_path, max_bytes)


@function_tool(description_override="List directory entries relative to base_dir.")
def list_directory(
    ctx: RunContextWrapper[AgentContext],
    rel_path: str = ".",
) -> Dict[str, Any]:
    return list_directory_impl(ctx.context.base_dir, rel_path)


@function_tool(description_override="Create multiple files at once using structured input.")
def write_many(
    ctx: RunContextWrapper[AgentContext],
    files: Any,
    overwrite: bool = True,
) -> Dict[str, Any]:
    file_map = FileMap.model_validate(files)
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


# ----------------------------------------------------------------------------
# Subprocess helper (used by run_pytest_impl)
# ----------------------------------------------------------------------------

def _run_subprocess(
    cmd: List[str],
    cwd: Path,
    timeout: int,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    # ----------  Windows-safe command resolution  ----------
    executable = shutil.which(cmd[0])
    if executable is None:
        raise RuntimeError(
            f"{cmd[0]!r} not found on PATH – is Node/npm installed?"
        )
    cmd[0] = executable
    # -------------------------------------------------------

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

# ----------  v6.2  templates  ----------
def _eslint_json() -> str:
    return json.dumps(
        {
            "root": True,
            "parser": "@typescript-eslint/parser",
            "plugins": ["@typescript-eslint", "react-refresh", "react-hooks"],
            "extends": [
                "eslint:recommended",
                "plugin:@typescript-eslint/recommended",
                "plugin:react-hooks/recommended",
            ],
            "parserOptions": { "ecmaVersion": 2020, "sourceType": "module", "ecmaFeatures": { "jsx": True } },
            "rules": { "react-refresh/only-export-components": "warn", "react-hooks/exhaustive-deps": "error" },
            "env": { "browser": True, "es2020": True },
            "settings": { "react": { "version": "detect" } },
        },
        indent=2,
    )


def _prettierrc() -> str:
    return json.dumps({ "semi": True, "singleQuote": True, "trailingComma": "es5", "printWidth": 88 }, indent=2)


def _vite_config_ts() -> str:
    return textwrap.dedent(
        """\
        import { defineConfig } from 'vite'
        import react from '@vitejs/plugin-react'
        // https://vitejs.dev/config/
        export default defineConfig({
          plugins: [react()],
          server: { port: 5173 },
          test: { globals: true, environment: 'jsdom' }
        })\
        """
    )


def _tsconfig_strict() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2020",
                "lib": ["ES2020", "DOM", "DOM.Iterable"],
                "jsx": "react-jsx",
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "strict": True,
                "skipLibCheck": True,
                "esModuleInterop": True,
                "allowSyntheticDefaultImports": True,
                "forceConsistentCasingInFileNames": True,
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": True,
            },
            "include": ["src", "index.tsx"],
        },
        indent=2,
    )


def _hello_vitest_test_tsx() -> str:
    return textwrap.dedent(
        """\
        import { expect, test } from 'vitest'
        import { render, screen } from '@testing-library/react'
        import App from '../src/App'

        test('renders headline', () => {
          render(<App />)
          expect(screen.getByText(/Personal Project Manager/i)).toBeInTheDocument()
        })\
        """
    )


def _playwright_config_js() -> str:
    return textwrap.dedent(
        """\
        import { defineConfig, devices } from '@playwright/test'
        export default defineConfig({
          testDir: './e2e',
          fullyParallel: true,
          forbidOnly: !!process.env.CI,
          retries: process.env.CI ? 2 : 0,
          use: { trace: 'on-first-retry' },
          projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
        })\
        """
    )


def _sample_e2e_spec_ts() -> str:
    return textwrap.dedent(
        """\
        import { test, expect } from '@playwright/test'
        test('homepage renders', async ({ page }) => {
          await page.goto('/')
          await expect(page.locator('h1')).toContainText('Personal Project Manager')
        })\
        """
    )

def _configure_kimi_client() -> None:
    # Clear OpenAI env that might interfere
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_BASE_URL", None)

    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing KIMI_API_KEY (or MOONSHOT_API_KEY).")

    base_url = os.getenv("KIMI_API_BASE") or os.getenv("MOONSHOT_API_BASE") or "https://api.moonshot.ai/v1"

    client = AsyncOpenAI(base_url=base_url, api_key=api_key,max_retries=10,timeout=180,)
    set_default_openai_client(client)
    # Keep Chat Completions for Kimi compatibility; Responses is also supported by OpenAI proper.
    set_default_openai_api("chat_completions")

    logging.info(f"Configured Kimi client with base URL: {base_url}")

    async def _on_429(response) -> None:
            # response is the httpx.Response object
            if response.status_code == 429:
                # Moonshot returns JSON: {"error":{"type":"engine_overloaded_error",...}}
                try:
                    body = response.json()
                    if body.get("error", {}).get("type") == "engine_overloaded_error":
                        await asyncio.sleep(60)   # 30-second nap
                except Exception:
                    pass            # ignore parse errors, fall back to SDK retry

        # 4.  register the hook
    client._client.event_hooks["response"].append(_on_429)

    set_default_openai_client(client)
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
    """Return conservative ranges plus new v6.2 packages."""
    out = {
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "vite": "^5.0.0",
        "@vitejs/plugin-react": "^4.2.0",
        "tailwindcss": "^3.4.0",
        "postcss": "^8.4.0",
        "autoprefixer": "^10.4.0",
        "dexie": "^4.0.0",
        "@dnd-kit/core": "^6.1.0",
        "@types/react": "^18.3.0",
        "@types/react-dom": "^18.3.0",
        # ----  v6.2  ----
        "react-router-dom": "^6.20.0",
        "@tanstack/react-query": "^5.0.0",
        "@headlessui/react": "^1.7.0",
        "clsx": "^2.0.0",
        # dev
        "typescript": "^5.5.0",
        "eslint": "^8.57.0",
        "prettier": "^3.2.0",
        "@typescript-eslint/eslint-plugin": "^7.0.0",
        "@typescript-eslint/parser": "^7.0.0",
        "eslint-plugin-react-hooks": "^4.6.0",
        "eslint-plugin-react-refresh": "^0.4.0",
        "vitest": "^1.2.0",
        "@playwright/test": "^1.40.0",
    }
    # allow user to pin majors
    frontend = _get(req, "specifications", "technical_requirements", "frontend", default=[])
    for pkg in frontend:
        m = re.match(r"(.+?)@([\^~]?\d+(?:\.\d+)?(?:\.\d+)?)", pkg)
        if m:
            out[m.group(1)] = m.group(2)
    return out


# ----------------------------------------------------------------------------
# SPA plan (TS/JS aware) — returns path->content
# ----------------------------------------------------------------------------

def plan_spa_files(req: Dict[str, Any]) -> Dict[str, str]:
    deps = infer_pkg_versions(req)
    pkg_name = (_get(req, "project", "name", default="app") or "app").strip()
    description = (_get(req, "project", "description", default="") or "").strip()

    use_ts = wants_typescript(req) or True  # default to TS to avoid external tool errors

    files: Dict[str, str] = {}
    
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
            "build": "tsc && vite build" if use_ts else "vite build",
            "preview": "vite preview",
            "test": "vitest",
            "test:e2e": "playwright test",
            "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
            "lint:fix": "eslint . --ext ts,tsx --fix",
            "format": "prettier --write .",
        },
        "dependencies": {
           "react": deps["react"],
            "react-dom": deps["react-dom"],
            "dexie": deps["dexie"],
            "@dnd-kit/core": deps["@dnd-kit/core"],
            "react-router-dom": deps["react-router-dom"],
            "@tanstack/react-query": deps["@tanstack/react-query"],
            "@headlessui/react": deps["@headlessui/react"],
            "clsx": deps["clsx"],
        },
        "devDependencies": dev_deps,
    }

    # vite config (JS to keep it simple)
    vite_config = _vite_config_ts()
    files["vite.config.ts"] = vite_config
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
        "vite.config.ts": _vite_config_ts(),
        "tsconfig.json": _tsconfig_strict() if use_ts else "",
        "tailwind.config.js": tailwind_config,
        "postcss.config.js": postcss_config,
        "index.html": index_html,
        "src/index.css": index_css,
        "src/main.tsx": main_tsx if use_ts else "",
        "src/App.tsx": app_tsx if use_ts else "",
        "src/routes.tsx": textwrap.dedent(
            """\
            import { createBrowserRouter } from 'react-router-dom'
            import App from './App'
            export const router = createBrowserRouter([{ path: '/', element: <App /> }])\
            """
        ),
        "src/db/dexie.ts": textwrap.dedent(
            """\
            import Dexie from 'dexie'
            export interface Project { id?: number; name: string }
            export interface Task { id?: number; projectId: number; title: string; status: string }
            export class PPM extends Dexie {
              projects!: Dexie.Table<Project, number>
              tasks!: Dexie.Table<Task, number>
              constructor() {
                super('ppm')
                this.version(1).stores({ projects: '++id,name', tasks: '++id,projectId,title,status' })
              }
            }
            export const db = new PPM()\
            """
        ),
        "src/hooks/useDexie.ts": textwrap.dedent(
            """\
            import { useLiveQuery } from 'dexie-react-hooks'
            import { db, type Project, type Task } from '../db/dexie'
            export const useProjects = () => useLiveQuery(() => db.projects.toArray())
            export const useTasks = (projectId: number) =>
              useLiveQuery(() => db.tasks.where('projectId').equals(projectId).toArray(), [projectId])\
            """
        ),
        "src/hooks/useDnd.ts": textwrap.dedent(
            """\
            import { useState } from 'react'
            import type { DragEndEvent } from '@dnd-kit/core'
            export function useDndColumns<T>(initial: T[]) {
              const [cols, setCols] = useState(initial)
              const handleDragEnd = (e: DragEndEvent) => {
                console.log(e)
              }
              return { cols, handleDragEnd }
            }\
            """
        ),
        "components/KanbanBoard.tsx": textwrap.dedent(
            """\
            import { DndContext } from '@dnd-kit/core'
            import { useDndColumns } from '../src/hooks/useDnd'
            import Task from './Task'
            const columns = ['Backlog', 'In Progress', 'Done']
            export default function KanbanBoard() {
              const { cols, handleDragEnd } = useDndColumns(columns)
              return (
                <DndContext onDragEnd={handleDragEnd}>
                  <div className='grid sm:grid-cols-3 gap-4'>
                    {cols.map(c => (
                      <section key={c} className='bg-white rounded shadow p-3'>
                        <h2 className='font-medium mb-2'>{c}</h2>
                        <Task title='Sample task' />
                      </section>
                    ))}
                  </div>
                </DndContext>
              )
            }\
            """
        ),
        "components/Task.tsx": textwrap.dedent(
            """\
            import { clsx } from 'clsx'
            export default function Task({ title }: { title: string }) {
              return <div className={clsx('border rounded px-2 py-1 bg-slate-50')}>{title}</div>
            }\
            """
        ),
        ".eslintrc.json": _eslint_json(),
        ".prettierrc": _prettierrc(),
        "tests/hello.test.tsx": _hello_vitest_test_tsx(),
        "e2e/home.spec.ts": _sample_e2e_spec_ts(),
        "playwright.config.js": _playwright_config_js(),
        "README.md": readme,
        ".gitignore": "node_modules/\ndist/\n.DS_Store\n.env\n/playwright-report\n/vitest-ui\n",
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
    if not AGENTS_AVAILABLE:
        raise RuntimeError(
            "The OpenAI Agents SDK and openai client are required to build the agent. "
            "Install with: pip install openai-agents openai"
        )
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
    Use `read_text_file` and `list_directory` to inspect the workspace instead of guessing.

    ## Validation Workflow (MANDATORY)
    1) Write files.
    2) Run `lint_and_fix` so the scaffold always compiles.
    3) Run `py_compile_all`.
    4) Run `run_pytest`.
    5) Persist summary via `record_validation`.

    ## Output Policy
    - Return a concise summary: plan → file count → validation results.
    - Include follow-up steps (npm install, vite dev) in the summary only.
    """

    tools = [
        create_directory,
        write_text_file,
        read_requirements,
        read_text_file,
        list_directory,
        write_many,
        py_compile_all,
        run_pytest,
        record_validation,
        lint_and_fix,
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

    files["pyproject.toml"] = (
        '[tool.pytest.ini_options]\n'
        'pythonpath = ["."]\n'
        'testpaths = ["."]\n'
)
    # 2.  test_scaffold.py
    files["test_scaffold.py"] = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def test_package_json_exists_and_has_scripts():\n"
        "    pkg = json.loads(Path('package.json').read_text())\n"
        "    assert 'scripts' in pkg\n"
        "    assert 'dev' in pkg['scripts']\n"
        "    assert 'build' in pkg['scripts']\n\n"
        "def test_vite_and_tailwind_files_exist():\n"
        "    for name in ['vite.config.ts', 'tailwind.config.js', 'postcss.config.js', 'index.html']:\n"
        "        assert Path(name).exists()\n"
    )

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
    parser.add_argument("--upgrade",action="store_true",help="Re-write an existing project in-place (keeps .git)")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    req_path = Path(args.requirements).expanduser().resolve()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    # Read requirements first
    if not req_path.exists():
        raise SystemExit(f"Requirements file not found: {req_path}")
    req = json.loads(req_path.read_text(encoding="utf-8"))

    if args.bootstrap:
        # Deterministic SPA write path (no LLM needed)
        bootstrap_spa(base_dir, req)
        lint_res = lint_and_fix_impl(base_dir, dry_run=args.dry_run)
        print(f"Lint-fix: {'OK' if lint_res.ok else 'FAIL'}")

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
        
    if args.upgrade:
        if not base_dir.exists():
            raise SystemExit("Directory does not exist; can't upgrade.")
        # keep a git stash-like backup
        subprocess.run(["git", "stash", "push", "-m", "kimi-agent-backup"], cwd=base_dir)
        args.bootstrap = True  # force deterministic rewrite


if __name__ == "__main__":
    main()

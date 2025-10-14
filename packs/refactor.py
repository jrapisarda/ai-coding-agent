"""
Refactor pack – black, ruff, mypy, pytest, CI, pre-commit.
"""
import textwrap
from pathlib import Path
from kimi_coding_agent_v_6_1 import ValidationResult, AgentContext, _run_subprocess

def plan_files(_req: dict) -> dict[str, str]:
    return {
        "pyproject.toml": textwrap.dedent("""\
            [tool.ruff]
            line-length = 88
            select = ["E", "F", "I", "N", "UP", "ANN", "S", "B", "C4", "DTZ", "TCH"]
            ignore = ["ANN101"]

            [tool.black]
            line-length = 88

            [tool.mypy]
            strict = true
        """),
        ".github/workflows/ci.yml": textwrap.dedent("""\
            name: CI
            on: [push, pull_request]
            jobs:
              lint:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                  - uses: actions/setup-python@v4
                    with: { python-version: "3.11" }
                  - run: pip install ruff black mypy pytest
                  - run: ruff check .
                  - run: black --check .
                  - run: mypy src
                  - run: pytest
        """),
        ".pre-commit-config.yaml": textwrap.dedent("""\
            repos:
              - repo: https://github.com/astral-sh/ruff-pre-commit
                rev: v0.1.0
                hooks: [id: ruff]
              - repo: https://github.com/psf/black
                rev: 23.9.1
                hooks: [id: black]
        """),
        "README_refactor.md": "# Refactored with kimī agent\n\nBlack + Ruff + MyPy + pre-commit enabled.",
    }

def validate(ctx: AgentContext) -> ValidationResult:
    dry = ctx.dry_run
    def run(cmd):
        return _run_subprocess(cmd, cwd=ctx.base_dir, timeout=60)

    code, _, _ = run([sys.executable, "-m", "ruff", "check", "."])
    ruff_ok = dry or code == 0
    code, _, _ = run([sys.executable, "-m", "black", "--check", "."])
    black_ok = dry or code == 0
    code, _, _ = run([sys.executable, "-m", "mypy", "src"])
    mypy_ok = dry or code == 0
    code, out, err = run([sys.executable, "-m", "pytest", "-q"])
    pytest_ok = dry or code == 0

    return ValidationResult(
        compiled_ok=ruff_ok and black_ok and mypy_ok,
        compile_errors=[],
        pytest_ok=pytest_ok,
        pytest_returncode=0 if pytest_ok else 1,
        pytest_stdout=out,
        pytest_stderr=err,
    )
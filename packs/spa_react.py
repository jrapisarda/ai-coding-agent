"""
React pack – thin wrapper around the *existing* plan_spa_files.
"""
from kimi_coding_agent_v_6_1 import plan_spa_files, ValidationResult, AgentContext, _run_subprocess, sys

def plan_files(req: dict) -> dict[str, str]:
    return plan_spa_files(req)

def validate(ctx: AgentContext) -> ValidationResult:
    dry = ctx.dry_run
    def run(cmd):
        return _run_subprocess(cmd, cwd=ctx.base_dir, timeout=120)
    # npm install if needed
    if not dry and not (ctx.base_dir / "node_modules").is_dir():
        run(["npm", "install"])
    # lint
    code, out, err = run(["npm", "run", "lint:fix"])
    lint_ok = dry or code == 0
    # pytest (python scaffold tests)
    code, pout, perr = run([sys.executable, "-m", "pytest", "-q"])
    pytest_ok = dry or code == 0
    return ValidationResult(
        compiled_ok=lint_ok,
        compile_errors=[],
        pytest_ok=pytest_ok,
        pytest_returncode=0 if pytest_ok else 1,
        pytest_stdout=pout,
        pytest_stderr=perr,
    )
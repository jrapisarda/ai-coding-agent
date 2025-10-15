# Developer Experience & Tooling

## Repository Conventions
- **Branching**: `main` protected; feature branches use `epic/<epic-no>-<short-description>`.
- **Commit Style**: Conventional Commits (e.g., `feat: add prospect scoring pipeline`).
- **Directory Layout**: Mirror high-level architecture (services, infra, docs, tests) with
  co-located `README.md` files describing module purpose.

## Automation & Toolchain
- **Package Management**: `uv` manages Python environments per service. Root `pyproject.toml`
  defines shared dependencies; services can extend via `uv pip install -r requirements.txt`.
- **Pre-commit Hooks**:
  - `black` (line-length 100)
  - `ruff` (lint, import sorting)
  - `mypy --strict`
  - `pytest --maxfail=1 --disable-warnings`
  The configuration lives in `.pre-commit-config.yaml`; CI enforces `pre-commit run --all-files`.
- **CI/CD Skeleton**: GitHub Actions workflows for `lint`, `type-check`, and `unit-test` jobs,
  triggered on pull requests targeting `main`. Cache `uv` environments to minimize runtime.
- **Containerization**: `docker-compose` orchestrates local dependencies (PostgreSQL, Redis, MinIO,
  Mailhog). Service Dockerfiles inherit from a hardened Python base image with non-root user.

## Documentation Assets
- **Contribution Guide**: Maintained via [`./templates/contributing.md`](./templates/contributing.md).
- **ADR Template**: Provided at [`./templates/adr-template.md`](./templates/adr-template.md) and copied
  for every significant decision.
- **Runbooks**: Each service contributes runbooks stored under `ops/runbooks/` (incident response,
  rollback, rate limit). Runbooks must be updated when new failure modes are introduced.

## Developer Workflow
1. Bootstrap environment using `uv venv` and `uv pip sync` per service requirements file.
2. Run `make sandbox` (see sandbox blueprint) to provision ephemeral infrastructure locally or in
   AWS sandbox account.
3. Develop feature behind feature flag when touching production pathways.
4. Execute `make qa` before opening PR; command wraps linting, typing, unit tests, and security scans.
5. Submit PR referencing relevant task IDs; request reviewers from both product and engineering.

## Knowledge Sharing & Onboarding
- Weekly engineering office hours rotate between services for knowledge transfer.
- `docs/playbooks/` hosts quick-start guides; new engineers complete onboarding checklist within
  first sprint.
- Architectural diagrams stored in `docs/architecture/` and maintained via `structurizr` or `diagrams`.

## Tooling Backlog (post-epic follow-ups)
- Integrate dependency scanning (Snyk) into CI.
- Add automated license compliance check.
- Implement ChatOps command `/run e2e` to trigger integration suite in sandbox.

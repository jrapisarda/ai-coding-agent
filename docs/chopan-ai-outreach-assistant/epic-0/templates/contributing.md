# Contributing Guide

Welcome to the chopan-ai-outreach-assistant program! This guide outlines expectations for
contributors working within the epic sandbox model.

## Prerequisites
- Python 3.11+ and Node.js 20+ installed locally.
- `uv`, `docker`, and `docker-compose` available on the command line.
- Access to the current epic sandbox account and Secrets Manager entries.

## Workflow Overview
1. **Pick a Task**: Select an issue marked `Ready` in the GitHub project board. Assign yourself.
2. **Create Branch**: `git checkout -b epic/<epic-no>-<task-slug>`.
3. **Sync Dependencies**: Run `uv pip sync` (Python) and `pnpm install` or `npm install` (frontend).
4. **Develop & Test**:
   - Write unit tests alongside code.
   - Run `pre-commit run --all-files` before pushing.
   - Use `make sandbox-up` to run services locally.
5. **Pull Request**:
   - Fill PR template including summary, test plan, security considerations.
   - Request reviewers from at least two disciplines (engineering + product/QA).
6. **Post-Merge**:
   - Ensure deployment pipeline completes.
   - Update documentation or runbooks if behavior changed.

## Coding Standards
- Favor typed Python (mypy strict) and prefer dataclasses/pydantic models for schemas.
- Keep functions <40 lines where reasonable; break large workflows into reusable components.
- Document public APIs with docstrings and add OpenAPI annotations in FastAPI routes.
- Ensure log messages include correlation IDs and avoid sensitive data.

## Communication
- Use project Slack channel for daily updates and async stand-up responses.
- Record design discussions in ADRs and link from relevant issues.
- Escalate blockers >24 hours to the delivery manager.

## Support
- Reference `docs/playbooks/onboarding.md` for environment setup.
- Contact DevEx team via `#devx-support` for tooling questions.

Thank you for contributing!

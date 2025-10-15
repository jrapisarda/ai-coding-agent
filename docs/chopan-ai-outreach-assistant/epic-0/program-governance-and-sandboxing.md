# Program Governance & Sandboxing

## Governance Model
- **Cadence**: Two-week sprints with mid-sprint backlog refinement and end-of-sprint review +
  retrospective. Release train aligned with sprint review outcome.
- **Roles**:
  - *Product Lead*: prioritizes backlog, approves scope changes.
  - *Tech Lead*: owns architecture decisions, ensures quality gates.
  - *Delivery Manager*: tracks capacity, monitors risk burndown, facilitates ceremonies.
  - *QA Lead*: defines testing strategy, enforces coverage/reporting requirements.
- **Definition of Done (DoD)**:
  1. Code merged with passing CI (lint, type-check, unit tests, coverage ≥80% for touched areas).
  2. Updated documentation (OpenAPI, runbooks, ADRs) where relevant.
  3. Observability hooks (logging, metrics, traces) validated in sandbox.
  4. Compliance sign-off for data-handling changes.
- **Decision Records**: All architecture or process changes require an ADR created via the template
  provided in [`./templates/adr-template.md`](./templates/adr-template.md) and stored under
  `docs/adr/` in the target repository.

## Backlog & Issue Hygiene
- Adopt GitHub Projects for sprint planning with columns: *Backlog*, *Ready*, *In Progress*,
  *Review*, *Done*.
- Every work item must include:
  - Problem statement & success metrics.
  - Links to relevant specs or compliance policies.
  - Test plan outlining unit/integration coverage expectations.
- Blockers older than 48 hours escalated in daily stand-up.

## Sandboxing Strategy
- **Per-Epic Sandboxes**: Each epic executes in an isolated AWS account + VPC to avoid shared state
  interference. Terraform workspaces manage environment-specific state.
- **Secrets Handling**: Secrets injected via AWS Secrets Manager with short-lived tokens; no secrets
  in source control. Local development uses `.env.sandbox` encrypted with `sops`.
- **Data Policy**:
  - Synthetic datasets only; no production PII.
  - Automatic teardown scripts ensure data purged after epic completion.
  - S3 buckets enabled with versioning + lifecycle policy (30-day retention) for audit trails.
- **Access Controls**: RBAC groups for developers, reviewers, and compliance officers. Access
  requests tracked via ticketing system with 24-hour SLA.

## Quality & Risk Management
- Weekly risk review capturing technical, operational, and compliance risks with mitigation owners.
- Change control board meets on-demand for high-risk deployments.
- Incident response simulation scheduled once per quarter using runbook in `ops/runbooks/`.

## Communication
- Daily stand-up (15 minutes) in shared channel with async updates for distributed teams.
- Sprint review deck stored in shared knowledge base; recordings archived for 6 months.
- Decision logs aggregated into monthly governance report delivered to leadership.

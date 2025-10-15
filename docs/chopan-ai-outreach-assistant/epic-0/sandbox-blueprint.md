# Sandbox Blueprint

## Purpose
Provide a repeatable recipe for spinning up isolated environments where each epic can be
implemented, tested, and demoed without impacting other efforts.

## Environment Composition
- **Networking**: Dedicated VPC with two private subnets and one public subnet. NAT gateway shared
  within the sandbox account. Security groups restrict ingress to bastion and ALB.
- **Compute**: ECS Fargate cluster sized for microservices with capacity providers `spot` (cost
  savings) and `on-demand` (baseline reliability).
- **Data Stores**:
  - PostgreSQL (RDS) single-AZ for sandbox with automated snapshots daily.
  - Redis (ElastiCache) in cache.t3.small tier.
  - MinIO (local) or S3 bucket with versioning for artifact snapshots.
- **Observability**: CloudWatch metrics/alarms, OpenTelemetry collector forwarding traces to
  sandbox Grafana stack, Sentry DSN dedicated to sandbox.

## Provisioning Workflow
1. Clone infrastructure repository and run `uv run terraform init` targeting the sandbox workspace.
2. Execute `terraform apply -var-file=environments/sandbox.tfvars`.
3. Populate Secrets Manager via `scripts/bootstrap_secrets.py` (reads from encrypted `secrets.enc`).
4. Trigger GitHub Actions workflow `sandbox-deploy` to build and push service images tagged with the
   epic ID (e.g., `epic-0`).
5. Notify QA lead once smoke tests pass.

## Data Management
- Seed synthetic data using `scripts/chopan seeds --prospects --env sandbox`.
- Enable automatic rollback via `scripts/snapshot_create.py --env sandbox` before risky changes.
- After epic completion, run `scripts/destroy_sandbox.py` to tear down compute and purge data, keeping
  only compliance snapshots in S3 per retention policy.

## Access & Security
- Access via federated IAM roles (`EngineerSandbox`, `ReviewerSandbox`). MFA enforced.
- Bastion host rotates SSH keys every 24 hours; credentials distributed through secure vault.
- Logging retained for 30 days; audit logs exported to central security account.

## Validation Checklist
- [x] Infrastructure code validated with `terraform validate` and `tflint`.
- [x] Smoke tests executed post-deploy (content service health, email webhook ingestion, worker queues).
- [x] Observability dashboards show traffic, errors, latency for each service.
- [x] Sandbox teardown documented and rehearsed.

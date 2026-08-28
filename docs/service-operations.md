# Municipal service operations

## Daily checks

- `/health` confirms process liveness.
- `/ready` confirms schema, required city data and core dependencies.
- `/api/v1/service-health` adds tenant-visible database, worker, object storage, tile and
  required-data status.
- `/api/v1/metrics` is Administrator-only and uses bounded route labels.
- Operations shows queued/running/failed/cancelled jobs, worker heartbeat, failed data
  versions, backup records, releases and immutable audit events.

These signals are measurement points. They do not create an SLA by themselves.

## Job handling

Jobs are durable database records with stage events and heartbeats. A queued job may be
cancelled after explicit confirmation. A failed job may be reset only within its retry
limit. The API does not kill a running process; an operator must stop it in the execution
environment and preserve the audit trail.

## Backup and restore

Use the repository backup/restore scripts and record checksum, storage URI, schema
version and status. Restore into an isolated target first, validate migrations and
tenant counts, then perform the approved cutover. Never use an untested backup as proof
of recoverability.

## Incident support bundle

Collect request ID, release version, migration version, health details, redacted job
events and relevant audit IDs. Exclude tokens, credentials, attachment bytes and
restricted record bodies unless separately authorized.

## Organization settings and retention

Administrator may record only the documented non-secret settings. Credentials, tokens,
private keys and passwords remain deployment secret-manager inputs. Configuration
updates use the last `updated_at` value so concurrent edits fail visibly.

Retention records cover audit, field observation, attachment and Job resources. A null
duration means the municipality has not supplied an approved duration. The current
service records and audits the policy but does not execute purges and does not implement
legal hold. Those controls require municipal governance approval, an implementation and
a restore-tested rollout before enablement.

# Validation and day-2 runbook

This runbook applies to the authenticated municipal workspace. Public GitHub
Pages is a read-only demonstration and must never receive municipal notes,
actor identity, per-building demographic estimates, credentials or raw uploads.

## Dataset update

Register a new immutable dataset version and SHA-256, inspect the source, run
the quality gate, build an `urban_state`, then run `dataset_diff`. Do not mark
the version current until ingestion and reconciliation succeed. Run affected
scopes incrementally and compare count/hash/metrics with a full rebuild before
activation. A failed or partial version remains non-current and auditable.

## Failed job and worker restart

Inspect the job, attempt, event and audit rows. Fix the versioned input or
operator-controlled command; never inject a command through job parameters.
An expired heartbeat is reclaimed only after the configured stale interval.
The attempt is requeued within its retry bound or becomes durably `failed`.
After a worker restart, verify one claim, ordered stages, heartbeats, and the
absence of duplicate effects before increasing concurrency.

## Backup and restore

Create an encrypted, access-controlled off-host custom-format dump under the
municipality's retention policy. Restore only into a new isolated database.
Verify PostGIS/pgRouting, every migration checksum, current dataset/network
versions, scenario/validation/evidence counts and audit continuity. The CI
fixture in `infra/scripts/verify_backup_restore.sh` checks command and schema
compatibility, not a municipal RPO/RTO.

## Network version update and reanalysis

Register source URL, retrieval date, license, attribution, SHA-256, extraction
rule, coverage and limitations. An official/manual network never silently
replaces the experimental model. Re-run common-OD validation, snapping,
stress-test sensitivity, criticality sensitivity, scenario analysis and
Evidence exports against the explicit network version. Keep prior runs.

## Scenario reanalysis

Create a new run referencing exact urban state, datasets, network, algorithm
and configuration hashes. Do not edit a reviewed run. Compare A/B/C without an
automatic recommendation and preserve known limitations and field status.

## User role change

Map verified OIDC subjects to the least municipal role. Viewer reads;
analyst runs validation; planner records field/municipal review; administrator
registers reference datasets. Record before/after roles and actor in the audit
log. Revoke access before archival when staff leave the pilot.

## Evidence regeneration

Regenerate into a new versioned directory. Re-hash JSON, CSV and print HTML,
validate that every artifact resolves within the directory, and compare the
manifest with its exact source/network/algorithm versions. Never overwrite a
reviewed package. Evidence corruption is a hard failure, not a warning.

## CI fixture coverage

The validation gates exercise deterministic route sampling, cross-model
contracts, safe failure injection, upload/XML/ZIP attacks, public-asset privacy,
accessibility checks and the 18-stage rehearsal. Database-specific duplicate
job, partial ingestion rollback, stale-worker recovery, migration checks and
backup/restore run only against ephemeral PostGIS. Production chaos is forbidden.

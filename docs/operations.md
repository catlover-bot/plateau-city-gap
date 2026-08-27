# Pilot operations

## Start

Copy `.env.example` to `.env`, replace the database password for every shared
environment, then run:

```bash
docker compose up --build
```

The command starts pinned PostgreSQL/PostGIS/pgRouting, runs checksum-verified migrations
once, and starts the API, PostgreSQL-backed worker and frontend. The frontend is exposed
on port 8080 by default. `/health` is process liveness; `/ready` checks the database,
migrations, extensions, a current required dataset, a network version and scenario store.

A brand-new empty database is correctly `not_ready` until municipal data is registered.
The frontend still starts so an administrator can inspect and onboard it.

## Worker

Jobs are claimed with `FOR UPDATE SKIP LOCKED`; their state, real stage, attempts,
heartbeat, retry count, timestamps and errors are durable. The idempotency key combines
city, sorted dataset version UUIDs, job type, algorithm version and config hash.

The worker never executes a command supplied in a database job payload. Operators map
each declared stage to a trusted argv through an environment variable such as:

```text
CITYGAP_JOB_EVIDENCE_EXPORT_RENDER_PACKAGE_COMMAND=python -m approved.module
```

Every stage must be configured. A missing or failed command produces a durable failure,
is retried up to `max_retries`, and never creates fake progress. Stage processes must use
staging/transactions and only set a dataset analysis-ready after their final validation.

## Failure recovery

1. Inspect `/jobs/{id}`, `job_attempts`, `job_events` and structured logs by request ID.
2. Correct the source/configuration; never edit succeeded artifacts in place.
3. Requeue under an explicit new config hash when inputs or algorithm configuration changed.
4. Use the same idempotency inputs to retrieve an existing job instead of duplicating it.
5. Verify `/ready`, row-count reconciliation and the quality gate before analysis.

No production RPO/RTO is asserted. Municipal owners must set retention, escalation,
credential rotation and incident-response policy before handling private operational data.

## Field review and evidence

Planner-authorized field checks persist per scenario site. They retain checklist observations,
notes, bounded HTTPS photo references and structured location context; CITY GAP does not upload
or host photos. A hazard overlap remains a confirmation flag and never changes siting feasibility
automatically. Scenario status and field-check mutations write actor/request/before/after audit
evidence in the same transaction.

Evidence Package V2 compares exactly three selected plans and emits deterministic JSON plus a
print-friendly HTML review sheet. It includes cover, assumptions/data years, candidate coordinates,
A/B/C metrics, coordinate map, network caveat, planning/hazard context, field checks, provenance,
algorithm/config hash and limitations. `recommendation` and `preferred_scenario` remain null.

```bash
python -m analysis.scripts.export_scenario_comparison_evidence
```

The authenticated `運用管理` surface reads `/admin/snapshot` and the pilot-readiness endpoint. It
shows current cities, datasets/versions/quality state, capabilities, networks, jobs and users/roles.
It contains no fallback operational records and reports connection/auth failures explicitly.

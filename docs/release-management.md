# Release management

## Version set

A service release records application version, migration version, frontend asset
version, release status, notes and rollback version. API, worker and frontend must use a
compatible set. Dataset and algorithm versions are independent domain versions and must
not be replaced by the application release number.

Deployment must set `CITYGAP_APPLICATION_VERSION` and
`CITYGAP_APPLICATION_COMMIT` to the immutable artifact identity for both API and worker.
`service-health` exposes those runtime values. The compose default
`unversioned-development` is deliberately not a release claim, and the migration seed
with an all-zero commit remains a candidate placeholder until a deployment records a
real commit.

## Milestone policy

Use small, reviewable commits for domain/schema, workflow, field/offline, operations,
documentation and verification milestones. Never force-push `main`. CI must pass before
the release is marked deployed.

## Release gates

- Python formatting/lint and complete unit suite
- frontend typecheck, lint, component tests and production build
- fresh PostGIS migration plus integration and Organization A/B isolation tests
- no uncommitted generated artifacts or credentials
- municipal/public API surface tests
- backup record and rollback target
- OIDC and required environment validation
- public Pages privacy and read-only checks

## Roll forward and rollback

Migrations are forward-only. Prefer a corrective migration. Application rollback is
permitted only when the older binary is compatible with the migrated schema. Restore is
the last resort and requires a verified backup, isolated validation and an operator
record. Dataset promotion and Urban State current status are domain operations and must
not be silently rewound with a code deployment.

## Acceptance boundary

Automated tests establish technical readiness. Municipality validation is still needed
for roles, records retention, terminology, real field procedure, accessibility,
security operations and whether analysis limitations are understandable to staff.

# Stable municipal API contract

## General rules

- Stable endpoints are under `/api/v1`.
- Authentication is OIDC in pilot/production; organization membership and a product
  permission are required.
- JSON request models reject unknown fields.
- Tenant-owned IDs outside the selected organization return 404.
- Mutating lifecycle calls use expected/proposed state and return 409 on stale state.
- Lists use bounded limits; high-volume lists use an opaque cursor. Map features require
  bbox/tile delivery rather than unbounded JSON.
- Errors use `error.code`, `message`, `detail`, `request_id`, `remediation` and optional
  field errors.

## Resource groups

- identity and setup: `/me`, `/cities`, `/cities/{city}/onboarding`
- data: `/cities/{city}/datasets`, `/dataset-versions/{id}/status`, Urban States and
  `/cities/{city}/annual-updates`
- work: Findings, Investigations, saved spatial views, Reviews, Assignments and Decision
  Records
- compute: analysis definitions/runs, scenarios, immutable-result scenario clones and
  comparisons
- field: selected-site offline packages, sync/conflicts and attachments
- evidence: evidence centers, reports, artifacts and classified exports
- operations: jobs, health, metrics and immutable audit events
- organization operations: non-secret configuration and retention-policy records under
  `/organizations/current`; only Administrator mutates them

## Large and binary data

Attachments use a raw request body with `filename` and `data_classification` query
parameters. The API streams at most 25 MiB, calculates SHA-256, then registers metadata.
Downloads are authorized by tenant metadata and return `ETag`, `nosniff` and private
cache headers.

Public and municipal OpenAPI documents are generated from their actual runtime surface.
The public document cannot be used to discover blocked municipal operations.

Saved-view share tokens are opaque locators, not bearer authorization. Resolving
`/saved-views/{share_token}` still requires an authenticated, active membership in the
owning organization and `investigation:read`. Annual-update creation is idempotent for
the organization, state pair and algorithm version and returns the durable dataset-diff
Job plus an explicit statement that prior version references were not mutated.

Organization configuration accepts only an API allow-list of non-secret keys, rejects
secret-bearing nested keys, caps JSON values at 16 KiB and uses `expected_updated_at`
for optimistic concurrency. Retention endpoints record a reviewed policy; they do not
claim deletion enforcement or legal-hold support.

# Stable municipal API contract

## Spatial Evidence Pack

- `POST /api/v1/investigations/{id}/spatial-packs`: bounded geometry、bbox、source versionsを受け、`spatial_evidence_pack` jobをqueueする。
- `GET /api/v1/spatial-packs/{id}`: tenant-scoped lifecycleとhash/countを返す。
- `GET /api/v1/spatial-packs/{id}/manifest`: content-addressed artifact metadataを返す。
- `GET /api/v1/spatial-packs/{id}/objects?object_type=&limit=&offset=`: 最大200件のbounded page。bulk geometryはartifact URIを使う。
- `GET /api/v1/spatial-packs/{id}/sections`: transect概要とimmutable section artifactを返す。
- `POST /api/v1/spatial-packs/{id}/refresh`: source versionを固定した新Packをqueueする。既存ready Packを破壊しない。

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
- data: city Data Hub, `/cities/{city}/data-coverage`, `/cities/{city}/sources`,
  `/cities/{city}/source-timeline`, searchable `/datasets`, dataset detail/lineage,
  source discovery/metadata checks, `/cities/{city}/datasets`, explicit
  `/datasets/{id}/validate` and `/datasets/{id}/promote`, immutable-resource
  `/resources/{id}/reprocess`, `/cities/{city}/data-tasks`, Urban States and
  `/cities/{city}/annual-updates`
- work: Findings, Investigations, saved spatial views, Reviews, Assignments and Decision
  Records
- compute: analysis definitions/runs, scenarios, immutable-result scenario clones and
  comparisons
- field: selected-site offline packages, sync/conflicts and attachments
- field/source review: source feedback, feedback-derived field tasks and separately
  reviewed, expiring local overrides
- evidence: Evidence Center V2 detail/integrity, deterministic reports, artifacts,
  classified exports and public-transparency records
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

Coverage and source responses are tenant-scoped and dimensioned; they never emit a
single quality score or an automatically selected source. Dataset lineage is version
pinned and reports `automatic_latest_substitution: false`. Investigation detail exposes
only recorded entity sources and persisted canonical spatial links; missing linkage is
returned as missing rather than inferred from proximity.

`POST /sources/discover` queues official-catalog discovery and always returns
`automatic_acceptance: false`. Metadata-check endpoints are rate bounded and do not
download or promote a changed resource. Validation and promotion require an exact Dataset
and Version pair; promotion queues capability refresh only after persisted quality and
ingestion gates pass. Reprocessing requires an existing checksum-addressed raw blob and
records that the previous canonical output is retained.

Feedback endpoints never update official raw blobs or canonical records. Field-task and
override transitions use expected state. A new official canonical version may create an
override reconciliation candidate, but cannot delete or silently supersede the municipal
override. Evidence Center detail recalculates and verifies its manifest SHA-256. Public
transparency creation is rejected unless every referenced report/Evidence Center is
public-classified for the same tenant and city.

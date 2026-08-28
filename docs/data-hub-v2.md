# Data Hub V2: coverage and source lineage

Data Hub V2 exposes the municipal data fabric without turning source discovery into
automatic acceptance. It has seven operational views: Sources, Datasets, Coverage,
Quality, Updates, Licenses and Dependencies. City Home shows the current Urban State,
available/partial/gap counts and sources with an observed update. Analysis shows missing
requirements beside Findings.

## Truth boundaries

- Coverage is one status plus a temporal-alignment dimension and an explanation. There
  is no aggregate quality score.
- `partial` means the available records still carry a known coverage or interpretation
  limitation. A partial required source yields a constrained `BASE` effect; absence,
  unknown coverage or required review yields `UNAVAILABLE`.
- Source selection policy `open-data-source-preference@2` evaluates reference-state fit,
  official identity, licence, family gates and declared recency in that order. Newer data
  never wins automatically.
- P04 2020 and MHLW 2026 remain distinct sources. Count, coverage, coordinate difference,
  attribute richness and identity are persisted separately. Ambiguous identity evidence
  stays unresolved and the database rejects automatic truth selection.
- Timeline values retain the period actually published. Year-only and model periods are
  text such as `2022`, `2020 model` and `2025 release`; the platform does not invent dates.
- PLATEAU 2025 remains the primary spatial model. Its experimental surface-adjacency
  graph is not labelled as an official pedestrian network.
- P11 remains bus-stop points and is never converted into an invented GTFS feed.

## Pilot coverage

The verified pilot inventory is attached only after a real city row with code `26202`
or `14205` exists. Migration 023 does not register cities. A database trigger makes a
fresh install and an upgrade behave consistently while remaining idempotent.

The timeline keeps these distinct: census and J-SHIS 2020, Economic Census 2021, P11
2022, NPA 2023/2024 event dates in its 2024 annual file, PLATEAU 2025, official R6 trial
projection periods 2025/2050/2070, MHLW medical 2026-06-01 and MHLW care 2026-06-30.
No interpolation or best projection is selected.

## API

Authenticated tenant-scoped reads are available at:

- `GET /api/v1/cities/{city}/data-hub`
- `GET /api/v1/cities/{city}/data-coverage`
- `GET /api/v1/cities/{city}/sources`
- `GET /api/v1/cities/{city}/source-timeline`
- `GET /api/v1/datasets?city={city}&q={human-name}`
- `GET /api/v1/datasets/{dataset_id}`
- `GET /api/v1/datasets/{dataset_id}/lineage`
- `POST /api/v1/sources/discover`
- `POST /api/v1/sources/{source_id}/metadata-checks`
- `POST /api/v1/sources/metadata-checks/schedule`
- `POST /api/v1/datasets/{dataset_id}/validate`
- `POST /api/v1/datasets/{dataset_id}/promote`
- `POST /api/v1/resources/{resource_id}/reprocess`
- `POST /api/v1/resources/{resource_id}/quarantine`
- `GET /api/v1/cities/{city}/data-tasks`
- `PATCH /api/v1/data-tasks/{task_id}`
- `POST|GET /api/v1/cities/{city}/source-feedback`
- `POST /api/v1/source-feedback/{feedback_id}/field-task`
- `GET /api/v1/cities/{city}/open-data-field-tasks`
- `PATCH /api/v1/open-data-field-tasks/{task_id}`
- `POST|GET /api/v1/cities/{city}/local-overrides`
- `PATCH /api/v1/local-overrides/{override_id}/review`
- `GET /api/v1/evidence-centers/{evidence_id}`
- `POST|GET /api/v1/cities/{city}/public-transparency`

Dataset lineage returns the recorded raw blob → resource → adapter → canonical record →
spatial link → analysis boundary. It explicitly reports that no latest-version
substitution occurs. Search includes human dataset and source names within the active
Organization.

Investigation detail also returns `source_timeline` and `source_contributions`. The Case
map inspector shows only the source saved on the selected entity or a persisted canonical
spatial link. Missing links render as missing; proximity is not used to invent identity.

## Schema

Forward migration `023_city_data_coverage_lineage.sql` adds:

- exact-period city source timeline entries;
- dimension-by-dimension dataset comparisons;
- unresolved source conflicts with database-level automatic-selection guards;
- versioned analysis source-selection policies;
- dataset-family-specific quality-gate policies;
- dataset/source search documents;
- idempotent pilot metadata attachment after real city registration.

Existing immutable resources, dataset versions, promotion gates, tenant foreign keys,
quarantine states and public/internal classifications remain unchanged.

Forward migration `024_open_data_operations.sql` adds the human Data Manager queue,
rate-bounded metadata schedules, structured analysis-blocking quarantine events,
same-raw/new-adapter reprocessing records, exact open-data inputs for analysis runs and
source-feedback records. Update discovery never replaces a currently promoted version.
Provider failure is recorded while existing analysis remains version pinned.

Raw bytes use SHA-256 object keys; a changed URL cannot create a distinct identity for
identical bytes. Development uses a local store. Production can select an HTTPS
S3-compatible store with a local inspection cache; the remote object's length and
SHA-256 metadata are verified before use. Generic uploads reject traversal, unsafe ZIP
expansion, XML entity declarations, formula-like CSV/GTFS cells, invalid encoding,
malformed geometry and oversized single geometries.

Forward migration `025_open_data_review_evidence.sql` closes the municipal review loop.
Source feedback is stored with database-enforced `raw_mutation_permitted=false` and
`canonical_mutation_permitted=false`, then may create a tenant-scoped field verification
task. A reviewed local override always records actor, reason, evidence, effective date,
review status and expiry. When a later official canonical record has the same external
identity, the database creates a reconciliation candidate and never removes the override.

Evidence Center V2 hashes source, algorithm, validation, open-data lineage, report and
claim-boundary manifests. Deterministic report V2 emits the same artifact SHA-256 for the
same version-pinned content. Public transparency records accept only public-classified
reports/evidence and expose reviewed citations and limitations; raw field observations,
decisions and building-level estimated demographics remain outside the public boundary.

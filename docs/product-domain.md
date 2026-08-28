# Product domain and invariants

## Ownership hierarchy

`Organization → City → Urban State / Dataset Version → Analysis Run → Finding → Investigation → Review / Field Observation → Decision Record`

An Organization is the primary tenant. A City is owned by one Organization in the
current deployment model. Technical UUIDs are identifiers, not authorization grants.

## Core entities

- `Dataset` and `DatasetVersion`: source identity, year, classification, quality and
  service lifecycle.
- `UrbanState`: effective date plus an explicit set of dataset/network versions.
- `AnalysisDefinition` and `AnalysisRun`: typed input contract and reproducible run.
- `Finding`: a review candidate without automated severity or policy priority.
- `Investigation`: the durable case that links findings, spatial state and evidence.
- `ScenarioRun` and `ScenarioComparison`: alternatives and trade-offs, never a
  recommendation.
- `ReviewRequest`: explicit reviewer state and notes.
- `FieldOfflinePackage`, `FieldSyncOperation` and `FieldSyncConflict`: selected-site
  field work with idempotency and no silent last-write-wins.
- `EvidenceCenter` and `ReportRecord`: deterministic manifests and artifacts.
- `DecisionRecord`: human-authored outcome after reviewed evidence.

## Lifecycle rules

- Dataset service lifecycle:
  `registered → validating → validated → accepted → ingesting → analysis_ready → promoted`.
  A version cannot become promoted merely because it was uploaded.
- Urban State lifecycle:
  `draft → validated → current → superseded → archived`. Draft states cannot drive a
  service analysis.
- Investigation transitions are validated in the domain layer. Closed and archived
  investigations reject new observations.
- Review transitions are compare-and-set operations. A reviewed investigation moves to
  `decision_pending`; a requested change returns it to `open`.
- Field conflicts remain `unresolved` until a user selects server, client or merged
  state.

Database check constraints, composite tenant foreign keys and API transition validators
all enforce these rules. See `backend/citygap_platform/domain/municipal_service.py` and
`infra/migrations/015_municipal_service.sql`.

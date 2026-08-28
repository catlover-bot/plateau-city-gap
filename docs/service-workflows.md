# Municipal service workflows

## City and data onboarding

1. Administrator creates a City in `onboarding` state.
2. Data Manager registers a real source and version metadata.
3. Validation, acceptance and ingestion are recorded as distinct lifecycle events.
4. Quality and ingestion gates must pass before promotion.
5. Data Manager creates an Urban State from promoted versions, validates it and makes it
   current explicitly.
6. City capabilities remain `partial` or `unavailable` until evidence exists.

## Finding to decision

1. Analyst runs a catalogued analysis against a validated/current Urban State and named
   promoted versions.
2. Output may become a Finding; the analyst triages or dismisses it with a reason.
3. Analyst opens an Investigation and links the relevant findings and spatial view. A
   saved view retains viewport, visible entity types and Urban State; its share URL
   remains tenant-authenticated.
4. Planner requests and performs a review. Changed evidence creates a visible request
   for changes.
5. Planner or Field Staff downloads only a selected scenario site, records notes and
   checklist state offline, then synchronizes the idempotent operation.
6. Version mismatch returns an explicit conflict. A human selects server, client or a
   merged state.
7. Field attachments are stored as restricted by default and linked by tenant-owned
   metadata.
8. Planner records a Decision only after reviewed evidence. CITY GAP never creates the
   decision automatically.

## Annual update

Register the new source versions, complete external ingestion and quality gates,
promote them, and create and validate the new observed Urban State. Data Manager then
registers an annual update between two observed states. The service queues one
idempotent `dataset_diff` Job with both states, all attached Dataset Versions and an
algorithm version. Existing Investigations, Analysis Runs and Reports retain their old
Urban State references. After the worker persists real differences and any verified
recomputation, staff review observed change separately from expected scenario effect
and generate the deterministic annual report. Causality remains a municipal
evaluation.

Scenario clone copies an immutable computed result into a new draft with a parent
reference. It does not rerun or alter the algorithm, and all human field checks are
reset to unknown. Changed assumptions require a new versioned computation rather than
editing copied metrics.

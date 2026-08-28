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
3. Analyst opens an Investigation and links the relevant findings and spatial view.
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

Register the new source versions, validate and promote them, create the new observed
Urban State, run the same versioned analyses, compare old and new states, review
observed change separately from expected scenario effect, then generate the
deterministic annual report. Causality remains a municipal evaluation.

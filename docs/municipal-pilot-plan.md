# Municipal pilot plan

CITY GAP is prepared for a bounded proof of concept, not declared production. A pilot owner should first supply the municipality-approved PLATEAU/population/facility versions, an official network output if available, the OIDC tenant configuration, backup retention/destination, named role assignments and the review protocol for estimated building demographics.

The technical kickoff gate is `citygap readiness`: resolve every blocker and accept each named limitation. Run an ingestion rehearsal, scenario lifecycle review, field-check entry and Evidence Package V2 export in a non-production database. Run `pg_dump`/`pg_restore`, confirm audit events contain request IDs/actors without sensitive payloads, and record measured API p50/p95 on the pilot hardware.

During the pilot, treat 500 m scores as investigation aids, experimental surface-adjacency routes as field-check targets, hazards as confirmation flags, and building population as estimates. Scenario output never makes a policy recommendation. Dataset updates must pass differential inspection and the quality gate before dependent analysis is made ready.

Exit criteria are agreed workflow usefulness, traceable decisions, acceptable measured performance, completed field validation, a successful restore drill and municipality approval of data/publication boundaries. A `v0.x-pilot` release remains pre-production.

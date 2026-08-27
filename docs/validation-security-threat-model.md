# CITY GAP validation security threat model

Scope: dataset upload, ZIP/XML, OIDC, RBAC, scenario and validation mutation,
Evidence export, offline field sync, PostGIS, worker and tile API. The model uses
STRIDE and assumes authenticated municipal deployment is separate from the
read-only public Pages build.

| Surface | STRIDE threats | Required controls | Validation evidence |
|---|---|---|---|
| Upload | Spoofed source, tampering, repudiation, oversized denial of service | immutable URL/version/SHA-256; file and row limits; audit actor/request; staging transaction | wrong checksum, oversized input and partial-ingestion rollback tests |
| ZIP | Traversal, symlink/encrypted member, zip bomb, member-count DoS | normalized relative members only; reject links/encryption; compressed/expanded/member/ratio limits | traversal and compression-ratio fixtures |
| XML/CityGML | XXE/DTD disclosure, entity expansion DoS, malformed geometry | streaming parser; reject `DOCTYPE`/`ENTITY`; bounded archive; CRS and geometry validation | XXE, malformed XML and invalid geometry fixtures |
| OIDC | Token spoofing, replay, issuer/audience confusion | cryptographic verifier boundary; exact issuer/audience; no unverified decode; development headers forbidden in pilot/production | missing/invalid bearer and issuer/audience tests |
| RBAC/API | Broken authorization, IDOR, role escalation | viewer/analyst/planner/admin permissions; city/resource ownership in repository query; negative tests; mutation audit | cross-role validation API tests and PostGIS ownership checks |
| Scenario/validation | Parameter tampering, false status promotion, repudiation | immutable input versions; bounded rule sets; optimistic expected status; no automatic promotion; before/after audit | invalid network version, expected-status conflict and role tests |
| Evidence export | Manifest/path tampering, overwrite, information disclosure | same-directory resolution; SHA-256/size verification; versioned output; privacy scan; no actor/notes in public assets | corrupted artifact/manifest and public-leak tests |
| Offline field sync | Replay, stale update, conflict tampering, note disclosure | unique operation ID; package hash/expiry; base record version; explicit conflict resolution; bounded payload; authenticated actor | replay/idempotency, stale version, tamper and 64 KiB tests |
| PostGIS | SQL injection, IDOR, invalid geometry DoS, privilege elevation | parameterized SQL; bbox/pagination; SRID/check constraints; separate DB role; immutable migrations | integration transactions, malformed bbox/geometry and migration tests |
| Worker | Command injection, duplicate execution, worker death, DB outage | only operator-configured argv; `shell=False`; idempotency key; row lock; heartbeat; bounded retry; durable failure/audit | duplicate job, injected failure and stale/dead worker recovery in ephemeral PostGIS |
| Tile API | Unbounded extraction, cache confusion, cross-city disclosure | required dataset version; bounded z/x/y/layer; versioned cache key; RBAC deployment boundary | tile input/version/cache contract tests |

Residual risks requiring municipal ownership include identity-provider policy,
off-host backup access and retention, incident response, private-data
classification, field-device control, license review and penetration testing.
Neither a passing automated test nor this threat model is external validation.

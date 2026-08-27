# Pilot readiness

Run `citygap readiness --city 26202` against the intended PostGIS instance, or call authenticated `GET /admin/pilot-readiness/{city_id}` as an administrator. The result is one of:

- `READY`: every required and optional check passes.
- `READY_WITH_LIMITATIONS`: required checks pass and one or more explicit optional capabilities do not.
- `NOT_READY`: at least one required operational check fails.

Required checks cover live PostGIS/pgRouting queries, all checksummed migrations, current PLATEAU registration, registered population and facility inputs, passed dataset quality gate, network version, persisted scenario, safe OIDC mode, demographic coverage and explicit backup configuration. Evidence and GTFS are reported as limitations rather than fabricated. Each failure includes a remediation.

Readiness is deployment-specific. Repository CI success alone cannot produce `READY`: an intended pilot instance still needs real dataset registration, verified OIDC issuer/audience, backup destination/restore drill and municipality-specific review inputs.

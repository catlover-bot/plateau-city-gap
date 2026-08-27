# Municipal pilot deployment

Copy `.env.example` to an untracked `.env`, set strong database credentials and run `docker compose up --build`. Compose starts pinned PostGIS/pgRouting, applies checksummed migrations once, then starts API, PostgreSQL-backed worker and nginx frontend. The API healthcheck blocks frontend startup until the process responds; `/ready` separately verifies database state and required versions.

For a pilot, set `CITYGAP_ENVIRONMENT=pilot`, `CITYGAP_AUTH_MODE=oidc`, `CITYGAP_OIDC_ISSUER`, `CITYGAP_OIDC_AUDIENCE`, `CITYGAP_REQUIRED_CITY_ID`, and a backup destination/verified backup flag. Pilot/production startup rejects development authentication. The application deliberately requires a deployment-supplied signature-verifying OIDC adapter; only after that adapter is integration-tested may `CITYGAP_OIDC_VERIFIER_CONFIGURED=true` be set. Environment metadata alone is not authentication. Put TLS and token verification at the approved ingress/integration boundary; never expose Postgres publicly.

Use `citygap city init`, `dataset add`, `validate`, `ingest`, `analyze`, `scenario`, `export` for the controlled municipal import path. Keep raw archives and detailed Parquet outside the public frontend. Before users enter, run the readiness command and the restore drill in [backup-restore.md](backup-restore.md).

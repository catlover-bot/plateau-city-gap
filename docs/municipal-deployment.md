# Municipal deployment design

## Development and evaluation

`docker compose up --build` starts PostgreSQL/PostGIS/pgRouting, FastAPI and the existing static
frontend. `.env.example` contains development defaults only. Shared or internet-reachable
deployments must use secret-managed credentials, TLS and a restricted database network.

## Production boundary

- Run migrations through a versioned migration job rather than relying on the Docker
  first-initialization directory.
- Give API, ingestion and read-only analyst roles separate least-privilege DB accounts.
- Put authentication/authorization at the API gateway and record actor, request, scenario config,
  data version and result version in an append-only audit log.
- Back up the database and object-store raw packages separately; test point-in-time restoration.
- Retain source package checksum and license metadata even when old dataset versions are retired.
- Keep private municipal datasets outside Git and public container images. Define retention,
  disclosure and aggregation rules before importing them.
- Deploy on-premises or cloud without changing the open CityGML/GeoJSON/GeoPackage/CSV boundaries.
- Use vector tiles or pre-generated packages for wide-area map delivery; limit feature-detail APIs
  by role, bbox, pagination and rate.

CITY GAP currently uses only public/statistical data. Future building population is an aggregate
estimate, not personal data, but fine spatial estimates still require disclosure and misuse
review before municipal publication.

## Update runbook

1. Place a newly obtained package in protected raw storage and calculate SHA-256.
2. Create the full inventory and compare specification/ADE versions and theme counts.
3. Load it as a new non-current dataset version and run geometry/provenance checks.
4. Compare `gml:id` added/removed/changed sets and downstream conservation tests.
5. Promote the version atomically, invalidate tiles/caches and retain rollback access.
6. Record operator, source URL, publication date, validation result and deployment identifier.

## Roles

- Platform administrator: credentials, migration, backup and restore.
- Data steward: source acceptance, license, version promotion and quality exceptions.
- Analyst: read-only analysis and reproducible scenarios.
- Policy reviewer: approved scenario comparison; no raw DB mutation.
- Public viewer: curated layers and evidence only.

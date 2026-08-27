# PostGIS integration boundary

CITY GAP validates its database contract against a real PostgreSQL 16, PostGIS 3.5 and
pgRouting 4.0 service in `Municipal Pilot CI`. The service image is pinned by digest.

The integration job applies every numbered SQL file with the checksum-aware migration
runner and then exercises:

- `postgis` and `pgrouting` extension functions;
- all migrations and their recorded SHA-256 checksums;
- GiST indexes and foreign-key metadata;
- a bbox query through the HTTP repository;
- the 30 tracked Maizuru canonical scenario artifacts and their 90 sites;
- scenario comparison, guarded lifecycle changes and a field check;
- constraint failure and transaction rollback;
- strict dataset/network/context version matching;
- an actual Uvicorn process connected to the database; and
- `pg_dump` followed by restore into a fresh database.

This is an integration-contract test, not a full Maizuru database load. It uses the
tracked, real-analysis-derived scenario artifacts plus one deliberately small spatial
fixture. The fixture does not represent city feature totals, and CI must never be cited
as evidence that all 97,140 Maizuru CityGML features were loaded into PostGIS.

## Run locally

With PostgreSQL/PostGIS/pgRouting available:

```bash
export CITYGAP_DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/citygap'
export CITYGAP_TEST_DATABASE_URL="$CITYGAP_DATABASE_URL"
python -m backend.citygap_platform.database.migrations upgrade
pytest backend/integration -q
```

For a full municipal load, run the registered source inventory and validation first,
then use the existing city-independent loaders in this order:

```bash
python analysis/scripts/ingest_plateau_postgis.py --help
python analysis/scripts/load_building_demographics_postgis.py --help
python analysis/scripts/load_plateau_context_postgis.py --help
python analysis/scripts/load_scenarios_postgis.py --help
```

Record the exact archive checksum, explicit dataset UUID, network version and config
hash. A successful CI contract does not replace the full-load row-count reconciliation.

## Migration policy

Applied SQL files are immutable. `schema_migrations` stores each filename and SHA-256.
The runner stops if an already-applied file changes. Schema changes use a new numbered
file; operators back up before upgrade and verify readiness afterward.

## Backup/restore contract

`infra/scripts/verify_backup_restore.sh` creates a custom-format dump, restores it into
an isolated database, and compares scenario and extension counts. Production operators
must additionally test encrypted off-host retention and recovery timing under their own
municipal policy; CI does not establish a production RPO or RTO.

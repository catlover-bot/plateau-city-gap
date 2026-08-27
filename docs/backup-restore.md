# Backup and restore

Create custom-format dumps with a PostgreSQL client compatible with the server:

```bash
pg_dump --format=custom --no-owner --no-acl --dbname="$CITYGAP_DATABASE_URL" \
  --file=citygap.dump
createdb citygap_restore_check
pg_restore --exit-on-error --no-owner --no-acl \
  --dbname=citygap_restore_check citygap.dump
```

Verify extensions, `schema_migrations`, current dataset versions, scenario counts, jobs
and audit counts before promoting a restored database. Restore into an isolated database;
never overwrite a running pilot database for a test.

CI runs `infra/scripts/verify_backup_restore.sh` against its small PostGIS integration
database and checks two extensions and 30 canonical scenarios. This validates command
compatibility and relational restoration, not full-city recovery time. Pilot operations
still require encrypted off-host storage, access control, retention, periodic restore
drills and locally agreed RPO/RTO.

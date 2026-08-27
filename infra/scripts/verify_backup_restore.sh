#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${CITYGAP_SOURCE_DATABASE:?CITYGAP_SOURCE_DATABASE is required}"

restore_database="citygap_restore_ci"
dump_file="$(mktemp --suffix=.dump)"
cleanup() {
  dropdb --if-exists --force "${restore_database}" >/dev/null 2>&1 || true
  rm -f "${dump_file}"
}
trap cleanup EXIT

pg_dump --format=custom --no-owner --no-acl --dbname="${CITYGAP_SOURCE_DATABASE}" \
  --file="${dump_file}"
dropdb --if-exists --force "${restore_database}"
createdb "${restore_database}"
pg_restore --exit-on-error --no-owner --no-acl --dbname="${restore_database}" "${dump_file}"

source_scenarios="$(psql --dbname="${CITYGAP_SOURCE_DATABASE}" --tuples-only --no-align \
  --command="SELECT count(*) FROM scenario_runs")"
restored_scenarios="$(psql --dbname="${restore_database}" --tuples-only --no-align \
  --command="SELECT count(*) FROM scenario_runs")"
restored_extensions="$(psql --dbname="${restore_database}" --tuples-only --no-align \
  --command="SELECT count(*) FROM pg_extension WHERE extname IN ('postgis','pgrouting')")"

test "${source_scenarios}" = "${restored_scenarios}"
test "${restored_scenarios}" = "30"
test "${restored_extensions}" = "2"
echo "backup_restore_verified scenarios=${restored_scenarios} extensions=${restored_extensions}"

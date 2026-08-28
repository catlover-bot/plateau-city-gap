#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${CITYGAP_SOURCE_DATABASE:?CITYGAP_SOURCE_DATABASE is required}"

restore_database="citygap_restore_ci"
dump_file="$(mktemp --suffix=.dump)"
attachment_archive=""
attachment_restore_directory=""
cleanup() {
  dropdb --if-exists --force "${restore_database}" >/dev/null 2>&1 || true
  rm -f "${dump_file}"
  if [ -n "${attachment_archive}" ]; then
    rm -f "${attachment_archive}"
  fi
  if [ -n "${attachment_restore_directory}" ]; then
    rm -rf -- "${attachment_restore_directory}"
  fi
}
trap cleanup EXIT

pg_dump --format=custom --no-owner --no-acl --dbname="${CITYGAP_SOURCE_DATABASE}" \
  --file="${dump_file}"
dropdb --if-exists --force "${restore_database}"
createdb "${restore_database}"
pg_restore --exit-on-error --no-owner --no-acl --dbname="${restore_database}" "${dump_file}"

source_scenarios="$(psql --dbname="${CITYGAP_SOURCE_DATABASE}" --tuples-only --no-align \
  --command="SELECT count(*) FROM scenario_runs WHERE parent_scenario_run_id IS NULL")"
restored_scenarios="$(psql --dbname="${restore_database}" --tuples-only --no-align \
  --command="SELECT count(*) FROM scenario_runs WHERE parent_scenario_run_id IS NULL")"
restored_extensions="$(psql --dbname="${restore_database}" --tuples-only --no-align \
  --command="SELECT count(*) FROM pg_extension WHERE extname IN ('postgis','pgrouting')")"

test "${source_scenarios}" = "${restored_scenarios}"
test "${restored_scenarios}" = "30"
test "${restored_extensions}" = "2"

attachment_result="not_configured"
if [ -n "${CITYGAP_ATTACHMENT_DIRECTORY:-}" ]; then
  test -d "${CITYGAP_ATTACHMENT_DIRECTORY}"
  attachment_source_directory="$(realpath "${CITYGAP_ATTACHMENT_DIRECTORY}")"
  attachment_archive="$(mktemp --suffix=.attachments.tar)"
  attachment_restore_directory="$(mktemp -d)"
  source_attachment_manifest="$(
    cd "${attachment_source_directory}"
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  )"
  tar --create --file "${attachment_archive}" -C "${attachment_source_directory}" .
  tar --extract --no-same-owner --file "${attachment_archive}" \
    -C "${attachment_restore_directory}"
  restored_attachment_manifest="$(
    cd "${attachment_restore_directory}"
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  )"
  test "${source_attachment_manifest}" = "${restored_attachment_manifest}"
  attachment_count="$(find "${attachment_restore_directory}" -type f | wc -l)"
  attachment_result="verified:${attachment_count}"
fi

echo "backup_restore_verified scenarios=${restored_scenarios} extensions=${restored_extensions} attachments=${attachment_result}"

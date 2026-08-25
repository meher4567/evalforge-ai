#!/usr/bin/env bash
set -Eeuo pipefail

: "${EVALFORGE_RESTORE_DATABASE_URL:?Set EVALFORGE_RESTORE_DATABASE_URL to the target database}"
: "${EVALFORGE_CONFIRM_RESTORE:?Set EVALFORGE_CONFIRM_RESTORE=RESTORE to confirm replacement}"

if [[ "${EVALFORGE_CONFIRM_RESTORE}" != "RESTORE" ]]; then
  echo "Refusing restore: EVALFORGE_CONFIRM_RESTORE must equal RESTORE" >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/evalforge-backup.dump" >&2
  exit 2
fi

archive="$1"
checksum="${archive}.sha256"
if [[ ! -f "${archive}" || ! -f "${checksum}" ]]; then
  echo "Backup archive and matching .sha256 file are required" >&2
  exit 2
fi

sha256sum --check "${checksum}"
pg_restore --list "${archive}" >/dev/null
pg_restore \
  --dbname="${EVALFORGE_RESTORE_DATABASE_URL}" \
  --clean \
  --if-exists \
  --exit-on-error \
  --no-owner \
  --no-acl \
  "${archive}"

psql "${EVALFORGE_RESTORE_DATABASE_URL}" \
  --no-psqlrc \
  --set=ON_ERROR_STOP=1 \
  --tuples-only \
  --command="SELECT version_num FROM alembic_version;"
echo "Restore completed and schema revision was readable."

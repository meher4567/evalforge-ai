#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?Set DATABASE_URL to the PostgreSQL database to back up}"

backup_dir="${EVALFORGE_BACKUP_DIR:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${backup_dir}/evalforge-${timestamp}.dump"

umask 077
mkdir -p -- "${backup_dir}"
pg_dump \
  --dbname="${DATABASE_URL}" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="${archive}"
pg_restore --list "${archive}" >/dev/null
sha256sum "${archive}" >"${archive}.sha256"

echo "Backup verified: ${archive}"
echo "Checksum: ${archive}.sha256"

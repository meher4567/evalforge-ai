# Backup and disaster recovery runbook

## Objectives

- Recovery point objective (RPO): 24 hours for the starter deployment; 1 hour when scheduled
  backups are enabled on a paid database plan.
- Recovery time objective (RTO): 4 hours, including integrity checks and application smoke tests.
- PostgreSQL is the system of record. Redis/Celery state is disposable; queued work may be
  resubmitted after recovery because run items use leases and uniqueness constraints.

## Create and verify a backup

Install PostgreSQL client tools, then run:

```bash
DATABASE_URL='<source-postgres-url>' \
EVALFORGE_BACKUP_DIR='./backups' \
./scripts/backup_postgres.sh
```

The script creates a custom-format archive, validates its catalog with `pg_restore --list`, and
writes a SHA-256 checksum. Store the archive and checksum in encrypted object storage with a
retention policy; do not commit them.

## Restore drill

Always restore into an empty, disposable database first. The restore script deliberately requires
a different environment variable and an explicit confirmation value:

```bash
EVALFORGE_RESTORE_DATABASE_URL='<disposable-target-url>' \
EVALFORGE_CONFIRM_RESTORE=RESTORE \
./scripts/restore_postgres.sh ./backups/evalforge-YYYYMMDDTHHMMSSZ.dump
```

After restore, run `alembic current`, `/readyz`, an authenticated tenant-isolation smoke test, and
one deterministic evaluation/comparison. Confirm users, memberships, apps, runs, traces, gate
rules, and reports have expected counts. Record duration and evidence in the incident ticket.

## Regional or total service loss

1. Freeze writes or disable the API service.
2. Select the newest checksum-valid backup within the RPO.
3. Provision replacement PostgreSQL and Redis services in the target region.
4. Restore PostgreSQL and configure application secrets from the secret manager.
5. Run migrations only after confirming the restored Alembic revision.
6. Start one API instance, then workers; validate readiness, auth, isolation, and a demo run.
7. Restore normal scale, update DNS, monitor errors/latency, and communicate recovery.
8. Rotate credentials exposed during response and complete a blameless post-incident review.

Run a restore drill at least quarterly and before any material schema or hosting migration.

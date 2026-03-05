# Database Migration Runbook

## Goal
Safely apply schema changes with versioned migrations and tested rollback steps.

## Preconditions
- Backup taken (or Cloud SQL automated backup verified).
- `DATABASE_URL` points to target environment.
- App containers are on a release tag compatible with the migration.

## Standard flow

1. Check current revision:
   - `alembic current`
2. Preview pending revisions:
   - `alembic history --verbose`
3. Apply latest revision:
   - `alembic upgrade head`
4. Verify app smoke endpoints.

## Existing pre-Alembic database bootstrap

For old environments already at baseline schema:

1. Stamp baseline (no DDL applied):
   - `alembic stamp 20260301_000001`
2. Apply newer migrations:
   - `alembic upgrade head`

## Dry-run + rollback simulation (local/staging)

- `python migration_verify.py`

This runs:
- upgrade head
- downgrade base
- upgrade head

against a temporary local SQLite DB.

## Rollback procedure (staging/production)

1. Identify previous safe revision:
   - `alembic history --verbose`
2. Downgrade one step:
   - `alembic downgrade -1`
3. If needed, downgrade to specific revision:
   - `alembic downgrade <revision_id>`
4. Re-run smoke tests.

## Failure handling

- If migration fails mid-run:
  - stop app rollout
  - inspect DB state
  - restore from backup if required
  - fix migration script and re-test in staging first

## Safety notes

- Never run destructive SQL manually in production without backup confirmation.
- Keep migrations small and reversible whenever possible.

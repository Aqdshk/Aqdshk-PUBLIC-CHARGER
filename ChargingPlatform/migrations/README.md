# Alembic Migrations

This directory contains versioned database migrations for `ChargingPlatform`.

## Quick start

- Create migration:
  - `alembic revision --autogenerate -m "describe_change"`
- Apply latest migrations:
  - `alembic upgrade head`
- Roll back one step:
  - `alembic downgrade -1`

## Existing production/staging databases

For existing deployments created before Alembic:

1. Back up DB.
2. Ensure schema matches current baseline.
3. Stamp baseline revision without applying DDL:
   - `alembic stamp 20260301_000001`
4. Apply newer migrations normally:
   - `alembic upgrade head`

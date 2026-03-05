# Google Cloud Deployment Runbook (PUBLIC CHARGER RND)

## Target topology

- `api.<domain>` -> ChargingPlatform (FastAPI + OCPP control APIs)
- `cs.<domain>` -> CustomerService (chat/support APIs)
- `app.<domain>` -> AppEV web frontend (static)
- Cloud SQL MySQL (private access)
- OCPP websocket endpoint over TLS (`wss`) routed via HTTPS LB/reverse proxy

## Minimum production baseline

- ChargingPlatform service: 4 vCPU / 16 GB RAM
- CustomerService service: 2 vCPU / 8 GB RAM
- Cloud SQL MySQL: 4 vCPU / 16 GB RAM (HA recommended)
- Object storage + logging + alerting enabled

## Required environment variables

- Core security:
  - `JWT_SECRET_KEY`
  - `PAYMENT_CALLBACK_SECRET`
  - `CORS_ORIGINS`
  - `OCPP_REQUIRE_AUTH=1`
  - `OCPP_SHARED_TOKEN` or `OCPP_CHARGER_TOKENS`
- Payment gateways (env-only credentials):
  - `PAYMENT_BILLPLZ_API_KEY`, `PAYMENT_BILLPLZ_API_SECRET`
  - `PAYMENT_FIUU_API_KEY`, `PAYMENT_FIUU_API_SECRET`
  - `PAYMENT_TNG_API_KEY`, `PAYMENT_TNG_API_SECRET`
  - `PAYMENT_OCBC_API_KEY`, `PAYMENT_OCBC_API_SECRET`
- Service integrations:
  - `GEMINI_API_KEY`
  - SMTP credentials

## Pre-deploy checklist

1. Build images from latest commit.
2. Validate production env variables:
   - `python scripts/check_production_env.py`
3. Run migration verification locally:
   - `python ChargingPlatform/migration_verify.py`
4. Run payment security tests:
   - `python -m unittest ChargingPlatform/tests/test_payment_security.py -v`
5. Confirm staging smoke checks pass:
   - `python scripts/staging_smoke_check.py`
6. Confirm backups configured for Cloud SQL.

## Deployment sequence

1. Deploy/upgrade Cloud SQL and networking.
2. Apply DB migrations:
   - `alembic upgrade head` (from ChargingPlatform runtime environment)
3. Deploy ChargingPlatform.
4. Deploy CustomerService.
5. Deploy AppEV web static site.
6. Update load balancer routes and TLS cert bindings.
7. Run post-deploy smoke tests.

## Post-deploy smoke tests

- `GET /docs` for ChargingPlatform = 200
- `GET /health` for CustomerService = 200
- Admin login + analytics load
- Payment topup create + callback idempotency replay
- OCPP authenticated websocket connect from test charger

## Rollback

1. Roll back traffic to previous service revision.
2. If schema rollback required:
   - `alembic downgrade -1` (or pinned revision)
3. Restore Cloud SQL backup if data integrity issue.
4. Re-run smoke tests and keep war-room active.

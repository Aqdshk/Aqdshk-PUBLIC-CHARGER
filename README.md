# PlagSini EV — Public Charging Platform

End-to-end EV charging operator stack: 314+ live AION DC chargers, customer
mobile/web app (PWA), admin operations console, partner B2B API for terminal
vendors (TNG eWallet integration in progress), and a self-hosted observability
stack — all running on a single VPS behind Nginx + Let's Encrypt.

> **Production:** [`https://charger.czeros.tech`](https://charger.czeros.tech)
> **Status:** Operational, 314+ chargers connected via OCPP 1.6.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Project Layout (Monorepo)](#project-layout-monorepo)
3. [Tech Stack](#tech-stack)
4. [Service URLs](#service-urls)
5. [Screenshots](#screenshots)
6. [Quick Start (Local Dev)](#quick-start-local-dev)
7. [Production Deployment](#production-deployment)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Charger Firmware Updates (OTA)](#charger-firmware-updates-ota)
10. [Monitoring](#monitoring)
11. [Documentation Index](#documentation-index)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USERS                                             │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────────────────┐  │
│  │ EV Driver    │    │ Admin / Staff  │    │ Partner (TNG terminal etc.) │  │
│  │ (PWA / web)  │    │ (web)          │    │ (server-to-server REST)     │  │
│  └──────┬───────┘    └────────┬───────┘    └──────────────┬──────────────┘  │
│         │ HTTPS               │ HTTPS                     │ HTTPS           │
└─────────┼─────────────────────┼───────────────────────────┼─────────────────┘
          │                     │                           │
          ▼                     ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           NGINX  (charger.czeros.tech, port 80/443, TLS via Certbot)        │
│  /app/         → AppEV (Flutter web PWA)                                    │
│  /api/         → ChargingPlatform REST + admin dashboards                   │
│  /bot/         → CustomerService chatbot                                    │
│  /monitoring/  → Grafana                                                    │
│  /static/firmware/ → OCPP firmware .bin downloads                           │
└──┬────────────┬─────────────────────────┬────────────────────────────┬─────┘
   │            │                         │                            │
   ▼            ▼                         ▼                            ▼
┌────────┐  ┌──────────────────────┐  ┌────────────────┐  ┌────────────────────┐
│ AppEV  │  │ ChargingPlatform     │  │ CustomerService│  │ Grafana / Loki /   │
│Flutter │  │ - FastAPI (HTTP)     │  │ Telegram + web │  │ Promtail           │
│web PWA │  │ - OCPP 1.6 WS server │  │ chatbot        │  │ (logs + dashboards)│
│        │  │ - SQLAlchemy + MySQL │  │                │  │                    │
│        │  │ - Alembic migrations │  │                │  │                    │
└────────┘  └──────┬─────────┬─────┘  └────────────────┘  └────────────────────┘
                   │         │
        ┌──────────┘         └──────────┐
        ▼                               ▼
┌────────────────┐              ┌────────────────────────────┐
│ MySQL 8.0      │              │ OCPP WebSocket (port 9000) │
│ - Chargers     │              │       │                    │
│ - Sessions     │              │       │ ws://              │
│ - Users        │              │       ▼                    │
│ - Payments     │              │  ┌───────────────────────┐ │
│ - Migrations   │              │  │ 314+ AION DC Chargers │ │
└────────────────┘              │  │ (live OCPP 1.6 conn)  │ │
                                │  └───────────────────────┘ │
                                └────────────────────────────┘
```

### Component summary

| Service               | Purpose                                       | Stack                              |
|-----------------------|-----------------------------------------------|------------------------------------|
| **AppEV**             | Customer-facing app (find/start charge, pay)  | Flutter (web PWA, Android, iOS)    |
| **ChargingPlatform**  | REST API + OCPP 1.6 server + admin dashboards | FastAPI, Uvicorn, SQLAlchemy, ocpp |
| **CustomerService**   | Support chatbot                                | Python, Telegram Bot API           |
| **monitoring**        | Logs + dashboards                              | Grafana, Loki, Promtail            |
| **MySQL**             | Persistence                                    | MySQL 8.0                          |
| **Nginx**             | Reverse proxy, TLS, rate-limit, gzip          | Nginx + Certbot                    |
| **ESP-Charger-RND**   | ESP32 firmware research (separate concern)    | C++, PlatformIO                    |

---

## Project Layout (Monorepo)

```
PUBLIC-CHARGER-RND/
├── .github/workflows/        # CI/CD pipelines (test.yml, deploy.yml)
├── AppEV/                    # Flutter mobile/web app (PWA)
│   ├── lib/                  #   Dart sources (screens, widgets, services)
│   ├── web/                  #   Web entry (index.html, push-sw.js, manifest)
│   ├── android/, ios/        #   Native shells
│   └── Dockerfile            #   Nginx-served release build
├── ChargingPlatform/         # Python backend
│   ├── api.py                #   FastAPI app — REST endpoints + admin pages
│   ├── ocpp_server.py        #   OCPP 1.6 WebSocket server (charger comms)
│   ├── database.py           #   SQLAlchemy models
│   ├── payment_gateway.py    #   Pluggable gateways (Billplz/Fiuu/TNG/OCBC)
│   ├── ocpi/                 #   OCPI 2.2.1 CPO interface (locations/CDRs/etc.)
│   ├── templates/            #   Jinja2 admin dashboards
│   ├── static/firmware/      #   Charger OTA .bin files
│   ├── migrations/           #   Alembic schema versions
│   └── tests/                #   pytest suite
├── CustomerService/          # Telegram + web chatbot
├── monitoring/               # Grafana dashboards, Loki, Promtail configs
├── nginx/                    # Nginx site configs (dev + production)
├── ESP-Charger-RND/          # ESP32 firmware (charger-side, research)
├── docker-compose.yml        # Local dev stack
├── docker-compose.prod.yml   # Production stack (VPS)
└── .env.example              # All required env vars documented
```

**Why monorepo:**
- Solo developer + tight cross-service coupling (AppEV ↔ ChargingPlatform API contract changes hit both at once).
- Single `docker compose` brings the whole stack up.
- One CI/CD pipeline; one set of secrets.
- Atomic commits across services (no "AppEV PR landed before backend PR shipped" version-skew bugs).

---

## Tech Stack

**Backend (`ChargingPlatform/`)**
Python 3.11 · FastAPI · Uvicorn · SQLAlchemy 2 · Alembic · MySQL 8.0 · `ocpp` library (1.6) · python-jose (JWT) · cryptography (TNG signing) · aiofiles · Jinja2

**Frontend (`AppEV/`)**
Flutter (stable channel) · Dart · provider · shared_preferences · http · `flutter_local_notifications` · service worker for web push

**Infra**
Docker + Docker Compose · Nginx (TLS via Let's Encrypt / certbot) · GitHub Actions (CI/CD) · Telegram (deploy + alert notifications)

**Observability**
Grafana 10 · Loki 3 (log aggregation) · Promtail (log shipper)

---

## Service URLs

### Production
| URL | What |
|------|------|
| `https://charger.czeros.tech/`              | API root (also serves admin auth) |
| `https://charger.czeros.tech/app/`          | **AppEV PWA** (customer app) |
| `https://charger.czeros.tech/operations`    | Admin OCPP operations console |
| `https://charger.czeros.tech/chargers`      | Live charger status dashboard |
| `https://charger.czeros.tech/admin`         | Admin user management |
| `https://charger.czeros.tech/pay?charger=…` | Quick-pay landing (QR scan target) |
| `https://charger.czeros.tech/bot/`          | Customer service chatbot |
| `https://charger.czeros.tech/monitoring/`   | Grafana (logs + system overview) |
| `https://charger.czeros.tech/static/firmware/…` | Charger OTA .bin downloads |
| `ws://203.99.148.43:9000/`                  | OCPP 1.6 WebSocket (chargers) |

### Local dev
| URL | What |
|------|------|
| `http://localhost:8000`        | FastAPI backend |
| `http://localhost:3000/app/`   | AppEV web |
| `http://localhost:3001/`       | Grafana |
| `http://localhost:8001/`       | Customer service bot |
| `ws://localhost:9000/`         | OCPP server |

---

## Screenshots

> Screenshots below show real production UI. Replace placeholder links by
> uploading PNG/JPG to GitHub Issues (drag-and-drop, copy the resulting
> `https://user-images.githubusercontent.com/…` URL) or to a `docs/img/`
> directory in the repo.

### AppEV (customer PWA)

| Screen | Description |
|--------|-------------|
| Login / Register | Email + password auth, JWT-based session |
| Home (Explore) | Nearby stations, favourites, promotions |
| Maps | Geo view of all chargers with live online/offline |
| Scan | QR scanner → opens charger detail |
| Charger detail | Connector status, tariff, "Start" button |
| Live charging | Realtime kWh, power, duration during a session |
| History | Past charging sessions + receipts |
| Wallet / Top-up | Balance + top-up flow |
| Rewards | Loyalty points + redemption |
| Me / Profile | Account, vehicles, e-invoice profile |

Add screenshots:
```
docs/img/appev-home.png
docs/img/appev-maps.png
docs/img/appev-charging.png
docs/img/appev-wallet.png
```

### Charging Platform (admin)

| Screen | Description |
|--------|-------------|
| `/chargers` | Status dashboard — all chargers, live heartbeat, FW version |
| `/operations` | OCPP ops: RemoteStart/Stop, Reset, Update Firmware (single + bulk), GetConfiguration |
| `/sessions` | Charging session log + filters |
| `/metering` | Per-session voltage/current/power/kWh time-series |
| `/faults` | Charger fault log |
| `/admin` | User management |
| `/dashboard` | Top-level KPI dashboard |
| `/payment-settings` | Payment gateway config (Billplz/Fiuu/TNG/OCBC) |
| `/settings` | Per-charger settings (lights, names, heartbeat interval) |

Add screenshots:
```
docs/img/admin-chargers.png
docs/img/admin-operations.png
docs/img/admin-sessions.png
docs/img/admin-metering.png
```

### Monitoring (Grafana)

| Dashboard | What it shows |
|-----------|---------------|
| PlagSini EV — System Overview | API logs (live), security/auth events, Nginx 4xx/5xx |
| OCPP heartbeats / connection count | Charger fleet health over time |
| HTTP latency | API p50/p95/p99 |
| MySQL slow queries | Performance hotspots |

---

## Quick Start (Local Dev)

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Compose (Linux)
- ~4 GB free RAM
- Node + Flutter SDK (only if rebuilding AppEV locally)

### Setup
```bash
# 1. Clone
git clone https://github.com/Aqdshk/Aqdshk-PUBLIC-CHARGER.git
cd Aqdshk-PUBLIC-CHARGER

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET_KEY, MYSQL_*, ADMIN_*

# 3. Start the stack
docker compose up -d

# 4. Run migrations
docker compose exec charging-platform alembic upgrade head

# 5. Verify
curl http://localhost:8000/health        # → 200 OK
open http://localhost:3000/app/          # AppEV
open http://localhost:8000/admin         # Admin
```

### Common dev tasks
```bash
# Tail backend logs
docker compose logs -f charging-platform

# Run pytest
docker compose exec charging-platform pytest -q tests/

# Rebuild AppEV after Flutter code change
docker compose build --no-cache appev && docker compose up -d appev

# New Alembic migration
docker compose exec charging-platform alembic revision --autogenerate -m "describe change"
```

---

## Production Deployment

**Production runs on a single VPS** (`203.99.148.43`) with Docker Compose. The
`docker-compose.prod.yml` brings up:

- `plagsini-api`        — ChargingPlatform (port 8000 HTTP, 9000 WS)
- `plagsini-web`        — AppEV Flutter web (port 3000)
- `plagsini-mysql`      — MySQL (internal)
- `plagsini-bot`        — Customer service chatbot (port 8001)
- `loki`, `promtail`, `grafana` — observability (port 3001)
- `plagsini-certbot`    — Let's Encrypt cert auto-renewal
- `docker-socket-proxy` — read-only docker.sock for Promtail container discovery

Nginx (host-installed, not in compose) terminates TLS and reverse-proxies to
each service. Config lives in [`nginx/nginx-vps.conf`](nginx/nginx-vps.conf).

### Manual deploy (legacy fallback)
```bash
ssh root@203.99.148.43 -p 2222
cd /opt/plagsini-ev
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Preferred deploy: GitHub Actions
See [CI/CD Pipeline](#cicd-pipeline) below. Click "Run workflow" on the Actions
tab — no SSH needed.

---

## CI/CD Pipeline

Two GitHub Actions workflows live in [`.github/workflows/`](.github/workflows/).

### `test.yml` — Automated checks (every push + PR)

Runs in <2 min on every push to `main` and every pull request:

| Job | What it catches |
|-----|-----------------|
| Python — syntax + import + tests | Typos, broken imports, failing pytest |
| YAML — docker-compose + workflows | Compose config errors, malformed workflow YAML |
| Alembic — migrations consistent | Branching migration heads, broken migration scripts |

Real bugs caught so far:
- Unterminated docstring in `ocpi/models.py` (would have crashed `import api` on container restart)
- Forgotten `ChargerReview` import while pulling fresh schema
- Missing env-var declarations in `docker-compose.prod.yml`

### `deploy.yml` — Manual-trigger production deploy

Goes through:

```
Operator clicks "Run workflow" on GitHub Actions
         │
         ▼
1. Resolve commit SHA + commit message
2. Telegram: 🚀 Deploy started <SHA> by <actor>
3. Check CI status on this commit:
     - CI failed/cancelled/timed-out → ABORT, no deploy
     - CI still running              → ABORT, retry later
     - CI green                      → continue
     - force_deploy=true             → skip this check (emergency hotfix)
4. SSH to VPS using dedicated ed25519 key
5. git fetch + checkout + ff-only pull on /opt/plagsini-ev
6. docker cp updated .py/.html files into plagsini-api
7. docker restart plagsini-api  (or compose build for AppEV/Dockerfile changes)
8. Health check loop: curl /health for up to 30s, must hit 200
9. Telegram: ✅ Deploy SUCCESS <SHA> / ❌ Deploy FAILED <SHA> + link to run logs
```

Inputs:
- `ref` — branch or commit SHA (default `main`); use to deploy/rollback to a specific commit.
- `rebuild_appev` — force `docker compose build appev` (slower, ~3 min).
- `rebuild_api` — force charging-platform image rebuild (only when Dockerfile or requirements.txt changed).
- `force_deploy` — skip CI gate (emergency hotfix only).

### Required secrets (`Settings → Secrets and variables → Actions`)

| Secret | What it's for |
|--------|---------------|
| `VPS_HOST`            | `203.99.148.43`                                    |
| `VPS_PORT`            | `2222`                                             |
| `VPS_USER`            | `root`                                             |
| `VPS_SSH_KEY`         | ed25519 private key (public key on VPS `authorized_keys`) |
| `TELEGRAM_BOT_TOKEN`  | PlagSinibot token                                  |
| `TELEGRAM_CHAT_ID`    | Admin chat ID                                      |

### Rollback
Re-run `deploy.yml` with `ref = <known-good SHA>`. Same Telegram notifications,
same health-check gate. Typically takes ~30 seconds.

---

## Charger Firmware Updates (OTA)

Chargers (AION DC, OCPP 1.6) fetch firmware via OCPP `UpdateFirmware`:

```
1. Admin opens /operations → Bulk Update Firmware
2. Selects target chargers (only "online" ones get the command)
3. Provides firmware URI: http://203.99.148.43:8000/static/firmware/APP_…bin
4. Backend sends OCPP UpdateFirmware to each charger over WS
5. Charger reports back via FirmwareStatusNotification:
      Downloading → Downloaded → Installing → Installed
   (or InstallationFailed — spec-compliant chargers)
6. Smart polling on /operations watches firmware_events for live toasts
   per charger, stops the moment all targeted chargers report a terminal
   event, or hits a 30-minute hard cap (for units that silently fail).
```

A subset of older AION units (10 known SNs as of 2026-05) fail silently —
they download the .bin completely but reject it at signature/header check and
boot back to V2.0.02 without sending `InstallationFailed`. These need vendor
recovery via USB reflash. See `ChargingPlatform/docs/` for the evidence trail.

---

## Monitoring

Grafana lives at [`/monitoring/`](https://charger.czeros.tech/monitoring/) (admin auth required).

Data sources:
- **Loki** — log aggregation from all Docker containers via Promtail
- **MySQL** (optional) — slow-query / metrics dashboards

Provisioned dashboards live in [`monitoring/grafana/dashboards/`](monitoring/grafana/dashboards/).

Alerting:
- Telegram channel via `PlagSinibot` for deploy notifications + uptime alerts
- Optional UptimeRobot external monitor (recommended) for off-VPS uptime checks

---

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [`DOCUMENTATION_DEVELOPER.md`](DOCUMENTATION_DEVELOPER.md) | Long-form developer guide |
| [`DOCUMENTATION_USER_MANUAL.md`](DOCUMENTATION_USER_MANUAL.md) | End-user manual |
| [`DEPLOYMENT_GCP_RUNBOOK.md`](DEPLOYMENT_GCP_RUNBOOK.md) | Alternate GCP deploy notes |
| [`PRODUCTION_READINESS_CHECKLIST.md`](PRODUCTION_READINESS_CHECKLIST.md) | Go-live checklist |
| [`CHARGER_CONFIGURATION.md`](CHARGER_CONFIGURATION.md) | OCPP config keys per AION charger |
| [`DATABASE_SCHEMA.dbml`](DATABASE_SCHEMA.dbml) | DB schema (dbdiagram.io format) |
| [`ChargingPlatform/CHARGING_FLOW.md`](ChargingPlatform/CHARGING_FLOW.md) | Charging session state machine |
| [`ChargingPlatform/DB_MIGRATION_RUNBOOK.md`](ChargingPlatform/DB_MIGRATION_RUNBOOK.md) | Alembic ops |
| [`ChargingPlatform/OCPI_README.md`](ChargingPlatform/OCPI_README.md) | OCPI 2.2.1 endpoints |
| [`ChargingPlatform/docs/TNG_INTEGRATION_ANALYSIS.md`](ChargingPlatform/docs/TNG_INTEGRATION_ANALYSIS.md) | TNG eWallet integration design |

---

## License

Private — © PlagSini EV. All rights reserved.

## Maintainer

**Aqid Ishak** ([@Aqdshk](https://github.com/Aqdshk))

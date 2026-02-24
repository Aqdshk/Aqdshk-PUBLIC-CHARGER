# ChargingPlatform (FastAPI + OCPP)

Backend service for the EV charging platform. It provides:
- REST APIs for AppEV and admin tools
- Admin web dashboard (Jinja2 templates)
- OCPP 1.6 WebSocket server for charger communication

## Current Status

Recently updated and verified:
- Admin pages use improved responsive sizing and compact cards across laptop/monitor layouts
- Sidebar toggle behavior is fixed in admin templates (correct active state handling)
- Payment API support includes:
  - `GET /api/payment/methods`
  - `POST /api/payment/process`
- Shared stylesheet cache-busting version is updated in templates

## Core Features

- **Charger Monitoring**: online/offline status, availability, heartbeat
- **Charging Sessions**: start/stop, transactions, consumption
- **Metering**: voltage/current/power/kWh readings
- **Fault & Maintenance**: fault logs and maintenance records
- **Billing & Payments**: payment methods and charge payment processing
- **OCPP Operations**: remote start/stop, configuration, diagnostics, reset, and more

## Run Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start server:
```bash
python main.py
```

3. Access:
- Admin UI / API host: `http://localhost:8000`
- OCPP WebSocket: `ws://localhost:9000/{charge_point_id}`

## Key API Endpoints (AppEV related)

- `GET /api/chargers`
- `GET /api/sessions`
- `POST /api/charging/start`
- `POST /api/charging/stop`
- `GET /api/payment/methods`
- `POST /api/payment/process`

## Project Structure

- `main.py` - Entry point (HTTP + OCPP startup)
- `api.py` - REST API endpoints
- `ocpp_server.py` - OCPP message handlers and command calls
- `database.py` - SQLAlchemy models and DB setup
- `templates/` - Admin HTML pages
- `static/` - Shared CSS/JS assets



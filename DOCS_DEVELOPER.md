# 🛠️ PlagSini EV Charging — Developer Documentation

> **Version:** 1.0.0  
> **Last Updated:** February 2026  
> **Tech Stack:** Flutter · FastAPI · SQLAlchemy · MySQL · Docker · OCPP 1.6 · ESP32

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
   - 2.1 [High-Level Architecture](#21-high-level-architecture)
   - 2.2 [Service Communication](#22-service-communication)
   - 2.3 [Port Mapping](#23-port-mapping)
3. [Project Structure](#3-project-structure)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start (Docker)](#5-quick-start-docker)
6. [ChargingPlatform (Backend)](#6-chargingplatform-backend)
   - 6.1 [Overview](#61-overview)
   - 6.2 [File Structure](#62-file-structure)
   - 6.3 [Database Models](#63-database-models)
   - 6.4 [API Endpoints](#64-api-endpoints)
   - 6.5 [OCPP 1.6 Server](#65-ocpp-16-server)
   - 6.6 [Email / OTP Service](#66-email--otp-service)
   - 6.7 [Web Dashboard (Templates)](#67-web-dashboard-templates)
   - 6.8 [Configuration & Environment Variables](#68-configuration--environment-variables)
   - 6.9 [Running Locally (Without Docker)](#69-running-locally-without-docker)
7. [AppEV (Flutter Frontend)](#7-appev-flutter-frontend)
   - 7.1 [Overview](#71-overview)
   - 7.2 [File Structure](#72-file-structure)
   - 7.3 [State Management (Providers)](#73-state-management-providers)
   - 7.4 [API Service](#74-api-service)
   - 7.5 [Screens](#75-screens)
   - 7.6 [Widgets](#76-widgets)
   - 7.7 [Theming & Design System](#77-theming--design-system)
   - 7.8 [Running Locally](#78-running-locally)
   - 7.9 [Building for Production](#79-building-for-production)
8. [ESP-Charger-RND (Firmware)](#8-esp-charger-rnd-firmware)
   - 8.1 [Overview](#81-overview)
   - 8.2 [File Structure](#82-file-structure)
   - 8.3 [Hardware Configuration](#83-hardware-configuration)
   - 8.4 [Flashing Firmware](#84-flashing-firmware)
   - 8.5 [OTA Updates](#85-ota-updates)
9. [Docker Setup](#9-docker-setup)
   - 9.1 [Services](#91-services)
   - 9.2 [Docker Commands](#92-docker-commands)
   - 9.3 [Volumes & Data Persistence](#93-volumes--data-persistence)
10. [Database Schema](#10-database-schema)
11. [OCPP 1.6 Protocol Integration](#11-ocpp-16-protocol-integration)
12. [Authentication & Security](#12-authentication--security)
13. [Deployment Guide](#13-deployment-guide)
14. [Troubleshooting](#14-troubleshooting)
15. [Contributing](#15-contributing)

---

## 1. System Overview

PlagSini is a **full-stack EV charging platform** consisting of three main components:

| Component | Tech | Purpose |
|-----------|------|---------|
| **ChargingPlatform** | Python (FastAPI + WebSocket) | Backend API, OCPP 1.6 server, Admin web dashboard |
| **AppEV** | Flutter (Dart) | Mobile/web app for EV drivers |
| **ESP-Charger-RND** | C++ (Arduino/PlatformIO) | ESP32 firmware for physical charger hardware |

All backend services are containerized with **Docker** and orchestrated via **Docker Compose**.

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌──────────────┐     HTTP/REST      ┌──────────────────────┐     WebSocket     ┌──────────────┐
│   AppEV      │ ◄────────────────► │  ChargingPlatform    │ ◄────────────────► │ ESP32 Charger│
│  (Flutter)   │     Port 8000      │  (FastAPI + OCPP)    │   Port 9000       │  (Firmware)  │
│  Port 3000   │                    │                      │   OCPP 1.6        │              │
└──────────────┘                    │  ┌────────────────┐  │                    └──────────────┘
                                    │  │  MySQL 8.0     │  │
      ┌──────────────┐              │  │  Port 3306     │  │
      │  Admin Web   │ ◄──────────► │  └────────────────┘  │
      │  Dashboard   │  Port 8000   │                      │
      │  (Jinja2)    │  (same)      │  ┌────────────────┐  │
      └──────────────┘              │  │  SMTP Email    │  │
                                    │  │  (Gmail)       │  │
                                    │  └────────────────┘  │
                                    └──────────────────────┘
```

### 2.2 Service Communication

| From | To | Protocol | Port |
|------|----|----------|------|
| AppEV | ChargingPlatform API | HTTP REST | 8000 |
| Admin Browser | ChargingPlatform Web | HTTP | 8000 |
| ESP32 Charger | ChargingPlatform OCPP | WebSocket | 9000 |
| ChargingPlatform | MySQL | TCP | 3306 |
| ChargingPlatform | Gmail SMTP | TLS | 587 |

### 2.3 Port Mapping

| Service | Internal Port | External Port | Description |
|---------|--------------|---------------|-------------|
| MySQL | 3306 | 3307 | Database |
| ChargingPlatform (API) | 8000 | 8000 | REST API + Web Dashboard |
| ChargingPlatform (OCPP) | 9000 | 9000 | OCPP 1.6 WebSocket |
| AppEV (Nginx) | 80 | 3000 | Flutter Web App |

---

## 3. Project Structure

```
PUBLIC CHARGER RND/
├── AppEV/                          # Flutter mobile/web application
│   ├── lib/
│   │   ├── main.dart               # App entry point
│   │   ├── constants/
│   │   │   └── app_colors.dart     # Color palette & design tokens
│   │   ├── models/
│   │   │   └── user.dart           # Data models
│   │   ├── providers/
│   │   │   ├── auth_provider.dart   # Authentication state
│   │   │   ├── charger_provider.dart# Charger data state
│   │   │   ├── payment_provider.dart# Payment state
│   │   │   └── session_provider.dart# Charging session state
│   │   ├── screens/                 # 29 screen files
│   │   │   ├── splash_screen.dart   # Animated splash
│   │   │   ├── login_screen.dart    # Login & Register
│   │   │   ├── otp_verification_screen.dart
│   │   │   ├── home_screen.dart     # Dashboard + Navigation
│   │   │   ├── find_charger_screen.dart # Map view
│   │   │   ├── scan_screen.dart     # QR scanner
│   │   │   ├── rewards_screen.dart  # Points & rewards
│   │   │   ├── profile_screen.dart  # User profile
│   │   │   ├── live_charging_screen.dart # Active session
│   │   │   └── ...                  # 20 more screens
│   │   ├── services/
│   │   │   └── api_service.dart     # HTTP client
│   │   └── widgets/                 # 10 reusable widgets
│   ├── assets/
│   │   └── images/                  # Logo & static images
│   ├── android/                     # Android platform config
│   ├── web/                         # Web platform config
│   ├── pubspec.yaml                 # Flutter dependencies
│   ├── Dockerfile                   # Multi-stage: Flutter build → Nginx
│   └── nginx.conf                   # Nginx reverse proxy config
│
├── ChargingPlatform/                # Backend (Python)
│   ├── main.py                      # Entry point (starts FastAPI + OCPP)
│   ├── api.py                       # FastAPI routes (~2800 lines)
│   ├── ocpp_server.py               # OCPP 1.6 handler (~800 lines)
│   ├── database.py                  # SQLAlchemy models
│   ├── email_service.py             # SMTP email for OTP
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Python 3.11 slim
│   ├── init_mysql.sql               # Optional MySQL init script
│   ├── templates/                   # Jinja2 HTML templates (Admin dashboard)
│   │   ├── dashboard.html
│   │   ├── chargers.html
│   │   ├── sessions.html
│   │   ├── metering.html
│   │   ├── faults.html
│   │   ├── maintenance.html
│   │   ├── invoice.html
│   │   ├── operations.html          # OCPP Operations (SteVe-like)
│   │   ├── settings.html
│   │   └── admin.html
│   └── static/                      # CSS, JS, logo files
│
├── ESP-Charger-RND/                 # Embedded firmware (ESP32)
│   ├── platformio.ini               # PlatformIO config
│   └── src/
│       ├── main.cpp                 # Entry point
│       ├── EvseController.cpp/h     # EVSE control logic
│       ├── OcppClient.cpp/h         # OCPP 1.6 WebSocket client
│       ├── LcdDisplay.cpp/h         # LCD I2C display
│       ├── OtaManager.cpp/h         # OTA firmware updates
│       ├── OcppFirmwareUpdate.cpp/h # OCPP firmware update handler
│       └── HardwareConfig.h         # Pin definitions
│
├── docker-compose.yml               # Docker orchestration (3 services + MySQL)
├── Makefile                         # Convenience make commands
└── DOCS_USER_MANUAL.md              # User manual
```

---

## 4. Prerequisites

### For Docker Deployment (Recommended)

| Tool | Version | Purpose |
|------|---------|---------|
| **Docker** | ≥ 20.10 | Container runtime |
| **Docker Compose** | ≥ 2.0 | Multi-container orchestration |

### For Local Development

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | ≥ 3.11 | ChargingPlatform backend |
| **Flutter** | ≥ 3.0 | AppEV frontend |
| **MySQL** | ≥ 8.0 | Database (or use Docker for DB only) |
| **PlatformIO** | Latest | ESP32 firmware build |
| **Git** | Latest | Version control |

---

## 5. Quick Start (Docker)

### 1. Clone & Navigate

```bash
cd "C:\PUBLIC CHARGER RND"
```

### 2. Configure Environment

Edit `docker-compose.yml` to set your SMTP credentials (for email OTP):

```yaml
environment:
  - SMTP_HOST=smtp.gmail.com
  - SMTP_PORT=587
  - SMTP_EMAIL=your-email@gmail.com
  - SMTP_PASSWORD=your-app-password     # Gmail App Password (16 chars)
  - SMTP_FROM_NAME=PlagSini EV
```

> **Gmail App Password:** Go to [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords) and generate a 16-character app password.

### 3. Build & Start All Services

```bash
docker-compose up -d --build
```

### 4. Verify Services

```bash
docker-compose ps
```

| Service | URL | Status |
|---------|-----|--------|
| **AppEV (Web)** | http://localhost:3000 | Flutter web app |
| **ChargingPlatform API** | http://localhost:8000 | Admin dashboard + REST API |
| **OCPP WebSocket** | ws://localhost:9000 | Charger connections |
| **MySQL** | localhost:3307 | Database |

### 5. Default Admin Login

- **URL:** http://localhost:8000
- **Email:** `1@admin.com`
- **Password:** `1`

⚠️ **Change the default password immediately!**

### Useful Makefile Commands

```bash
make build     # Build all Docker images
make up        # Start all services
make down      # Stop all services
make logs      # View logs (all services)
make restart   # Restart all services
make clean     # Stop, remove volumes, prune
```

---

## 6. ChargingPlatform (Backend)

### 6.1 Overview

The ChargingPlatform is a **Python** application that serves as:
- **REST API Server** (FastAPI, port 8000) — Mobile app endpoints + admin web dashboard
- **OCPP 1.6 Server** (WebSocket, port 9000) — Physical charger communication
- **Admin Web Dashboard** (Jinja2 templates) — Browser-based management UI

### 6.2 File Structure

| File | Purpose |
|------|---------|
| `main.py` | Application entry point; starts FastAPI + OCPP servers |
| `api.py` | All FastAPI REST endpoints (~2800+ lines) |
| `ocpp_server.py` | OCPP 1.6 message handlers (ChargePoint class) |
| `database.py` | SQLAlchemy ORM models and database setup |
| `email_service.py` | SMTP email service for OTP verification |
| `requirements.txt` | Python package dependencies |
| `Dockerfile` | Docker build instructions |

### 6.3 Database Models

#### Users & Wallet

| Model | Table | Key Fields |
|-------|-------|------------|
| `User` | `users` | `id`, `email`, `phone`, `password_hash`, `name`, `is_active`, `is_verified`, `is_admin` |
| `Wallet` | `wallets` | `id`, `user_id`, `balance` (MYR), `points`, `currency` |
| `WalletTransaction` | `wallet_transactions` | `id`, `user_id`, `wallet_id`, `transaction_type`, `amount`, `points_amount`, `status` |
| `Vehicle` | `vehicles` | `id`, `user_id`, `plate_number`, `brand`, `model`, `battery_capacity_kwh`, `connector_type` |
| `OTPVerification` | `otp_verifications` | `id`, `email`, `otp_code`, `is_verified`, `attempts`, `expires_at` |

#### Charger & Sessions

| Model | Table | Key Fields |
|-------|-------|------------|
| `Charger` | `chargers` | `id`, `charge_point_id`, `vendor`, `model`, `firmware_version`, `status`, `availability`, `last_heartbeat` |
| `ChargingSession` | `charging_sessions` | `id`, `charger_id`, `transaction_id`, `start_time`, `stop_time`, `energy_consumed`, `status` |
| `Payment` | `payments` | `id`, `user_id`, `amount`, `payment_method`, `payment_status` |
| `Pricing` | `pricing` | `id`, `charger_id`, `price_per_kwh`, `price_per_minute` |
| `MeterValue` | `meter_values` | `id`, `charger_id`, `transaction_id`, `voltage`, `current`, `power`, `total_kwh` |
| `Fault` | `faults` | `id`, `charger_id`, `fault_type`, `message`, `cleared` |
| `MaintenanceRecord` | `maintenance_records` | `id`, `charger_id`, `maintenance_type`, `work_performed`, `status` |

#### Password Hashing

Passwords are hashed using `PBKDF2-HMAC-SHA256` with a random 16-byte hex salt:

```python
# Format: "<salt>$<hash>"
salt = secrets.token_hex(16)
hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
password_hash = f"{salt}${hash_obj.hex()}"
```

### 6.4 API Endpoints

#### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/send-otp` | Send OTP to email |
| `POST` | `/api/auth/verify-otp` | Verify OTP code |
| `POST` | `/api/users/register-with-otp` | Register user (requires verified OTP) |
| `POST` | `/api/users/login` | Login with email + password |

#### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/{id}` | Get user profile |
| `PUT` | `/api/users/{id}` | Update user profile |
| `GET` | `/api/users/{id}/wallet` | Get wallet balance & points |
| `POST` | `/api/users/{id}/wallet/topup` | Top up wallet |
| `GET` | `/api/users/{id}/wallet/transactions` | Transaction history |

#### Chargers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/chargers` | List all chargers with status |
| `GET` | `/api/chargers/{id}` | Get specific charger details |

#### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/active` | Get active sessions |
| `POST` | `/api/sessions/start` | Start a charging session |
| `POST` | `/api/sessions/stop` | Stop a charging session |

#### Metering

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/meter-values` | Get meter values |

#### Rewards

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/rewards/catalog` | Get available rewards |
| `POST` | `/api/users/{id}/rewards/redeem` | Redeem a reward |
| `GET` | `/api/users/{id}/rewards/history` | Get redemption history |

#### Vehicles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/{id}/vehicles` | List user vehicles |
| `POST` | `/api/users/{id}/vehicles` | Add a vehicle |
| `DELETE` | `/api/vehicles/{id}` | Remove a vehicle |

#### OCPP Operations (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ocpp/{charge_point_id}/remote-start` | Remote start transaction |
| `POST` | `/api/ocpp/{charge_point_id}/remote-stop` | Remote stop transaction |
| `POST` | `/api/ocpp/{charge_point_id}/change-availability` | Change availability |
| `POST` | `/api/ocpp/{charge_point_id}/change-configuration` | Change config key |
| `POST` | `/api/ocpp/{charge_point_id}/get-configuration` | Get config keys |
| `POST` | `/api/ocpp/{charge_point_id}/clear-cache` | Clear auth cache |
| `POST` | `/api/ocpp/{charge_point_id}/reset` | Reset charger |
| `POST` | `/api/ocpp/{charge_point_id}/unlock-connector` | Unlock connector |
| `POST` | `/api/ocpp/{charge_point_id}/get-diagnostics` | Request diagnostics |
| `POST` | `/api/ocpp/{charge_point_id}/update-firmware` | Push firmware update |
| `POST` | `/api/ocpp/{charge_point_id}/reserve-now` | Reserve a charger |
| `POST` | `/api/ocpp/{charge_point_id}/cancel-reservation` | Cancel reservation |
| `POST` | `/api/ocpp/{charge_point_id}/trigger-message` | Trigger OCPP message |
| `POST` | `/api/ocpp/{charge_point_id}/get-composite-schedule` | Get charge schedule |
| `POST` | `/api/ocpp/{charge_point_id}/set-charging-profile` | Set charge profile |
| `POST` | `/api/ocpp/{charge_point_id}/clear-charging-profile` | Clear charge profile |
| `POST` | `/api/ocpp/{charge_point_id}/data-transfer` | Custom data exchange |
| `POST` | `/api/ocpp/{charge_point_id}/get-local-list-version` | Get local list version |
| `POST` | `/api/ocpp/{charge_point_id}/send-local-list` | Update local list |

#### Admin Dashboard Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard (redirects to `/dashboard`) |
| `GET` | `/dashboard` | Main dashboard with charts |
| `GET` | `/chargers` | Charger management page |
| `GET` | `/sessions` | Sessions management page |
| `GET` | `/metering` | Metering data page |
| `GET` | `/faults` | Faults overview page |
| `GET` | `/maintenance` | Maintenance records page |
| `GET` | `/invoice` | Invoice management page |
| `GET` | `/operations` | OCPP Operations page (SteVe-like) |
| `GET` | `/settings` | System settings page |
| `GET` | `/admin` | Admin user management page |

### 6.5 OCPP 1.6 Server

The OCPP server runs on **WebSocket port 9000** and handles communication with physical chargers using the **OCPP 1.6 JSON** protocol.

#### Connection URL Format

```
ws://<server-ip>:9000/<charge-point-id>
```

Example: `ws://192.168.1.100:9000/CHARGER_001`

#### Supported OCPP 1.6 Messages (Server → Charger)

| Operation | Description |
|-----------|-------------|
| `RemoteStartTransaction` | Start charging remotely |
| `RemoteStopTransaction` | Stop charging remotely |
| `ChangeAvailability` | Set connector available/unavailable |
| `ChangeConfiguration` | Modify configuration key-value |
| `GetConfiguration` | Read configuration keys |
| `ClearCache` | Clear authorization cache |
| `Reset` | Soft/Hard reset |
| `UnlockConnector` | Unlock the charging connector |
| `GetDiagnostics` | Request diagnostic upload |
| `UpdateFirmware` | Trigger firmware download & install |
| `ReserveNow` | Reserve a connector for a user |
| `CancelReservation` | Cancel an existing reservation |
| `TriggerMessage` | Trigger charger to send a message |
| `GetCompositeSchedule` | Get combined charging schedule |
| `SetChargingProfile` | Set power limits/schedule |
| `ClearChargingProfile` | Remove a charging profile |
| `DataTransfer` | Vendor-specific data exchange |
| `GetLocalListVersion` | Check local auth list version |
| `SendLocalList` | Update the local authorization list |

#### Supported OCPP 1.6 Messages (Charger → Server)

| Message | Description |
|---------|-------------|
| `BootNotification` | Charger announces itself on connect |
| `Heartbeat` | Periodic keep-alive signal |
| `StatusNotification` | Charger/connector status change |
| `StartTransaction` | Charger reports session start |
| `StopTransaction` | Charger reports session end |
| `MeterValues` | Real-time energy/power measurements |
| `Authorize` | Authorization request for ID tag |
| `DataTransfer` | Custom data from charger |
| `DiagnosticsStatusNotification` | Diagnostics upload status |
| `FirmwareStatusNotification` | Firmware update progress |

#### Active ChargePoint Tracking

```python
# Global dictionary (in-memory)
active_charge_points: Dict[str, ChargePoint] = {}

# Access a connected charger
def get_active_charge_point(charge_point_id: str) -> Optional[ChargePoint]:
    return active_charge_points.get(charge_point_id)
```

### 6.6 Email / OTP Service

Located in `email_service.py`:

- **SMTP Provider:** Gmail (configurable)
- **OTP Length:** 6 digits
- **OTP Expiry:** 5 minutes
- **Max Attempts:** 5
- **Dev Mode:** If `SMTP_EMAIL` is not set, OTP is logged to console

**Flow:**
1. User submits email → `POST /api/auth/send-otp`
2. Server generates 6-digit OTP, stores in `otp_verifications` table
3. Server sends HTML email via SMTP (or logs to console in dev mode)
4. User enters OTP → `POST /api/auth/verify-otp`
5. Server validates OTP, marks as verified
6. User completes registration → `POST /api/users/register-with-otp` (requires `otp_id`)

### 6.7 Web Dashboard (Templates)

The admin dashboard is built with:
- **Jinja2** for HTML templates
- **Chart.js** for interactive charts
- **Vanilla CSS & JavaScript** (no framework)
- **Dark theme** with neon green (#00FF88) accents

Templates are located in `ChargingPlatform/templates/`.

### 6.8 Configuration & Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./charging_platform.db` | Database connection string |
| `ADMIN_EMAIL` | `1@admin.com` | Default admin email |
| `ADMIN_PASSWORD` | `1` | Default admin password |
| `ADMIN_NAME` | `Admin` | Default admin display name |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_EMAIL` | *(empty)* | Sender email address |
| `SMTP_PASSWORD` | *(empty)* | Sender email password / App Password |
| `SMTP_FROM_NAME` | `PlagSini EV` | Email sender display name |
| `PYTHONUNBUFFERED` | `1` | Python output buffering (Docker) |

### 6.9 Running Locally (Without Docker)

```bash
cd ChargingPlatform

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# (Optional) Set MySQL connection
set DATABASE_URL=mysql+pymysql://user:password@localhost:3306/charging_platform

# Run the server
python main.py
```

This starts:
- FastAPI on `http://0.0.0.0:8000`
- OCPP WebSocket on `ws://0.0.0.0:9000`

---

## 7. AppEV (Flutter Frontend)

### 7.1 Overview

AppEV is a **Flutter** application for EV drivers. It targets:
- **Android** (APK / Play Store)
- **iOS** (via Xcode)
- **Web** (deployed via Nginx in Docker)

**Design Philosophy:** Futuristic dark theme with neon green accents, glassmorphism effects, and smooth animations.

### 7.2 File Structure

```
AppEV/lib/
├── main.dart                        # App entry, theme, providers
├── constants/
│   └── app_colors.dart              # Design tokens (colors, gradients)
├── models/
│   └── user.dart                    # User data model
├── providers/
│   ├── auth_provider.dart           # Auth state (login, register, OTP)
│   ├── charger_provider.dart        # Charger list & status
│   ├── payment_provider.dart        # Payment processing
│   └── session_provider.dart        # Active charging session
├── screens/                         # 29 screens
│   ├── splash_screen.dart           # Animated EV splash
│   ├── login_screen.dart            # Login + Register tabs
│   ├── otp_verification_screen.dart # OTP input
│   ├── home_screen.dart             # Main navigation + Dashboard
│   ├── find_charger_screen.dart     # OpenStreetMap + markers
│   ├── scan_screen.dart             # QR code camera scanner
│   ├── rewards_screen.dart          # Points, catalog, redeem
│   ├── profile_screen.dart          # User profile & settings
│   ├── live_charging_screen.dart    # Real-time charging UI
│   ├── charger_detail_screen.dart   # Charger info + actions
│   ├── edit_profile_screen.dart     # Edit name, phone, etc.
│   ├── wallet_history_screen.dart   # Transaction history
│   ├── topup_screen.dart            # Wallet top-up
│   ├── payment_screen.dart          # Payment methods
│   ├── history_screen.dart          # Charging history
│   ├── my_vehicles_screen.dart      # Vehicle management
│   ├── favourite_stations_screen.dart
│   ├── invite_friends_screen.dart
│   ├── business_accounts_screen.dart
│   ├── subscriptions_screen.dart
│   ├── sign_in_methods_screen.dart
│   ├── einvoice_profile_screen.dart
│   ├── faq_screen.dart
│   ├── contact_us_screen.dart
│   ├── dcfc_chargers_screen.dart
│   ├── auto_charge_screen.dart
│   ├── offline_chargers_screen.dart
│   ├── new_sites_screen.dart
│   └── promotions_screen.dart
├── services/
│   └── api_service.dart             # All HTTP calls to backend
└── widgets/                         # 10 reusable widgets
    ├── header_widget.dart           # App header with logo
    ├── bottom_nav_bar.dart          # Bottom navigation
    ├── ev_illustration.dart         # Splash EV illustration
    ├── featured_station_card.dart   # Featured card widget
    ├── nearby_station_card.dart     # Nearby card widget
    ├── category_icon.dart           # Quick action icon
    └── ...
```

### 7.3 State Management (Providers)

The app uses the **Provider** package for state management:

| Provider | Responsibility |
|----------|---------------|
| `AuthProvider` | User authentication, login, register, OTP, profile |
| `ChargerProvider` | Fetching & caching charger list, status, availability |
| `PaymentProvider` | Payment method management, transaction processing |
| `SessionProvider` | Active charging session tracking, start/stop |

All providers are registered in `main.dart` via `MultiProvider`.

### 7.4 API Service

`api_service.dart` handles all HTTP communication with the backend.

**Base URL Logic:**
```dart
static String get baseUrl {
  // 1. Check for --dart-define override
  const envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  if (envUrl.isNotEmpty) return envUrl;

  // 2. Web: localhost
  if (kIsWeb) return 'http://localhost:8000/api';

  // 3. Android emulator: 10.0.2.2
  return 'http://10.0.2.2:8000/api';
}
```

**Override for physical device:**
```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000/api
```

### 7.5 Screens

#### Navigation Flow

```
SplashScreen → LoginScreen → HomeScreen (with BottomNavBar)
                                  ├── [0] DashboardScreen
                                  ├── [1] FindChargerScreen (Map)
                                  ├── [2] ScanScreen (QR Camera)
                                  ├── [3] RewardsScreen
                                  └── [4] ProfileScreen
```

#### Key Screens

| Screen | Description |
|--------|-------------|
| `SplashScreen` | Animated EV + charger illustration with PlagSini logo |
| `LoginScreen` | Tabbed Login/Register forms with email OTP flow |
| `HomeScreen` | Bottom nav with 5 tabs |
| `DashboardScreen` | Quick actions, active session banner, station lists |
| `FindChargerScreen` | OpenStreetMap with charger markers, real-time status |
| `ScanScreen` | Camera-based QR scanner + manual charger ID entry |
| `RewardsScreen` | Points balance, reward catalog, redemption, history |
| `LiveChargingScreen` | Real-time voltage, current, power, energy, cost |
| `ChargerDetailScreen` | Full charger info with start/stop actions |
| `ProfileScreen` | User info, wallet, vehicles, settings, logout |

### 7.6 Widgets

| Widget | File | Description |
|--------|------|-------------|
| `HeaderWidget` | `header_widget.dart` | App bar with PlagSini logo + notifications |
| `BottomNavBar` | `bottom_nav_bar.dart` | 5-tab bottom navigation |
| `EVIllustration` | `ev_illustration.dart` | Custom painted EV + charger for splash |
| `FeaturedStationCard` | `featured_station_card.dart` | Large station card |
| `NearbyStationCard` | `nearby_station_card.dart` | Compact station card |
| `CategoryIcon` | `category_icon.dart` | Quick action circular icon |

### 7.7 Theming & Design System

**Color Palette:**

| Token | Hex | Usage |
|-------|-----|-------|
| `primaryGreen` | `#00FF88` | Primary accent, CTAs, success |
| `mediumGreen` | `#00D977` | Secondary accent |
| `darkGreen` | `#00AA55` | Gradient end |
| `background` | `#0A0A1A` | App background |
| `surface` | `#0F1B2D` | Card surfaces |
| `cardBackground` | `#12192B` | Elevated cards |
| `textPrimary` | `#E8E8E8` | Primary text |
| `textSecondary` | `#CCCCCC` | Secondary text |
| `borderLight` | `#1E2D42` | Card borders |
| `error` | `#FF4444` | Error states |
| `warning` | `#FFA500` | Warning states |

**Design Language:**
- Dark, futuristic theme
- Glassmorphism (translucent cards with blur)
- Neon green accents
- Smooth Cupertino-style page transitions
- Material Design 3 components

### 7.8 Running Locally

#### Web

```bash
cd AppEV
flutter pub get
flutter run -d chrome
```

#### Android (Emulator)

```bash
cd AppEV
flutter pub get
flutter run -d android
```

#### Android (Physical Device)

```bash
cd AppEV
flutter run --dart-define=API_BASE_URL=http://<YOUR_PC_IP>:8000/api
```

#### iOS

```bash
cd AppEV
flutter pub get
flutter run -d ios
```

### 7.9 Building for Production

#### Web Build

```bash
flutter build web --release
```

Output: `AppEV/build/web/` → Deploy to any web server (Nginx, Apache, etc.)

#### Android APK

```bash
flutter build apk --release
```

Output: `AppEV/build/app/outputs/flutter-apk/app-release.apk`

#### Android App Bundle (Play Store)

```bash
flutter build appbundle --release
```

---

## 8. ESP-Charger-RND (Firmware)

### 8.1 Overview

The ESP32 firmware controls the physical EV charging hardware and communicates with the ChargingPlatform via **OCPP 1.6** over **WebSocket**.

### 8.2 File Structure

| File | Purpose |
|------|---------|
| `main.cpp` | Entry point, initializes all modules |
| `EvseController.cpp/h` | EVSE (Electric Vehicle Supply Equipment) control logic |
| `OcppClient.cpp/h` | OCPP 1.6 WebSocket client (MicroOcpp library) |
| `LcdDisplay.cpp/h` | I2C LCD display output |
| `OtaManager.cpp/h` | OTA (Over-The-Air) firmware updates via ArduinoOTA |
| `OcppFirmwareUpdate.cpp/h` | OCPP-triggered firmware updates (HTTP download) |
| `HardwareConfig.h` | GPIO pin definitions and hardware constants |

### 8.3 Hardware Configuration

- **Board:** ESP32 DevKitC (`esp32dev`)
- **Framework:** Arduino
- **Baud Rate:** 115200
- **Libraries:**
  - `MicroOcpp` — OCPP 1.6 client
  - `ArduinoJson` — JSON parsing
  - `WebSockets` — WebSocket communication
  - `LiquidCrystal_I2C` — LCD display

### 8.4 Flashing Firmware

#### Via USB Serial

```bash
cd ESP-Charger-RND
pio run -t upload -e esp32dev
```

#### Monitor Serial Output

```bash
pio device monitor -b 115200
```

### 8.5 OTA Updates

After initial USB flash and WiFi connection:

```bash
pio run -t upload -e esp32dev --upload-port <ESP32_IP_ADDRESS>
```

Example:
```bash
pio run -t upload -e esp32dev --upload-port 192.168.1.100
```

The ESP32 IP address is shown on the Serial Monitor after WiFi connects.

---

## 9. Docker Setup

### 9.1 Services

The `docker-compose.yml` defines 4 services:

| Service | Image | Container Name | Ports |
|---------|-------|----------------|-------|
| `mysql` | `mysql:8.0` | `charging-platform-mysql` | `3307:3306` |
| `charging-platform` | Custom (Python 3.11) | `charging-platform` | `8000:8000`, `9000:9000` |
| `appev` | Custom (Flutter → Nginx) | `appev` | `3000:80` |

### 9.2 Docker Commands

```bash
# Build all images
docker-compose build

# Start all services (detached)
docker-compose up -d

# Rebuild and start a specific service
docker-compose up -d --build charging-platform
docker-compose up -d --build appev

# View logs
docker-compose logs -f
docker-compose logs -f charging-platform

# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: deletes data)
docker-compose down -v

# Access MySQL CLI
docker exec -it charging-platform-mysql mysql -ucharging_user -pcharging_password charging_platform

# Access Python container shell
docker exec -it charging-platform bash

# Check container health
docker-compose ps
```

### 9.3 Volumes & Data Persistence

| Volume | Mount Point | Purpose |
|--------|-------------|---------|
| `mysql-data` | `/var/lib/mysql` | MySQL database files |
| `charging-platform-data` | `/app/data` | Application data |

> **Note:** `docker-compose down` preserves volumes. Use `docker-compose down -v` to delete all data.

---

## 10. Database Schema

### Entity Relationship Diagram

```
┌─────────┐     1:1      ┌──────────┐     1:N      ┌─────────────────────┐
│  users   │─────────────►│ wallets  │─────────────►│ wallet_transactions │
│          │              │          │              │                     │
│ id (PK)  │              │ id (PK)  │              │ id (PK)             │
│ email    │              │ user_id  │              │ user_id             │
│ phone    │              │ balance  │              │ wallet_id           │
│ name     │              │ points   │              │ transaction_type    │
│ is_admin │              │ currency │              │ amount              │
└─────────┘              └──────────┘              │ points_amount       │
     │                                              └─────────────────────┘
     │ 1:N
     ▼
┌──────────┐
│ vehicles │
│          │
│ id (PK)  │
│ user_id  │
│ plate_no │
│ brand    │
│ model    │
└──────────┘

┌──────────┐     1:N      ┌────────────────────┐
│ chargers │─────────────►│ charging_sessions   │
│          │              │                    │
│ id (PK)  │              │ id (PK)            │
│ cp_id    │              │ charger_id         │
│ vendor   │              │ transaction_id     │
│ model    │              │ start_time         │
│ status   │              │ stop_time          │
│ avail.   │              │ energy_consumed    │
└──────────┘              │ status             │
     │                    └────────────────────┘
     │ 1:N
     ├──────────────►  meter_values
     ├──────────────►  faults
     └──────────────►  maintenance_records

┌───────────────────┐
│ otp_verifications │
│                   │
│ id (PK)           │
│ email             │
│ otp_code          │
│ is_verified       │
│ attempts          │
│ expires_at        │
└───────────────────┘
```

### Database Connection

- **Docker (MySQL):** `mysql+pymysql://charging_user:charging_password@mysql:3306/charging_platform`
- **Local (SQLite fallback):** `sqlite:///./charging_platform.db`

---

## 11. OCPP 1.6 Protocol Integration

### Connection Flow

```
1. ESP32 connects via WebSocket → ws://<server>:9000/<charge_point_id>
2. Server accepts with subprotocol "ocpp1.6"
3. Charger sends BootNotification → Server responds Accepted + heartbeat interval
4. Charger sends periodic Heartbeat → Server responds with current time
5. On plug-in: Charger sends StatusNotification (Preparing)
6. On auth: Charger sends Authorize → Server responds Accepted/Rejected
7. Charging starts: StartTransaction → Server responds with transaction ID
8. During charging: MeterValues (voltage, current, power, energy)
9. Charging stops: StopTransaction → Server responds Accepted
10. Charger sends StatusNotification (Available)
```

### OCPP Operations Page

The admin dashboard includes a **SteVe-like** OCPP Operations page (`/operations`) that allows direct interaction with connected chargers:

1. Select a **Charge Point** from the dropdown (only online chargers shown)
2. Select an **Operation** from the available OCPP 1.6 operations
3. Fill in the operation-specific parameters
4. Click **"Execute"** to send the command
5. View the response in real-time

#### Change Configuration — Key Types

- **Predefined:** Dropdown with 38 standard OCPP 1.6 keys (e.g., `HeartbeatInterval`, `MeterValueSampleInterval`, `AuthorizeRemoteTxRequests`)
- **Custom:** Free-text input for vendor-specific keys

---

## 12. Authentication & Security

### User Authentication Flow

```
Register:
  Email → Send OTP → Verify OTP → Create Account (with otp_id) → Auto Login

Login:
  Email + Password → Validate → Return user data + token
```

### Password Security

- **Algorithm:** PBKDF2-HMAC-SHA256
- **Iterations:** 100,000
- **Salt:** 16-byte random hex (per user)
- **Storage:** `<salt>$<hash>` format

### OTP Security

- **Code Length:** 6 numeric digits
- **Expiry:** 5 minutes
- **Max Attempts:** 5 per OTP
- **Cooldown:** Rate limiting on send endpoint

### CORS

Currently configured with `allow_origins=["*"]` for development. **In production**, restrict to specific origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 13. Deployment Guide

### Production Checklist

- [ ] Change default admin password (`ADMIN_EMAIL`, `ADMIN_PASSWORD`)
- [ ] Configure SMTP credentials for email OTP
- [ ] Restrict CORS origins in `api.py`
- [ ] Set up SSL/TLS (HTTPS) for API and WebSocket
- [ ] Use strong MySQL passwords
- [ ] Configure firewall rules (ports 3000, 8000, 9000)
- [ ] Set up database backups
- [ ] Configure logging and monitoring
- [ ] Set up domain name and DNS
- [ ] Use Docker secrets for sensitive environment variables

### Cloud Deployment (Example: VPS)

```bash
# 1. SSH into your server
ssh user@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Clone the project
git clone <your-repo-url> /opt/plagsini
cd /opt/plagsini

# 4. Edit environment variables
nano docker-compose.yml

# 5. Build and start
docker-compose up -d --build

# 6. Verify
docker-compose ps
curl http://localhost:8000/api/chargers
```

### Reverse Proxy (Nginx Example)

```nginx
server {
    listen 80;
    server_name plagsini.com;

    # Flutter Web App
    location / {
        proxy_pass http://localhost:3000;
    }

    # API + Admin Dashboard
    location /api/ {
        proxy_pass http://localhost:8000;
    }

    # OCPP WebSocket
    location /ws/ {
        proxy_pass http://localhost:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 14. Troubleshooting

### Docker Issues

| Issue | Solution |
|-------|----------|
| Container won't start | `docker-compose logs <service>` to check errors |
| MySQL connection refused | Wait for MySQL healthcheck to pass (~30s after start) |
| Port already in use | Change port mapping in `docker-compose.yml` |
| Build fails | `docker-compose build --no-cache <service>` |
| Out of disk space | `docker system prune -a` (removes unused images) |

### Backend Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Database tables missing | Server auto-creates on startup via `init_db()` |
| SMTP authentication error | Use Gmail App Password, not regular password |
| OTP not sent | Check `SMTP_EMAIL` and `SMTP_PASSWORD` env vars. Check logs. |
| Charger not connecting | Verify WebSocket URL and port 9000 is accessible |

### Flutter Issues

| Issue | Solution |
|-------|----------|
| `pub get` fails | `flutter clean && flutter pub get` |
| API connection error (web) | Ensure backend is running on port 8000 |
| API connection error (Android) | Use `--dart-define=API_BASE_URL=http://<PC_IP>:8000/api` |
| Camera not working | Check AndroidManifest.xml for CAMERA permission |
| Map not loading | Check internet connection (OpenStreetMap requires network) |
| Build error on web | `flutter clean && flutter build web --release` |

### ESP32 Issues

| Issue | Solution |
|-------|----------|
| Upload fails | Check USB cable & COM port. Try different cable. |
| WiFi not connecting | Verify SSID and password in firmware config |
| OCPP connection fails | Check WebSocket URL, port 9000, and network |
| OTA upload fails | Ensure ESP32 and PC on same network. Check IP. |

### PowerShell-Specific

| Issue | Solution |
|-------|----------|
| `&&` not recognized | Use `;` instead of `&&` for command chaining in PowerShell |
| `curl` not working as expected | PowerShell aliases `curl` to `Invoke-WebRequest`. Use `curl.exe` or full `Invoke-WebRequest` syntax |

---

## 15. Contributing

### Code Style

- **Python:** Follow PEP 8. Use type hints.
- **Dart/Flutter:** Follow `flutter_lints` rules. Use `const` constructors where possible.
- **C++:** Follow Arduino conventions. Comment hardware-specific code.

### Branching Strategy

```
main        ← Production-ready code
├── develop ← Integration branch
│   ├── feature/xxx ← New features
│   ├── bugfix/xxx  ← Bug fixes
│   └── hotfix/xxx  ← Critical fixes
```

### Adding a New API Endpoint

1. Define the Pydantic model in `api.py`
2. Add the FastAPI route in `api.py`
3. If new DB table needed, add model in `database.py`
4. Add corresponding method in `AppEV/lib/services/api_service.dart`
5. Update the relevant Provider
6. Update the UI screen

### Adding a New Flutter Screen

1. Create `lib/screens/my_new_screen.dart`
2. Add navigation from the relevant parent screen
3. If it needs API data, add method to `api_service.dart`
4. If it needs state, update the relevant Provider
5. Follow the existing theming patterns (`AppColors`, etc.)

---

*© 2026 PlagSini EV Charging Platform — Developer Documentation*

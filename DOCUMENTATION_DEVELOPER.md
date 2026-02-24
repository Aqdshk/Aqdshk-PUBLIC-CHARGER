# 🛠️ PlagSini EV Charging Platform — Developer Documentation

> **Version:** 1.0.0  
> **Last Updated:** February 2026  
> **Author:** PlagSini Dev Team

---

## Recent Implementation Updates (Feb 2026)

- Admin web templates were refined for better responsive behavior across laptop and large monitor breakpoints.
- Shared admin card/grid sizing is now more compact using fluid CSS sizing.
- Sidebar toggle logic was aligned with the correct CSS class state in admin pages.
- `ChargingPlatform/api.py` includes `GET /api/payment/methods` and `POST /api/payment/process`.
- `AppEV/lib/services/api_service.dart` transaction parsing now accepts both list and wrapped responses.
- `AppEV/lib/screens/live_charging_screen.dart` uses a stored provider reference in `dispose()` to avoid unsafe context usage.
- The profile/login prompt illustration asset (`assets/ev_city_night.jpg`) was verified in code and manifest.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Prerequisites](#4-prerequisites)
5. [Environment Setup](#5-environment-setup)
   - 5.1 [Docker Compose (Recommended)](#51-docker-compose-recommended)
   - 5.2 [Manual Setup](#52-manual-setup)
6. [Backend — ChargingPlatform](#6-backend--chargingplatform)
   - 6.1 [Architecture Overview](#61-architecture-overview)
   - 6.2 [Database Models](#62-database-models)
   - 6.3 [REST API Endpoints](#63-rest-api-endpoints)
   - 6.4 [OCPP 1.6 WebSocket Server](#64-ocpp-16-websocket-server)
   - 6.5 [Email Service (OTP)](#65-email-service-otp)
   - 6.6 [Admin Web Templates](#66-admin-web-templates)
7. [Frontend — AppEV (Flutter)](#7-frontend--appev-flutter)
   - 7.1 [Architecture Overview](#71-architecture-overview)
   - 7.2 [State Management](#72-state-management)
   - 7.3 [Screens & Navigation](#73-screens--navigation)
   - 7.4 [API Service](#74-api-service)
   - 7.5 [Theme & Design System](#75-theme--design-system)
   - 7.6 [Building for Different Platforms](#76-building-for-different-platforms)
8. [ESP32 Charger Firmware](#8-esp32-charger-firmware)
   - 8.1 [Hardware Requirements](#81-hardware-requirements)
   - 8.2 [Firmware Architecture](#82-firmware-architecture)
   - 8.3 [Building & Flashing](#83-building--flashing)
   - 8.4 [OTA Updates](#84-ota-updates)
9. [Docker Deployment](#9-docker-deployment)
   - 9.1 [Services Overview](#91-services-overview)
   - 9.2 [Docker Compose Configuration](#92-docker-compose-configuration)
   - 9.3 [Building & Running](#93-building--running)
   - 9.4 [Volume Management](#94-volume-management)
10. [API Reference](#10-api-reference)
    - 10.1 [Authentication APIs](#101-authentication-apis)
    - 10.2 [Charger APIs](#102-charger-apis)
    - 10.3 [Charging Session APIs](#103-charging-session-apis)
    - 10.4 [OCPP Operation APIs](#104-ocpp-operation-apis)
    - 10.5 [User & Wallet APIs](#105-user--wallet-apis)
    - 10.6 [Rewards APIs](#106-rewards-apis)
    - 10.7 [Admin APIs](#107-admin-apis)
    - 10.8 [Maintenance APIs](#108-maintenance-apis)
    - 10.9 [Invoice APIs](#109-invoice-apis)
11. [Configuration & Environment Variables](#11-configuration--environment-variables)
12. [Testing](#12-testing)
13. [Common Development Tasks](#13-common-development-tasks)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        PlagSini Platform                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    HTTP/REST     ┌────────────────────────┐       │
│  │  AppEV   │ ◄──────────────► │   ChargingPlatform     │       │
│  │ (Flutter) │    Port 8000     │      (FastAPI)         │       │
│  │  :3000   │                  │                        │       │
│  └──────────┘                  │  ┌──────────────────┐  │       │
│                                │  │  OCPP WebSocket  │  │       │
│  ┌──────────┐   OCPP 1.6 WS   │  │    Server :9000  │  │       │
│  │  ESP32   │ ◄──────────────► │  └──────────────────┘  │       │
│  │ Charger  │    Port 9000     │                        │       │
│  └──────────┘                  │  ┌──────────────────┐  │       │
│                                │  │  Admin Web UI    │  │       │
│  ┌──────────┐                  │  │  (Jinja2 HTML)   │  │       │
│  │  Admin   │ ◄──────────────► │  └──────────────────┘  │       │
│  │ Browser  │    Port 8000     │                        │       │
│  └──────────┘                  └───────────┬────────────┘       │
│                                            │                     │
│                                ┌───────────▼────────────┐       │
│                                │      MySQL 8.0         │       │
│                                │       :3307             │       │
│                                └────────────────────────┘       │
│                                                                  │
│                                ┌────────────────────────┐       │
│                                │    Gmail SMTP           │       │
│                                │  (OTP Email Service)    │       │
│                                └────────────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **EV Driver** uses **AppEV** (Flutter web/mobile) to find chargers, scan QR, start/stop charging.
2. **AppEV** communicates with **ChargingPlatform** via REST API (port 8000).
3. **ChargingPlatform** sends OCPP 1.6 commands (RemoteStartTransaction, etc.) to the **ESP32 Charger** via WebSocket (port 9000).
4. **ESP32 Charger** sends real-time data (MeterValues, StatusNotification, Heartbeat) back to **ChargingPlatform** via OCPP WebSocket.
5. **Admin** manages the platform through the **Web Dashboard** (served by FastAPI on port 8000).
6. **Email OTP** is sent via **Gmail SMTP** during user registration.

---

## 2. Technology Stack

### Backend (ChargingPlatform)
| Component | Technology | Version |
|-----------|-----------|---------|
| Web Framework | FastAPI | ≥ 0.104.1 |
| ASGI Server | Uvicorn | ≥ 0.24.0 |
| WebSocket | websockets | ≥ 12.0 |
| OCPP Library | ocpp (Python) | ≥ 0.19.0 |
| ORM | SQLAlchemy | ≥ 2.0.23 |
| Validation | Pydantic | ≥ 2.5.0 |
| Database | MySQL 8.0 | (via Docker) |
| DB Driver | PyMySQL | ≥ 1.1.0 |
| Template Engine | Jinja2 | ≥ 3.1.2 |
| Email | smtplib (stdlib) | Python 3.11 |

### Frontend (AppEV)
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | Flutter | SDK ≥ 3.0.0 |
| State Management | Provider | ^6.1.1 |
| HTTP Client | http | ^1.1.0 |
| Local Storage | shared_preferences | ^2.2.2 |
| Maps | flutter_map (OpenStreetMap) | ^6.1.0 |
| Geolocation | geolocator | ^10.1.0 |
| QR Scanner | mobile_scanner | ^6.0.2 |
| Date Formatting | intl | ^0.20.2 |
| Coordinates | latlong2 | ^0.9.1 |

### Firmware (ESP-Charger-RND)
| Component | Technology | Version |
|-----------|-----------|---------|
| Platform | ESP32 (esp32dev) | Espressif32 |
| Framework | Arduino | via PlatformIO |
| OCPP Client | MicroOcpp | ^1.0.0 |
| WebSocket | WebSockets (links2004) | latest |
| JSON | ArduinoJson | ^6 |
| LCD Display | LiquidCrystal_I2C | ^1.1.2 |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containerization | Docker + Docker Compose |
| Web Server (AppEV) | Nginx Alpine |
| Database | MySQL 8.0 |
| SMTP | Gmail (App Password) |

---

## 3. Project Structure

```
PUBLIC CHARGER RND/
├── docker-compose.yml              # Docker orchestration
├── Makefile                        # Build shortcuts
│
├── ChargingPlatform/               # Backend (Python/FastAPI)
│   ├── Dockerfile                  # Python 3.11 slim image
│   ├── requirements.txt            # Python dependencies
│   ├── main.py                     # Entry point (starts FastAPI + OCPP WS)
│   ├── api.py                      # All REST API endpoints (~2800 lines)
│   ├── ocpp_server.py              # OCPP 1.6 ChargePoint handler (~860 lines)
│   ├── database.py                 # SQLAlchemy models & DB setup
│   ├── email_service.py            # OTP email via Gmail SMTP
│   ├── create_tables.py            # Manual DB table creation script
│   ├── init_mysql.sql              # MySQL initialization SQL
│   ├── static/                     # Static assets (CSS, JS, logos)
│   │   ├── styles.css
│   │   ├── main.js
│   │   ├── logo.png
│   │   └── PLAGSINI LOGO.png
│   └── templates/                  # Jinja2 HTML templates (Admin UI)
│       ├── dashboard.html
│       ├── chargers.html
│       ├── sessions.html
│       ├── metering.html
│       ├── faults.html
│       ├── maintenance.html
│       ├── invoice.html
│       ├── operations.html         # OCPP 1.6 Operations (SteVe-like)
│       ├── admin.html
│       └── settings.html
│
├── AppEV/                          # Frontend (Flutter)
│   ├── Dockerfile                  # Multi-stage: Flutter build → Nginx
│   ├── pubspec.yaml                # Flutter dependencies
│   ├── nginx.conf                  # Nginx config for web deployment
│   ├── android/                    # Android platform files
│   │   └── app/src/main/
│   │       └── AndroidManifest.xml # Camera permission configured
│   ├── web/                        # Web platform files
│   ├── assets/
│   │   ├── images/
│   │   │   ├── logo.png
│   │   │   └── PLAGSINI LOGO.png
│   │   ├── icons/
│   │   └── fonts/
│   └── lib/
│       ├── main.dart               # App entry point & theme config
│       ├── constants/
│       │   └── app_colors.dart     # Design system colors
│       ├── models/
│       │   └── user.dart           # User data model
│       ├── providers/              # State management (Provider pattern)
│       │   ├── auth_provider.dart   # Authentication state
│       │   ├── charger_provider.dart # Charger data state
│       │   ├── session_provider.dart # Charging session state
│       │   └── payment_provider.dart # Payment state
│       ├── services/
│       │   └── api_service.dart    # HTTP API client (~635 lines)
│       ├── screens/                # All app screens (29 files)
│       │   ├── splash_screen.dart  # Animated splash with car/station
│       │   ├── login_screen.dart   # Login + Registration
│       │   ├── otp_verification_screen.dart  # Email OTP input
│       │   ├── home_screen.dart    # Main home + Dashboard
│       │   ├── find_charger_screen.dart # Map view
│       │   ├── scan_screen.dart    # QR code scanner
│       │   ├── rewards_screen.dart # Rewards + History
│       │   ├── profile_screen.dart # User profile
│       │   ├── live_charging_screen.dart # Active session view
│       │   ├── charger_detail_screen.dart
│       │   ├── wallet_history_screen.dart
│       │   ├── topup_screen.dart
│       │   ├── history_screen.dart
│       │   ├── edit_profile_screen.dart
│       │   ├── my_vehicles_screen.dart
│       │   ├── payment_screen.dart
│       │   ├── ... (and more)
│       │   └── contact_us_screen.dart
│       └── widgets/                # Reusable UI components (10 files)
│           ├── header_widget.dart
│           ├── bottom_nav_bar.dart
│           ├── ev_illustration.dart # Custom painted EV animation
│           ├── featured_station_card.dart
│           ├── nearby_station_card.dart
│           ├── category_icon.dart
│           └── ...
│
└── ESP-Charger-RND/                # Charger Firmware (ESP32)
    ├── platformio.ini              # PlatformIO config
    └── src/
        ├── main.cpp                # Entry point
        ├── HardwareConfig.h        # Pin definitions & constants
        ├── EvseController.cpp/h    # EVSE state machine & relay control
        ├── OcppClient.cpp/h        # OCPP 1.6 client (MicroOcpp)
        ├── OcppFirmwareUpdate.cpp/h # OCPP firmware update handler
        ├── LcdDisplay.cpp/h        # I2C LCD display driver
        └── OtaManager.cpp/h        # Arduino OTA update manager
```

---

## 4. Prerequisites

### For Docker Deployment (Recommended)
- **Docker Desktop** ≥ 4.0 (Windows/macOS) or Docker Engine (Linux)
- **Docker Compose** v2+
- **Git** (to clone the repository)

### For Local Development
- **Python** 3.11+
- **Flutter SDK** ≥ 3.0.0
- **MySQL** 8.0 (or use Docker for just the database)
- **PlatformIO** (for ESP32 firmware development)
- **Android Studio** or **VS Code** with Flutter/Dart extensions

---

## 5. Environment Setup

### 5.1 Docker Compose (Recommended)

The fastest way to get the entire platform running:

```bash
# 1. Clone the repository
git clone <repository-url>
cd "PUBLIC CHARGER RND"

# 2. Start all services
docker-compose up -d --build

# 3. Check services are running
docker-compose ps
```

**Services will be available at:**
| Service | URL |
|---------|-----|
| AppEV (Flutter Web) | http://localhost:3000 |
| ChargingPlatform API | http://localhost:8000 |
| Admin Dashboard | http://localhost:8000 |
| OCPP WebSocket | ws://localhost:9000 |
| MySQL | localhost:3307 |

**Default Admin Credentials:**
- Email: `1@admin.com`
- Password: `1`

### 5.2 Manual Setup

#### Backend (ChargingPlatform)

```bash
# 1. Navigate to backend
cd ChargingPlatform

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
# Windows (PowerShell)
$env:DATABASE_URL = "sqlite:///./charging_platform.db"
$env:SMTP_EMAIL = "your-email@gmail.com"
$env:SMTP_PASSWORD = "your-app-password"
$env:SMTP_FROM_NAME = "PlagSini EV"

# Linux/macOS
export DATABASE_URL="sqlite:///./charging_platform.db"
export SMTP_EMAIL="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SMTP_FROM_NAME="PlagSini EV"

# 5. Run the server
python main.py
```

The backend supports both **SQLite** (default, for development) and **MySQL** (for production).

#### Frontend (AppEV)

```bash
# 1. Navigate to frontend
cd AppEV

# 2. Get dependencies
flutter pub get

# 3. Run on Web
flutter run -d chrome

# 4. Run on Android (with custom API URL)
flutter run --dart-define=API_BASE_URL=http://<YOUR_PC_IP>:8000/api

# 5. Build for Web
flutter build web --release
```

#### ESP32 Firmware

```bash
# 1. Install PlatformIO CLI
pip install platformio

# 2. Navigate to firmware
cd ESP-Charger-RND

# 3. Build
pio run

# 4. Flash to ESP32
pio run -t upload

# 5. Monitor serial output
pio device monitor -b 115200
```

---

## 6. Backend — ChargingPlatform

### 6.1 Architecture Overview

The backend is a single Python application that runs two servers concurrently:

1. **FastAPI HTTP Server** (port 8000) — REST API + Admin Web UI
2. **OCPP WebSocket Server** (port 9000) — Handles charger connections

```python
# main.py — Entry point
def start_servers():
    init_db()                    # Create database tables
    create_default_admin()       # Create admin user if not exists
    
    # Start OCPP WebSocket server in background thread
    ocpp_thread = threading.Thread(
        target=lambda: asyncio.run(ocpp_server()),
        daemon=True
    )
    ocpp_thread.start()
    
    # Start FastAPI server (blocking)
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 6.2 Database Models

All models are defined in `database.py` using SQLAlchemy ORM:

| Model | Table | Description |
|-------|-------|-------------|
| `User` | `users` | User accounts (email, password hash, admin flag) |
| `Wallet` | `wallets` | User wallet (balance in MYR, reward points) |
| `WalletTransaction` | `wallet_transactions` | All wallet transactions (topup, charge, refund, points) |
| `Vehicle` | `vehicles` | User's registered EVs (brand, model, battery capacity) |
| `OTPVerification` | `otp_verifications` | Email OTP codes (6-digit, 5-min expiry, max 5 attempts) |
| `Charger` | `chargers` | Registered charging stations (status, config, heartbeat) |
| `ChargingSession` | `charging_sessions` | Active and completed charging sessions |
| `Payment` | `payments` | Payment records for sessions |
| `Pricing` | `pricing` | Pricing configurations (per kWh, per minute) |
| `MeterValue` | `meter_values` | Real-time meter readings (V, A, W, kWh) |
| `Fault` | `faults` | Charger fault/error records |
| `MaintenanceRecord` | `maintenance_records` | Maintenance history |

**Password Hashing:**
```python
# Uses PBKDF2-HMAC-SHA256 with random salt
def set_password(self, password: str):
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    self.password_hash = f"{salt}${hash_obj.hex()}"
```

**Database Connection:**
```python
# Supports both SQLite (dev) and MySQL (production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./charging_platform.db")
```

### 6.3 REST API Endpoints

See [Section 10: API Reference](#10-api-reference) for the full list.

### 6.4 OCPP 1.6 WebSocket Server

The OCPP server is implemented in `ocpp_server.py` using the `ocpp` Python library.

**Connection Flow:**
1. Charger connects to `ws://<server>:9000/<charge_point_id>` with subprotocol `ocpp1.6`.
2. Server creates a `ChargePoint` instance and starts handling messages.
3. Active charge points are tracked in `active_charge_points` dictionary.

**Handled OCPP Messages (Charger → Server):**
| Message | Handler | Description |
|---------|---------|-------------|
| `BootNotification` | `on_boot_notification` | Charger registration/reconnection |
| `Heartbeat` | `on_heartbeat` | Keep-alive, returns current time |
| `StatusNotification` | `on_status_notification` | Charger status updates |
| `Authorize` | `on_authorize` | ID tag authorization |
| `StartTransaction` | `on_start_transaction` | Session start notification |
| `StopTransaction` | `on_stop_transaction` | Session end notification |
| `MeterValues` | `on_meter_values` | Real-time energy readings |
| `DataTransfer` | `on_data_transfer` | Custom data exchange |
| `DiagnosticsStatusNotification` | `on_diagnostics_status_notification` | Diagnostics upload status |
| `FirmwareStatusNotification` | `on_firmware_status_notification` | Firmware update status |

**Outgoing OCPP Commands (Server → Charger):**
| Method | Description |
|--------|-------------|
| `remote_start_transaction` | Start charging remotely |
| `remote_stop_transaction` | Stop charging remotely |
| `change_availability` | Set connector availability |
| `change_configuration` | Update charger config key |
| `get_configuration` | Read charger configuration |
| `clear_cache` | Clear authorization cache |
| `reset` | Hard/Soft reset charger |
| `unlock_connector` | Unlock specific connector |
| `get_diagnostics` | Request diagnostics file |
| `update_firmware` | Trigger firmware update |
| `reserve_now` | Reserve a connector |
| `cancel_reservation` | Cancel reservation |
| `data_transfer` | Send custom data |
| `get_local_list_version` | Get local auth list version |
| `send_local_list` | Update local auth list |
| `trigger_message` | Trigger specific message |
| `get_composite_schedule` | Get charging schedule |
| `clear_charging_profile` | Remove charging profiles |
| `set_charging_profile` | Set smart charging profile |

### 6.5 Email Service (OTP)

Implemented in `email_service.py`:

- **Gmail SMTP** with TLS (port 587)
- **HTML email template** with branded PlagSini design
- **Async sending** via `asyncio.to_thread()`
- **Dev mode fallback**: If SMTP is not configured, OTP is logged to console

**Configuration:**
```python
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")           # Gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")       # Gmail App Password
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "PlagSini EV")
```

**Gmail App Password Setup:**
1. Go to Google Account → Security → 2-Step Verification (enable if not already)
2. Go to App Passwords → Generate a new one
3. Use the 16-character password as `SMTP_PASSWORD`

### 6.6 Admin Web Templates

Admin UI is server-rendered HTML using Jinja2 templates + vanilla JavaScript.

| Page | Template | Description |
|------|----------|-------------|
| Dashboard | `dashboard.html` | Statistics, charts (Chart.js) |
| Chargers | `chargers.html` | Charger list with real-time status |
| Sessions | `sessions.html` | Charging session management |
| Metering | `metering.html` | Energy meter readings |
| Faults | `faults.html` | Error/fault log |
| Maintenance | `maintenance.html` | Maintenance records CRUD |
| Invoice | `invoice.html` | Billing and invoice management |
| OCPP Operations | `operations.html` | Full OCPP 1.6 command interface |
| Admin | `admin.html` | User management |
| Settings | `settings.html` | Platform configuration |

All templates share a common sidebar navigation and use a dark futuristic theme defined in `static/styles.css`.

---

## 7. Frontend — AppEV (Flutter)

### 7.1 Architecture Overview

AppEV follows the **Provider pattern** for state management with a clean separation of concerns:

```
lib/
├── main.dart           # App entry, theme, MultiProvider setup
├── constants/          # Shared constants (colors)
├── models/             # Data models (User)
├── providers/          # State management (ChangeNotifier)
├── services/           # API communication layer
├── screens/            # Full-page UI screens
└── widgets/            # Reusable UI components
```

### 7.2 State Management

Uses `provider` package with `ChangeNotifier`:

| Provider | File | Responsibility |
|----------|------|---------------|
| `AuthProvider` | `auth_provider.dart` | Login/register/logout, OTP flow, user data |
| `ChargerProvider` | `charger_provider.dart` | Fetch & cache nearby chargers, GPS location |
| `SessionProvider` | `session_provider.dart` | Active session tracking, history, polling |
| `PaymentProvider` | `payment_provider.dart` | Payment state management |

**Provider Setup (main.dart):**
```dart
MultiProvider(
  providers: [
    ChangeNotifierProvider(create: (_) => AuthProvider()),
    ChangeNotifierProvider(create: (_) => ChargerProvider()),
    ChangeNotifierProvider(create: (_) => PaymentProvider()),
    ChangeNotifierProvider(create: (_) => SessionProvider()),
  ],
  child: MaterialApp(...),
)
```

### 7.3 Screens & Navigation

| Screen | File | Description |
|--------|------|-------------|
| Splash | `splash_screen.dart` | Animated car+station+cable with PlagSini logo |
| Login/Register | `login_screen.dart` | Tab-based login & registration form |
| OTP Verification | `otp_verification_screen.dart` | 6-digit OTP input with resend |
| Home | `home_screen.dart` | Bottom nav controller (5 tabs) |
| Dashboard | `home_screen.dart` (embedded) | Quick actions, nearby stations, active session banner |
| Find Charger | `find_charger_screen.dart` | OpenStreetMap with charger pins |
| Scan QR | `scan_screen.dart` | Camera QR scanner with torch toggle |
| Rewards | `rewards_screen.dart` | Points display, catalog, redeem, history |
| Profile | `profile_screen.dart` | Account info, menu items |
| Live Charging | `live_charging_screen.dart` | Real-time session data |
| Charger Detail | `charger_detail_screen.dart` | Individual charger info |
| Edit Profile | `edit_profile_screen.dart` | Update user details |
| Wallet History | `wallet_history_screen.dart` | Transaction list |
| Top-Up | `topup_screen.dart` | Add funds to wallet |
| History | `history_screen.dart` | Past charging sessions |
| My Vehicles | `my_vehicles_screen.dart` | Vehicle management |
| Payment | `payment_screen.dart` | Payment methods |
| Subscriptions | `subscriptions_screen.dart` | Subscription plans |
| Invite Friends | `invite_friends_screen.dart` | Referral system |
| FAQ | `faq_screen.dart` | Help articles |
| Contact Us | `contact_us_screen.dart` | Support form |

**Bottom Navigation:**
```
Index 0: Dashboard (Home)
Index 1: Find Charger (Map)
Index 2: Scan QR Code
Index 3: Rewards
Index 4: Profile
```

### 7.4 API Service

All HTTP communication is centralized in `api_service.dart`:

```dart
class ApiService {
  // Dynamic base URL detection
  static String get baseUrl {
    // 1. Check --dart-define override
    // 2. Web: http://localhost:8000/api
    // 3. Android emulator: http://10.0.2.2:8000/api
  }
  
  // All methods are static for easy access
  static Future<List<Map<String, dynamic>>> getNearbyChargers(...);
  static Future<Map<String, dynamic>> login(...);
  static Future<Map<String, dynamic>> sendOTP(...);
  // ... 30+ API methods
}
```

**API URL Configuration:**
| Platform | Default URL |
|----------|------------|
| Web | `http://localhost:8000/api` |
| Android Emulator | `http://10.0.2.2:8000/api` |
| Custom | `--dart-define=API_BASE_URL=http://<IP>:8000/api` |

### 7.5 Theme & Design System

The app uses a **dark futuristic theme** with neon green accents:

| Element | Color | Hex |
|---------|-------|-----|
| Primary Green | Neon Green | `#00FF88` |
| Medium Green | — | `#00D977` |
| Dark Green | — | `#00AA55` |
| Background | Dark Navy | `#0A0A1A` |
| Surface | — | `#0F1B2D` |
| Card Background | — | `#12192B` |
| Text Primary | Light | `#E8E8E8` |
| Text Secondary | — | `#CCCCCC` |
| Border | — | `#1E2D42` |
| Error | Red | `#FF4444` |
| Warning | Orange | `#FFA500` |

All page transitions use `CupertinoPageTransitionsBuilder` for smooth iOS-style slide animations across all platforms.

### 7.6 Building for Different Platforms

```bash
# Web (development)
flutter run -d chrome

# Web (production build)
flutter build web --release

# Android APK
flutter build apk --release

# Android App Bundle (for Play Store)
flutter build appbundle --release

# iOS (requires macOS + Xcode)
flutter build ios --release

# With custom API URL
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000/api
```

**Android Permissions (already configured in AndroidManifest.xml):**
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-feature android:name="android.hardware.camera" android:required="false" />
<uses-feature android:name="android.hardware.camera.autofocus" android:required="false" />
```

---

## 8. ESP32 Charger Firmware

### 8.1 Hardware Requirements

- **ESP32 DevKitC** (or compatible)
- Relay module for EVSE control
- Current/Voltage sensor (for metering)
- I2C LCD display (16x2 or 20x4)
- Control Pilot (CP) circuit
- Manual ON/OFF buttons

### 8.2 Firmware Architecture

```
main.cpp
  ├── EvseController    — EVSE state machine (A/B/C states), relay control, CP PWM
  ├── OcppClient        — MicroOcpp integration, WebSocket to server
  ├── LcdDisplay        — I2C LCD status display
  ├── OcppFirmwareUpdate — HTTP firmware download triggered by OCPP
  └── OtaManager        — Arduino OTA for development updates
```

**Key Classes:**

| Class | File | Responsibility |
|-------|------|---------------|
| `EvseController` | `EvseController.cpp/h` | EVSE pilot signal, relay control, current measurement |
| `OcppClient` | `OcppClient.cpp/h` | MicroOcpp library wrapper, WS connection to server |
| `LcdDisplay` | `LcdDisplay.cpp/h` | LCD status messages (charging state, energy, errors) |
| `OcppFirmwareUpdate` | `OcppFirmwareUpdate.cpp/h` | Handles OCPP `UpdateFirmware` command |
| `OtaManager` | `OtaManager.cpp/h` | Arduino OTA for development firmware uploads |

### 8.3 Building & Flashing

```bash
# Using PlatformIO CLI
cd ESP-Charger-RND

# Build firmware
pio run

# Upload via USB
pio run -t upload

# Upload via OTA (replace with your ESP32's IP)
pio run -t upload --upload-port 192.168.1.100

# Monitor serial output
pio device monitor -b 115200
```

### 8.4 OTA Updates

Two OTA update mechanisms:

1. **Arduino OTA** — For development. Upload firmware from PlatformIO via WiFi.
2. **OCPP Firmware Update** — For production. Server triggers `UpdateFirmware` with a download URL. The ESP32 downloads and installs the new firmware via HTTP.

---

## 9. Docker Deployment

### 9.1 Services Overview

| Service | Container | Image | Ports |
|---------|-----------|-------|-------|
| `mysql` | `charging-platform-mysql` | `mysql:8.0` | 3307:3306 |
| `charging-platform` | `charging-platform` | Built from `./ChargingPlatform/Dockerfile` | 8000:8000, 9000:9000 |
| `appev` | `appev` | Built from `./AppEV/Dockerfile` | 3000:80 |

### 9.2 Docker Compose Configuration

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: charging-platform-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=rootpassword
      - MYSQL_DATABASE=charging_platform
      - MYSQL_USER=charging_user
      - MYSQL_PASSWORD=charging_password
    ports:
      - "3307:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]

  charging-platform:
    build: ./ChargingPlatform
    container_name: charging-platform
    ports:
      - "8000:8000"    # FastAPI REST API + Admin UI
      - "9000:9000"    # OCPP WebSocket
    environment:
      - DATABASE_URL=mysql+pymysql://charging_user:charging_password@mysql:3306/charging_platform
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_EMAIL=<your-email>@gmail.com
      - SMTP_PASSWORD=<your-app-password>
      - SMTP_FROM_NAME=PlagSini EV
    depends_on:
      mysql:
        condition: service_healthy

  appev:
    build: ./AppEV
    container_name: appev
    ports:
      - "3000:80"     # Nginx serving Flutter web build
    depends_on:
      - charging-platform
```

### 9.3 Building & Running

```bash
# Build and start all services
docker-compose up -d --build

# Rebuild a specific service
docker-compose up -d --build charging-platform
docker-compose up -d --build appev

# View logs
docker-compose logs -f charging-platform
docker-compose logs -f appev

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

### 9.4 Volume Management

| Volume | Purpose |
|--------|---------|
| `mysql-data` | MySQL database files (persistent) |
| `charging-platform-data` | Application data (mounted at `/app/data`) |

```bash
# List volumes
docker volume ls

# Inspect a volume
docker volume inspect public-charger-rnd_mysql-data

# Backup MySQL data
docker exec charging-platform-mysql mysqldump -u charging_user -pcharging_password charging_platform > backup.sql

# Restore MySQL data
docker exec -i charging-platform-mysql mysql -u charging_user -pcharging_password charging_platform < backup.sql
```

---

## 10. API Reference

Base URL: `http://localhost:8000/api`

### 10.1 Authentication APIs

#### Send OTP
```
POST /api/auth/send-otp
Body: { "email": "user@example.com" }
Response: { "success": true, "message": "OTP sent", "otp_id": 1 }
```

#### Verify OTP
```
POST /api/auth/verify-otp
Body: { "otp_id": 1, "otp_code": "123456" }
Response: { "success": true, "message": "OTP verified" }
```

#### Register (with OTP)
```
POST /api/users/register-with-otp
Body: {
  "email": "user@example.com",
  "password": "password123",
  "name": "John Doe",
  "phone": "0123456789",
  "otp_id": 1,
  "otp_code": "123456"
}
Response: { "success": true, "user": {...}, "token": "..." }
```

#### Register (without OTP)
```
POST /api/users/register
Body: {
  "email": "user@example.com",
  "password": "password123",
  "name": "John Doe",
  "phone": "0123456789"
}
Response: { "success": true, "user": {...}, "token": "..." }
```

#### Login
```
POST /api/users/login
Body: { "email": "user@example.com", "password": "password123" }
Response: { "success": true, "user": {...}, "token": "..." }
```

### 10.2 Charger APIs

#### List All Chargers
```
GET /api/chargers
Response: [{ "id": 1, "charge_point_id": "CP001", "status": "online", "availability": "available", ... }]
```

#### Get Charger Status
```
GET /api/chargers/{charge_point_id}/status
Response: { "id": 1, "charge_point_id": "CP001", "status": "online", ... }
```

#### Get Charger Configuration
```
GET /api/chargers/{charge_point_id}/configuration
Response: { "success": true, "configuration": [{ "key": "HeartbeatInterval", "value": "300" }] }
```

#### Change Charger Configuration
```
POST /api/chargers/{charge_point_id}/configuration/change
Body: { "key": "HeartbeatInterval", "value": "300" }
Response: { "success": true, "message": "Configuration accepted" }
```

### 10.3 Charging Session APIs

#### Start Charging
```
POST /api/charging/start
Body: { "charge_point_id": "CP001", "id_tag": "USER001", "connector_id": 1 }
Response: { "success": true, "message": "Charging started", "transaction_id": 123 }
```

#### Stop Charging
```
POST /api/charging/stop
Body: { "charge_point_id": "CP001", "transaction_id": 123 }
Response: { "success": true, "message": "Charging stopped" }
```

#### List Sessions
```
GET /api/sessions
Response: [{ "id": 1, "transaction_id": 123, "start_time": "...", "energy_consumed": 15.5, "status": "completed" }]
```

#### Get Meter Values
```
GET /api/metering/{charge_point_id}
Response: [{ "timestamp": "...", "voltage": 230.5, "current": 32.0, "power": 7360.0, "total_kwh": 15.5 }]
```

#### Get Latest Meter Value
```
GET /api/metering/{charge_point_id}/latest
Response: { "timestamp": "...", "voltage": 230.5, "current": 32.0, "power": 7360.0, "total_kwh": 15.5 }
```

### 10.4 OCPP Operation APIs

All OCPP operation endpoints follow the pattern:
```
POST /api/ocpp/{charge_point_id}/<operation-name>
```

| Endpoint | Body Parameters |
|----------|----------------|
| `/change-availability` | `{ "connector_id": 1, "type": "Operative" }` |
| `/clear-cache` | `{}` |
| `/reset` | `{ "type": "Hard" }` |
| `/unlock-connector` | `{ "connector_id": 1 }` |
| `/get-diagnostics` | `{ "location": "ftp://...", "start_time": "...", "stop_time": "..." }` |
| `/update-firmware` | `{ "location": "http://...", "retrieve_date": "..." }` |
| `/reserve-now` | `{ "connector_id": 1, "expiry_date": "...", "id_tag": "...", "reservation_id": 1 }` |
| `/cancel-reservation` | `{ "reservation_id": 1 }` |
| `/data-transfer` | `{ "vendor_id": "...", "message_id": "...", "data": "..." }` |
| `/get-local-list-version` | `{}` |
| `/send-local-list` | `{ "list_version": 1, "update_type": "Full", "local_authorization_list": [...] }` |
| `/trigger-message` | `{ "requested_message": "BootNotification", "connector_id": 1 }` |
| `/get-composite-schedule` | `{ "connector_id": 1, "duration": 3600 }` |
| `/clear-charging-profile` | `{ "id": 1, "connector_id": 1 }` |
| `/set-charging-profile` | `{ "connector_id": 1, "cs_charging_profiles": {...} }` |

### 10.5 User & Wallet APIs

#### Get User Profile
```
GET /api/users/{user_id}
Response: { "success": true, "user": { "id": 1, "name": "...", "email": "...", "wallet": {...} } }
```

#### Update User Profile
```
PUT /api/users/{user_id}
Body: { "name": "New Name", "phone": "0123456789" }
```

#### Get Wallet
```
GET /api/users/{user_id}/wallet
Response: { "balance": 50.00, "points": 1200, "currency": "MYR" }
```

#### Top-Up Wallet
```
POST /api/users/{user_id}/wallet/topup
Body: { "amount": 50.00, "payment_method": "fpx" }
```

#### Get Wallet Transactions
```
GET /api/users/{user_id}/wallet/transactions
Response: [{ "id": 1, "transaction_type": "topup", "amount": 50.0, "status": "completed" }]
```

#### Vehicle CRUD
```
GET    /api/users/{user_id}/vehicles
POST   /api/users/{user_id}/vehicles
DELETE /api/users/{user_id}/vehicles/{vehicle_id}
```

### 10.6 Rewards APIs

#### Get Rewards Catalog
```
GET /api/rewards/catalog
Response: [{ "id": 1, "name": "Free Charging 5kWh", "points_required": 500, "category": "free_charge" }]
```

#### Redeem Reward
```
POST /api/users/{user_id}/rewards/redeem
Body: { "reward_id": 1 }
Response: { "success": true, "message": "Redeemed!", "points_remaining": 700 }
```

#### Get Reward History
```
GET /api/users/{user_id}/rewards/history
Response: [{ "reward_name": "Free Charging 5kWh", "points_spent": 500, "redeemed_at": "..." }]
```

### 10.7 Admin APIs

#### Admin Login
```
POST /api/admin/login
Body: { "email": "1@admin.com", "password": "1" }
```

#### List Users
```
GET /api/admin/users
Response: [{ "id": 1, "name": "...", "email": "...", "is_admin": false, ... }]
```

#### Get Admin Stats
```
GET /api/admin/stats
Response: { "total_chargers": 5, "active_sessions": 2, "total_users": 100, "total_energy_kwh": 5000.0 }
```

#### CRUD Admin Users
```
GET    /api/admin/users/{user_id}
POST   /api/admin/users
PUT    /api/admin/users/{user_id}
DELETE /api/admin/users/{user_id}
```

### 10.8 Maintenance APIs

```
GET    /api/maintenance               # List all records
GET    /api/maintenance/{record_id}    # Get specific record
POST   /api/maintenance                # Create new record
PUT    /api/maintenance/{record_id}    # Update record
DELETE /api/maintenance/{record_id}    # Delete record
```

### 10.9 Invoice APIs

```
GET /api/invoice/summary     # Revenue summary and statistics
GET /api/invoice/sessions    # Completed sessions for invoicing
```

---

## 11. Configuration & Environment Variables

### ChargingPlatform Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./charging_platform.db` | Database connection string |
| `ADMIN_EMAIL` | `1@admin.com` | Default admin email |
| `ADMIN_PASSWORD` | `1` | Default admin password |
| `ADMIN_NAME` | `Admin` | Default admin display name |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server host |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_EMAIL` | (empty) | Sender email address |
| `SMTP_PASSWORD` | (empty) | Email password / App Password |
| `SMTP_FROM_NAME` | `PlagSini EV` | Email display name |
| `PYTHONUNBUFFERED` | `1` | Disable Python output buffering |

### MySQL Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL root password |
| `MYSQL_DATABASE` | `charging_platform` | Database name |
| `MYSQL_USER` | `charging_user` | Application DB user |
| `MYSQL_PASSWORD` | `charging_password` | Application DB password |

### Flutter Build-Time Variables

| Variable | Usage |
|----------|-------|
| `API_BASE_URL` | `--dart-define=API_BASE_URL=http://<IP>:8000/api` |

---

## 12. Testing

### Backend API Testing

```bash
# Test health check
curl http://localhost:8000/api/chargers

# Test OTP flow
curl -X POST http://localhost:8000/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Test login
curl -X POST http://localhost:8000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "1@admin.com", "password": "1"}'

# Test OCPP operation
curl -X POST http://localhost:8000/api/ocpp/CP001/reset \
  -H "Content-Type: application/json" \
  -d '{"type": "Soft"}'
```

### Flutter Testing

```bash
cd AppEV

# Run unit tests
flutter test

# Run with verbose logging
flutter run -d chrome --verbose
```

### ESP32 Testing

```bash
cd ESP-Charger-RND

# Build and check for errors
pio run

# Upload and monitor
pio run -t upload && pio device monitor -b 115200
```

### Database Inspection

```bash
# Connect to MySQL in Docker
docker exec -it charging-platform-mysql mysql -u charging_user -pcharging_password charging_platform

# Useful queries
SELECT * FROM users;
SELECT * FROM chargers;
SELECT * FROM charging_sessions WHERE status = 'active';
SELECT * FROM otp_verifications ORDER BY id DESC LIMIT 5;
```

---

## 13. Common Development Tasks

### Adding a New API Endpoint

1. Define Pydantic model in `api.py`:
```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    success: bool
    data: Any
```

2. Add the endpoint:
```python
@app.post("/api/my-endpoint", response_model=MyResponse)
async def my_endpoint(request: MyRequest, db: Session = Depends(get_db)):
    # Implementation
    return MyResponse(success=True, data=...)
```

### Adding a New Flutter Screen

1. Create `lib/screens/my_screen.dart`
2. Import in the parent screen/navigation
3. Add API methods in `api_service.dart` if needed
4. Use `Provider.of<MyProvider>(context)` for state

### Adding a New OCPP Handler

1. In `ocpp_server.py`, add to the `ChargePoint` class:
```python
@on('NewMessage')
async def on_new_message(self, **kwargs):
    logger.info(f"NewMessage from {self.id}")
    return call_result.NewMessage(status="Accepted")
```

2. For outgoing commands:
```python
async def send_new_command(self):
    request = call.NewCommand(param="value")
    response = await self.call(request)
    return response
```

### Adding a New Database Table

1. Define model in `database.py`:
```python
class NewTable(Base):
    __tablename__ = "new_tables"
    id = Column(Integer, primary_key=True, index=True)
    # ... columns
```

2. Tables are auto-created on startup via `init_db()`.

### Updating Docker Images

```bash
# Rebuild specific service
docker-compose up -d --build charging-platform

# Rebuild all
docker-compose up -d --build

# Full clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 14. Troubleshooting

### Docker Issues

| Problem | Solution |
|---------|----------|
| `port already in use` | Stop conflicting service: `docker-compose down` then restart |
| MySQL health check failing | Wait 30s for MySQL to initialize. Check: `docker logs charging-platform-mysql` |
| `no space left on device` | Clean up: `docker system prune -a` |
| Build fails | Check Docker daemon is running. Try `docker-compose build --no-cache` |

### Backend Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Install deps: `pip install -r requirements.txt` |
| DB connection error | Check `DATABASE_URL` env var. Ensure MySQL is running. |
| OCPP charger not connecting | Check WebSocket URL is `ws://<IP>:9000/<charger_id>`, subprotocol = `ocpp1.6` |
| OTP email not sending | Check SMTP vars. View logs: `docker logs charging-platform` |
| `SMTP Authentication failed` | Regenerate Gmail App Password. Ensure 2FA is enabled. |

### Flutter Issues

| Problem | Solution |
|---------|----------|
| `flutter pub get` fails | Delete `pubspec.lock` and retry. Check Flutter SDK version. |
| API calls failing (web) | Ensure CORS is configured. Check browser console for errors. |
| API calls failing (Android) | Use `--dart-define=API_BASE_URL=http://<PC_IP>:8000/api` |
| Camera not working | Check permissions in `AndroidManifest.xml`. Request permission at runtime. |
| Map not loading | Check internet connection. `flutter_map` uses OpenStreetMap (no API key needed). |

### ESP32 Issues

| Problem | Solution |
|---------|----------|
| Upload fails | Check COM port. Try different USB cable. Hold BOOT button during upload. |
| WiFi not connecting | Check SSID/password in `HardwareConfig.h`. Ensure 2.4GHz network. |
| OCPP not connecting | Verify WebSocket URL and port 9000 is reachable from ESP32. |
| OTA upload fails | Ensure ESP32 and PC are on same network. Check IP address. |
| LCD not displaying | Check I2C address (usually 0x27 or 0x3F). Check wiring (SDA/SCL). |

### PowerShell-Specific Issues

| Problem | Solution |
|---------|----------|
| `&&` not recognized | Use `;` instead of `&&` in PowerShell, or run each command separately |
| `curl` behaves differently | PowerShell `curl` is an alias for `Invoke-WebRequest`. Use `curl.exe` for standard curl |

---

*© 2026 PlagSini EV Charging Platform. All rights reserved.*

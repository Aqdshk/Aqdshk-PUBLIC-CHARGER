# Hybrid Implementation Roadmap - Step by Step

Practical implementation guide untuk migrate dari ESP32 standalone ke Hybrid (RPi + ESP32) architecture.

---

## **Current State → Target State**

### **Current (ESP32 Standalone):**
- ✅ ESP32 handle semua: OCPP, charging control, safety, LCD
- ✅ Single charger
- ✅ Basic functionality

### **Target (Hybrid RPi + ESP32):**
- ✅ Raspberry Pi: OCPP, payment, web UI, analytics, database
- ✅ ESP32: Real-time charging control, safety, CP PWM
- ✅ Multiple chargers support
- ✅ Commercial features

---

## **Phase 1: Foundation (Week 1-2)**

### **Step 1.1: Setup Raspberry Pi**

1. **Install Raspberry Pi OS:**
   ```bash
   # Download Raspberry Pi Imager
   # Flash to SD card (32GB+)
   # Enable SSH, WiFi (optional)
   ```

2. **Basic Setup:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3-pip git -y
   ```

3. **Enable I2C:**
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Enable
   sudo apt install i2c-tools -y
   i2cdetect -y 1  # Test I2C bus
   ```

### **Step 1.2: Create Communication Protocol**

1. **Define Message Format:**
   - Create `message_protocol.h` dengan struct definitions
   - Command: START, STOP, SET_CURRENT
   - Status: State, meter values, errors

2. **Test I2C Communication:**
   - ESP32 as I2C slave (address 0x10)
   - RPi as I2C master
   - Simple read/write test

---

## **Phase 2: Basic Communication (Week 2-3)**

### **Step 2.1: Modify ESP32 Code**

1. **Remove OCPP:**
   - Comment out `OcppClient` initialization
   - Keep `EvseController` (charging logic)
   - Keep safety systems

2. **Add I2C Communication Module:**
   - Create `Communication.h` and `Communication.cpp`
   - Implement I2C slave mode
   - Report status to RPi
   - Receive commands from RPi

3. **Test:**
   - ESP32 report status setiap 1 saat
   - RPi send START/STOP commands
   - Verify charging start/stop working

### **Step 2.2: RPi Basic Controller**

1. **Create Python Script:**
   ```python
   # charger_controller.py
   import smbus
   import time
   
   class ChargerController:
       def __init__(self, i2c_address):
           self.bus = smbus.SMBus(1)
           self.address = i2c_address
       
       def start_charging(self, current_limit=16):
           # Send START command
           pass
       
       def stop_charging(self):
           # Send STOP command
           pass
       
       def get_status(self):
           # Read status from ESP32
           pass
   ```

2. **Test:**
   - Send commands via command line
   - Read status
   - Verify communication working

---

## **Phase 3: Move OCPP to Raspberry Pi (Week 3-4)**

### **Step 3.1: Install OCPP Library on RPi**

1. **Option A: MicroOcpp (C++):**
   ```bash
   # Compile MicroOcpp for Linux
   # Create wrapper library
   ```

2. **Option B: ArduinoOcpp (Python port atau use existing Python OCPP):**
   ```bash
   pip install ocpp
   ```

3. **Option C: Custom OCPP Client (Python):**
   ```bash
   pip install websockets json
   # Implement basic OCPP 1.6J client
   ```

### **Step 3.2: Integrate OCPP with Charger**

1. **OCPP Client on RPi:**
   - Connect to SteVe
   - Handle BootNotification, Heartbeat
   - Handle RemoteStartTransaction, RemoteStopTransaction

2. **Bridge OCPP ↔ ESP32:**
   - RemoteStartTransaction → send START to ESP32
   - RemoteStopTransaction → send STOP to ESP32
   - ESP32 status → send MeterValues to OCPP

3. **Test:**
   - Connect to SteVe
   - Test remote start/stop from SteVe
   - Verify transactions working

---

## **Phase 4: Web Server (Week 4-5)**

### **Step 4.1: Setup Web Server**

1. **Install Flask/FastAPI:**
   ```bash
   pip install flask flask-socketio
   # atau
   pip install fastapi uvicorn websockets
   ```

2. **Create Basic Web Server:**
   ```python
   # web_server.py
   from flask import Flask, render_template
   from flask_socketio import SocketIO, emit
   
   app = Flask(__name__)
   socketio = SocketIO(app)
   
   @app.route('/')
   def index():
       return render_template('index.html')
   
   @app.route('/api/status')
   def get_status():
       # Get charger status
       return charger_controller.get_status()
   
   @socketio.on('connect')
   def handle_connect():
       # Send real-time updates
       emit('status', charger_controller.get_status())
   ```

3. **Create Dashboard:**
   - HTML template dengan real-time status
   - Start/Stop buttons
   - Current/Voltage/Energy display

### **Step 4.2: Deploy Web Server**

1. **Run on Boot:**
   ```bash
   # Create systemd service
   sudo nano /etc/systemd/system/charger-web.service
   
   [Unit]
   Description=EV Charger Web Server
   After=network.target
   
   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/charger
   ExecStart=/usr/bin/python3 /home/pi/charger/web_server.py
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   
   sudo systemctl enable charger-web
   sudo systemctl start charger-web
   ```

2. **Test:**
   - Access web interface dari browser
   - Test start/stop charging
   - Verify real-time updates

---

## **Phase 5: Database (Week 5-6)**

### **Step 5.1: Setup Database**

1. **SQLite (Simple):**
   ```bash
   # Built-in dengan Python
   import sqlite3
   ```

2. **PostgreSQL (Production):**
   ```bash
   sudo apt install postgresql postgresql-contrib -y
   pip install psycopg2
   ```

### **Step 5.2: Create Schema**

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    id_tag VARCHAR(21),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    energy_kwh REAL,
    cost REAL,
    status VARCHAR(20)
);

CREATE TABLE meter_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    timestamp TIMESTAMP,
    voltage REAL,
    current REAL,
    power REAL,
    energy REAL
);
```

### **Step 5.3: Integrate with Charger**

1. **Store Transactions:**
   - Save start/stop events
   - Save meter values periodically
   - Calculate cost

2. **API Endpoints:**
   - `/api/transactions` - Get transaction history
   - `/api/transactions/<id>` - Get transaction details

---

## **Phase 6: Payment System (Week 6-8)**

### **Step 6.1: Choose Payment Gateway**

1. **Stripe:**
   ```bash
   pip install stripe
   ```

2. **PayPal:**
   ```bash
   pip install paypalrestsdk
   ```

3. **Local Payment (QR Code, etc.):**
   - Generate QR code untuk payment
   - Manual payment confirmation

### **Step 6.2: Integrate Payment**

1. **Payment Flow:**
   - User select charging session
   - Enter payment method
   - Process payment
   - Start charging after payment confirmed

2. **Receipt Generation:**
   ```python
   # Generate PDF receipt
   from reportlab.pdfgen import canvas
   ```

3. **Test:**
   - Test payment processing
   - Test receipt generation
   - Test refund (if needed)

---

## **Phase 7: Analytics (Week 8-9)**

### **Step 7.1: Analytics Engine**

1. **Usage Statistics:**
   - Daily/monthly energy usage
   - Number of transactions
   - Average charging time

2. **Revenue Reports:**
   - Daily/monthly revenue
   - Payment method breakdown

3. **Performance Metrics:**
   - Uptime
   - Error rates
   - Average charging speed

### **Step 7.2: Dashboard**

1. **Charts:**
   ```python
   # Use Chart.js atau Plotly
   pip install plotly
   ```

2. **Reports:**
   - Generate PDF reports
   - Export to CSV

---

## **Phase 8: Multi-Charger Support (Week 9-10)**

### **Step 8.1: Charger Manager**

1. **Multiple ESP32 Support:**
   ```python
   class ChargerManager:
       def __init__(self):
           self.chargers = []
           # ESP32 addresses: 0x10, 0x11, 0x12, etc.
           for addr in [0x10, 0x11, 0x12]:
               self.chargers.append(ChargerController(addr))
   ```

2. **Load Balancing:**
   - Distribute power across chargers
   - Priority management

3. **Health Monitoring:**
   - Ping each charger
   - Detect failures
   - Automatic failover

### **Step 8.2: Update Web UI**

1. **Multi-Charger Dashboard:**
   - Show all chargers status
   - Select charger untuk control
   - Aggregated statistics

2. **OCPP Integration:**
   - Each ESP32 = one OCPP charge point
   - Manage multiple charge points

---

## **Code Structure**

```
project/
├── raspberry-pi/
│   ├── src/
│   │   ├── main.py                 # Entry point
│   │   ├── charger_manager.py      # Multi-charger management
│   │   ├── ocpp_client.py          # OCPP client
│   │   ├── payment_handler.py      # Payment processing
│   │   ├── web_server.py           # Web server
│   │   ├── database.py             # Database interface
│   │   ├── analytics.py            # Analytics engine
│   │   └── communication/
│   │       ├── i2c_protocol.py     # I2C communication
│   │       └── message_protocol.py # Message definitions
│   ├── web/
│   │   ├── static/                 # CSS, JS
│   │   ├── templates/              # HTML templates
│   │   └── api/                    # REST API
│   ├── database/
│   │   └── schema.sql              # Database schema
│   └── config/
│       └── config.yaml             # Configuration
│
└── esp32-charger/
    ├── src/
    │   ├── main.cpp                # Entry (simplified)
    │   ├── ChargerController.cpp   # Real-time control
    │   ├── Communication.cpp       # RPi communication
    │   ├── SafetySystem.cpp        # Safety checks
    │   ├── ControlPilot.cpp        # CP PWM
    │   └── MeterReading.cpp        # Energy measurement
    └── platformio.ini
```

---

## **Immediate Next Steps**

1. **Decide Communication Protocol:**
   - I2C (simple, prototype)
   - Ethernet (production, scalable)

2. **Setup Raspberry Pi:**
   - Install OS
   - Enable I2C
   - Test basic setup

3. **Create Communication Protocol:**
   - Define message format
   - Test I2C communication

4. **Modify ESP32 Code:**
   - Remove OCPP
   - Add I2C communication
   - Test basic communication

---

## **Timeline Estimate**

- **Phase 1-2:** 2-3 weeks (Foundation + Basic Communication)
- **Phase 3:** 1-2 weeks (OCPP Migration)
- **Phase 4:** 1-2 weeks (Web Server)
- **Phase 5:** 1 week (Database)
- **Phase 6:** 2-3 weeks (Payment)
- **Phase 7:** 1-2 weeks (Analytics)
- **Phase 8:** 1-2 weeks (Multi-Charger)

**Total: ~10-16 weeks** untuk full implementation

---

## **Quick Start (Minimal Viable Product)**

Kalau nak quick start dengan minimal features:

1. **Week 1:** Setup RPi, basic I2C communication
2. **Week 2:** Move OCPP to RPi, test remote start/stop
3. **Week 3:** Simple web interface, database
4. **Week 4:** Basic payment (manual confirmation)

**MVP dalam 4 minggu** dengan core features working!

---

**Ready untuk start?** Mari kita plan Phase 1 dulu!








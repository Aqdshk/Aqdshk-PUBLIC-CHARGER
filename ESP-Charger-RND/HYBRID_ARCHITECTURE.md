# Hybrid Architecture: Raspberry Pi + ESP32 for Commercial EV Charger

Architecture design untuk commercial EV charger dengan payment, web UI, analytics, dan multiple charger support.

---

## **Architecture Overview**

```
┌─────────────────────────────────────────────────────────┐
│              Raspberry Pi 4 (Main Controller)           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Linux OS (Raspberry Pi OS)                      │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  OCPP Central System Client                │ │  │
│  │  │  - SteVe Integration                       │ │  │
│  │  │  - Transaction Management                  │ │  │
│  │  │  - Remote Start/Stop                       │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Payment System                             │ │  │
│  │  │  - Payment Gateway Integration              │ │  │
│  │  │  - Credit Card Processing                  │ │  │
│  │  │  - RFID/NFC Card Reader                    │ │  │
│  │  │  - Receipt Generation                      │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Web Server (Node.js/Python/Flask)         │ │  │
│  │  │  - Admin Dashboard                         │ │  │
│  │  │  - User Interface                          │ │  │
│  │  │  - Real-time Status                        │ │  │
│  │  │  - Configuration                           │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Database (SQLite/PostgreSQL/MySQL)        │ │  │
│  │  │  - Transaction History                     │ │  │
│  │  │  - User Data                               │ │  │
│  │  │  - Analytics Data                          │ │  │
│  │  │  - Configuration                           │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Analytics Engine                          │ │  │
│  │  │  - Usage Statistics                        │ │  │
│  │  │  - Revenue Reports                         │ │  │
│  │  │  - Load Analysis                           │ │  │
│  │  │  - Performance Metrics                     │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Charger Manager (Multi-connector)         │ │  │
│  │  │  - Manage Multiple ESP32 Chargers          │ │  │
│  │  │  - Load Balancing                          │ │  │
│  │  │  - Priority Management                     │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│            │                                             │
│            │ I2C / SPI / UART / Ethernet               │
│            │ (Communication Protocol)                   │
└────────────┼─────────────────────────────────────────────┘
             │
             │ (Multiple ESP32 Chargers)
             │
    ┌────────┴────────┬──────────────┬──────────────┐
    │                 │              │              │
┌───▼────────┐  ┌─────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│  ESP32 #1  │  │  ESP32 #2  │  │ ESP32 #3 │  │ ESP32 #N │
│  (Charger1)│  │  (Charger2)│  │(Charger3)│  │(ChargerN)│
│            │  │            │  │          │  │          │
│ ┌────────┐ │  │ ┌────────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │Real-time│ │  │ │Real-time│ │  │ │Real- │ │  │ │Real- │ │
│ │CP PWM   │ │  │ │CP PWM   │ │  │ │time  │ │  │ │time  │ │
│ │Control  │ │  │ │Control  │ │  │ │CP PWM│ │  │ │CP PWM│ │
│ └────────┘ │  │ └────────┘ │  │ └──────┘ │  │ └──────┘ │
│ ┌────────┐ │  │ ┌────────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │Safety  │ │  │ │Safety  │ │  │ │Safety│ │  │ │Safety│ │
│ │Checks  │ │  │ │Checks  │ │  │ │Checks│ │  │ │Checks│ │
│ └────────┘ │  │ └────────┘ │  │ └──────┘ │  │ └──────┘ │
│ ┌────────┐ │  │ ┌────────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │Contactor│ │  │ │Contactor│ │  │ │Cont. │ │  │ │Cont. │ │
│ │Control │ │  │ │Control │ │  │ │Ctrl  │ │  │ │Ctrl  │ │
│ └────────┘ │  │ └────────┘ │  │ └──────┘ │  │ └──────┘ │
│ ┌────────┐ │  │ ┌────────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │Meter   │ │  │ │Meter   │ │  │ │Meter │ │  │ │Meter │ │
│ │Reading │ │  │ │Reading │ │  │ │Read. │ │  │ │Read. │ │
│ └────────┘ │  │ └────────┘ │  │ └──────┘ │  │ └──────┘ │
└────────────┘  └────────────┘  └──────────┘  └──────────┘
```

---

## **Division of Responsibilities**

### **Raspberry Pi (Main Controller):**

#### **1. OCPP Central System Client**
- Manage OCPP connection ke SteVe backend
- Handle BootNotification, Heartbeat
- Process RemoteStartTransaction, RemoteStopTransaction
- Send MeterValues, StatusNotification
- Handle firmware updates

#### **2. Payment System**
- Payment gateway integration (Stripe, PayPal, dll)
- Credit card processing
- RFID/NFC card reader management
- Receipt generation (PDF/email)
- Pricing rules (per kWh, time-based, dll)
- Refund handling

#### **3. Web Server & UI**
- Admin dashboard (monitor semua chargers)
- User interface (payment, start/stop charging)
- Real-time status updates (WebSocket)
- Configuration management
- Firmware upload interface
- Reports & analytics dashboard

#### **4. Database**
- Transaction history (all chargers)
- User accounts & payment methods
- Charger configurations
- Usage statistics
- Revenue reports
- Error logs

#### **5. Analytics Engine**
- Usage statistics (per charger, per day/month)
- Revenue reports
- Load analysis (peak hours, usage patterns)
- Performance metrics (uptime, error rates)
- Predictive analytics (maintenance scheduling)

#### **6. Charger Manager (Multi-connector)**
- Manage multiple ESP32 chargers
- Load balancing (distribute power across chargers)
- Priority management (VIP users, scheduled charging)
- Health monitoring (ping/status checks)
- Automatic failover

---

### **ESP32 (Real-time Charger Controller):**

#### **1. Control Pilot (CP) Management**
- Generate CP PWM signal (1 kHz, precise timing)
- Read CP voltage (State A/B/C/D detection)
- IEC 61851 state machine
- Current limit communication

#### **2. Safety Systems**
- RCD/GFCI monitoring
- Emergency stop handling
- Overcurrent protection
- Overvoltage/undervoltage protection
- Temperature monitoring
- Ground fault detection

#### **3. Power Control**
- Contactor control (AC power switching)
- Current limiting
- Soft start/stop sequences
- Power quality monitoring

#### **4. Meter Reading**
- Energy measurement (kWh)
- Current measurement (A)
- Voltage measurement (V)
- Power measurement (W)
- Real-time sampling

#### **5. Communication with Raspberry Pi**
- Report status (state, errors, meter values)
- Receive commands (start/stop, current limit)
- Heartbeat/ping to RPi
- Error reporting

---

## **Communication Protocol**

### **Option 1: I2C (Recommended untuk Multiple ESP32)**

**Pros:**
- Multiple devices on same bus (up to 127 addresses)
- Simple wiring (2 wires: SDA, SCL)
- Good untuk short distances (< 1m)

**Cons:**
- Limited speed (100kHz standard, 400kHz fast)
- Limited distance

**Implementation:**
- RPi: I2C master
- ESP32: I2C slave dengan unique address (0x10, 0x11, 0x12, etc.)

### **Option 2: SPI**

**Pros:**
- Fast communication
- Full duplex
- Good untuk high-speed data transfer

**Cons:**
- More wires (MOSI, MISO, SCK, CS per device)
- More complex wiring untuk multiple devices

### **Option 3: UART/Serial**

**Pros:**
- Simple (2 wires: TX, RX)
- Long distance dengan RS485
- Reliable

**Cons:**
- Need separate UART per ESP32 (atau RS485 bus)
- Slower than SPI/I2C

### **Option 4: Ethernet (Recommended untuk Multiple Chargers)**

**Pros:**
- Standard network protocol
- Long distance
- Multiple devices via switch/hub
- Easy to scale
- Remote management

**Cons:**
- ESP32 need Ethernet module (ESP32-POE atau external PHY)
- More expensive
- More complex setup

**Implementation:**
- Each ESP32 has unique IP address (192.168.1.101, 102, 103, etc.)
- Communication via TCP/UDP atau HTTP REST API

---

## **Recommended Communication Protocol: I2C (Development) + Ethernet (Production)**

### **Development/Prototype:**
- Use **I2C** untuk simple setup
- Up to 8-16 chargers per RPi

### **Production:**
- Use **Ethernet** untuk scalability
- Each ESP32 dengan Ethernet module
- Easy to add/remove chargers
- Remote management
- Better isolation

---

## **Message Protocol (I2C/SPI/UART)**

### **Command Format (RPi → ESP32):**

```cpp
struct ChargerCommand {
    uint8_t command;      // START_CHARGING, STOP_CHARGING, SET_CURRENT_LIMIT, etc.
    uint16_t currentLimit; // Amperes (for SET_CURRENT_LIMIT)
    uint32_t transactionId; // OCPP transaction ID
    char idTag[21];       // OCPP idTag
};
```

### **Status Format (ESP32 → RPi):**

```cpp
struct ChargerStatus {
    uint8_t state;         // IDLE, CHARGING, FAULT, etc.
    uint8_t errorCode;     // Error code (0 = no error)
    float voltage;         // Voltage (V)
    float current;         // Current (A)
    float power;           // Power (W)
    float energy;          // Energy (kWh)
    uint32_t transactionId; // Active transaction ID
    uint32_t timestamp;    // Unix timestamp
};
```

---

## **Implementation Steps**

### **Phase 1: Single Charger (RPi + ESP32)**

1. **Setup Raspberry Pi:**
   - Install Raspberry Pi OS
   - Setup I2C/Ethernet communication
   - Basic charger control interface

2. **Modify ESP32 Code:**
   - Add communication protocol (I2C/Ethernet)
   - Remove OCPP (move to RPi)
   - Keep real-time safety features
   - Report status to RPi

3. **Test Communication:**
   - Verify RPi ↔ ESP32 communication
   - Test start/stop charging
   - Test status reporting

### **Phase 2: Add Web Server**

1. **Setup Web Server (Node.js/Python/Flask):**
   - Admin dashboard
   - Real-time status display
   - Start/stop charging interface

2. **Add Database:**
   - Transaction history
   - Configuration storage

### **Phase 3: Add Payment System**

1. **Integrate Payment Gateway:**
   - Stripe/PayPal integration
   - Credit card processing
   - Receipt generation

2. **Add User Interface:**
   - Payment interface
   - User registration/login
   - Transaction history for users

### **Phase 4: Add Analytics**

1. **Analytics Engine:**
   - Usage statistics
   - Revenue reports
   - Performance metrics

2. **Dashboard:**
   - Charts & graphs
   - Export reports

### **Phase 5: Multi-Charger Support**

1. **Charger Manager:**
   - Multiple ESP32 management
   - Load balancing
   - Priority management

2. **Scalability:**
   - Add/remove chargers dynamically
   - Health monitoring
   - Failover handling

---

## **Code Structure (Raspberry Pi)**

```
raspberry-pi-charger/
├── src/
│   ├── main.py                 # Main application entry
│   ├── charger_manager.py      # Manage multiple ESP32 chargers
│   ├── ocpp_client.py          # OCPP client (SteVe integration)
│   ├── payment_handler.py      # Payment processing
│   ├── web_server.py           # Web server (Flask/FastAPI)
│   ├── database.py             # Database interface
│   ├── analytics.py            # Analytics engine
│   └── communication/
│       ├── i2c_protocol.py     # I2C communication
│       ├── ethernet_protocol.py # Ethernet communication
│       └── message_protocol.py  # Message format definitions
├── web/
│   ├── static/                 # CSS, JS, images
│   ├── templates/              # HTML templates
│   └── api/                    # REST API endpoints
├── database/
│   └── schema.sql              # Database schema
└── config/
    └── config.yaml             # Configuration file
```

---

## **Code Structure (ESP32 - Modified)**

```
esp32-charger/
├── src/
│   ├── main.cpp                # Main entry (simplified)
│   ├── ChargerController.cpp   # Real-time charger control
│   ├── Communication.cpp       # RPi communication (I2C/Ethernet)
│   ├── SafetySystem.cpp        # Safety checks
│   ├── ControlPilot.cpp        # CP PWM & sensing
│   ├── MeterReading.cpp        # Energy measurement
│   └── HardwareConfig.h        # Pin configuration
└── platformio.ini
```

---

## **Key Changes Needed**

### **ESP32 Code Changes:**

1. **Remove OCPP:**
   - Remove `OcppClient.cpp`
   - Remove `OcppFirmwareUpdate.cpp` (move to RPi)

2. **Add Communication Protocol:**
   - I2C slave mode atau Ethernet client
   - Implement message protocol
   - Report status to RPi
   - Receive commands from RPi

3. **Keep Real-time Features:**
   - Control Pilot PWM
   - Safety systems
   - Contactor control
   - Meter reading

### **Raspberry Pi Code (New):**

1. **OCPP Client:**
   - Use MicroOcpp atau ArduinoOcpp Linux version
   - Handle OCPP communication
   - Forward commands to ESP32

2. **Charger Manager:**
   - Manage multiple ESP32 chargers
   - Communication protocol implementation
   - Status aggregation

3. **Web Server:**
   - Flask/FastAPI untuk web interface
   - WebSocket untuk real-time updates
   - REST API untuk mobile apps

4. **Payment System:**
   - Payment gateway integration
   - Transaction management
   - Receipt generation

5. **Database:**
   - SQLite (simple) atau PostgreSQL (production)
   - Transaction history
   - User management

---

## **Hardware Requirements**

### **Raspberry Pi:**
- Raspberry Pi 4 (recommended) atau Pi 3B+
- SD Card (32GB+ Class 10)
- Power Supply (5V 3A+)
- Case dengan cooling
- Optional: PoE HAT (kalau guna PoE)

### **ESP32 (per charger):**
- ESP32 DevKit atau custom board
- Ethernet module (kalau guna Ethernet)
- Or I2C connection ke RPi (kalau guna I2C)
- Existing hardware (relays, contactors, CP circuit)

### **Additional Hardware:**
- Payment terminal (credit card reader, RFID reader)
- Display/Touchscreen (optional, untuk user interface)
- Network switch (kalau multiple ESP32 via Ethernet)

---

## **Communication Example (I2C)**

### **ESP32 Side (I2C Slave):**

```cpp
// ESP32 sebagai I2C slave, address 0x10
#include <Wire.h>

#define I2C_SLAVE_ADDRESS 0x10

struct ChargerStatus status;

void setup() {
    Wire.begin(I2C_SLAVE_ADDRESS);
    Wire.onRequest(onRequest);  // RPi request data
    Wire.onReceive(onReceive);  // RPi send command
}

void onRequest() {
    // Send status to RPi
    Wire.write((uint8_t*)&status, sizeof(status));
}

void onReceive(int numBytes) {
    // Receive command from RPi
    ChargerCommand cmd;
    Wire.readBytes((uint8_t*)&cmd, sizeof(cmd));
    
    // Process command
    if (cmd.command == START_CHARGING) {
        startCharging(cmd.currentLimit);
    } else if (cmd.command == STOP_CHARGING) {
        stopCharging();
    }
}
```

### **Raspberry Pi Side (I2C Master):**

```python
# Python dengan smbus library
import smbus

bus = smbus.SMBus(1)  # I2C bus 1

def send_command(charger_address, command):
    # Send command to ESP32
    bus.write_i2c_block_data(charger_address, 0, command_bytes)

def get_status(charger_address):
    # Read status from ESP32
    status_bytes = bus.read_i2c_block_data(charger_address, 0, status_size)
    return parse_status(status_bytes)
```

---

## **Next Steps**

1. **Design Communication Protocol** - Define message formats
2. **Implement ESP32 Communication Module** - Add I2C/Ethernet code
3. **Setup Raspberry Pi** - Install OS, setup development environment
4. **Implement RPi Charger Manager** - Basic communication & control
5. **Add Web Server** - Simple dashboard
6. **Integrate OCPP** - Move OCPP to RPi
7. **Add Payment System** - Payment gateway integration
8. **Add Database** - Transaction storage
9. **Add Analytics** - Reports & statistics
10. **Scale to Multiple Chargers** - Multi-connector support

---

**Ready untuk start?** Mari kita plan implementation step-by-step!








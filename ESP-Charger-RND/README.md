# ESP32 EV Charger Controller (OCPP-ready)

This project uses `ESP32` as the **"brain" for an EV charger**, with:

- **EVSE logic** (state machine, Control Pilot PWM, contactor control)
- **OCPP 1.6J integration** with SteVe backend (remote start/stop, transaction management)
- **I2C LCD Display** for status monitoring (16x2 LCD with PCF8574T adapter)
- **Manual buttons** for start/stop charging (2-press safety feature)
- **OTA (Over-The-Air) Updates** via ArduinoOTA (local network)
- **OCPP Firmware Update** via SteVe backend (remote firmware management)
- **Meter simulation** for testing (can be replaced with real Modbus/CT sensor)

> **IMPORTANT (Safety)**  
> This code is only a framework (prototype). All AC / contactor / RCD connections for the EV charger **must** be designed & inspected by qualified engineers and comply with standards (e.g., IEC 61851, IEC 60364). Do not use this project directly for actual grid installation without proper design and testing.

---

## How to Build (PlatformIO)

1. Ensure you have **VS Code + PlatformIO** or use **CLI**:

   ```bash
   cd ESP-Charger-RND
   pio run
   pio run --target upload
   pio device monitor
   ```

2. Edit `platformio.ini` if needed (different board, libraries, etc.).

---

## Main Files

- `src/HardwareConfig.h`  
  Pin mapping for contactor, Control Pilot, RCD, emergency stop, buttons, LCD.

- `src/EvseController.*`  
  EVSE state machine (Idle / WaitingForCar / WaitingForAuth / Charging / Fault), contactor control, CP PWM generation, and meter reading simulation (can be replaced with real Modbus / CT sensor).

- `src/OcppClient.*`  
  OCPP 1.6J client using MicroOcpp library:
  - WiFi connection management
  - OCPP WebSocket connection to SteVe backend
  - Remote start/stop transaction handling
  - Transaction management and meter value reporting

- `src/LcdDisplay.*`  
  I2C LCD display for status monitoring (state, current, energy, transaction info).

- `src/OtaManager.*`  
  ArduinoOTA for firmware updates via local network.

- `src/OcppFirmwareUpdate.*`  
  OCPP Firmware Management for remote firmware updates from SteVe backend.

- `src/main.cpp`  
  Main loop: initialize all modules, handle button inputs, update LCD, manage OTA updates.

---

## Configuration

### SteVe OCPP Setup

On the SteVe server (e.g., `http://34.143.146.176:8180/steve/manager/signin`):

1. Add a new **Charge Point**
2. Set **ChargeBoxId / Charge Point ID** = `ESP32-CP-01` (or any value, but **must match** the `CHARGE_POINT_ID` in `OcppClient.cpp`)
3. Select **OCPP 1.6J** and set the number of connectors (e.g., 1)

### WiFi & OCPP Client Setup

1. Edit `src/OcppClient.cpp`:
   - Enter `WIFI_SSID` and `WIFI_PASSWORD`
   - Ensure `OCPP_WS_URL` is correct:
     - Example: `ws://34.143.146.176:8180/steve/websocket/CentralSystemService`
   - Ensure `CHARGE_POINT_ID` matches the one in SteVe (default: `ESP32-CP-01`)

2. Edit `src/HardwareConfig.h` if needed:
   - Pin mapping for your hardware
   - LCD I2C address (default: 0x27)
   - Simulated meter values for testing

3. Flash ESP32 and open Serial Monitor (`115200 baud`):
   - You should see WiFi connection logs
   - Once OCPP is connected, `BootNotification` will appear in SteVe UI and the charge point will show as **online**

### OTA (Over-The-Air) Update

To update firmware without USB cable:

1. First upload via USB: `pio run -t upload`
2. Get IP address from Serial Monitor (e.g., `192.168.1.100`)
3. Subsequent uploads via OTA:
   ```bash
   pio run -t upload -e esp32dev --upload-port 192.168.1.100
   ```

**Full documentation:** See `OTA_UPDATE.md`

### OCPP Firmware Update

To update firmware remotely from SteVe backend:

1. Host firmware `.bin` file on HTTP server (GitHub Releases or web server)
2. Trigger `UpdateFirmware` command from SteVe with firmware URL
3. ESP32 will download and install firmware automatically

**Full documentation:** See `OCPP_FIRMWARE_UPDATE.md`

---

## Hardware Setup

See `WIRING_DIAGRAM.md` for complete wiring diagram.

### Pin Mapping (Default)

- **Control Pilot (CP)**:
  - `PIN_CP_PWM` (GPIO 25) → CP PWM output
  - `PIN_CP_SENSE` (GPIO 34) → CP voltage sensing (ADC)

- **Power Control**:
  - `PIN_CONTACTOR` (GPIO 23) → Contactor/relay control

- **Safety Inputs**:
  - `PIN_RCD_STATUS` (GPIO 35) → RCD/RCBO status
  - `PIN_EMERGENCY_STOP` (GPIO 32) → Emergency stop button

- **Manual Buttons**:
  - `PIN_BTN_ON` (GPIO 18) → Start charging button
  - `PIN_BTN_OFF` (GPIO 19) → Stop charging button

- **LCD Display (I2C)**:
  - `PIN_I2C_SDA` (GPIO 21) → I2C Data
  - `PIN_I2C_SCL` (GPIO 22) → I2C Clock
  - Address: `0x27` (default, can be changed according to hardware)

> **IMPORTANT (Safety):** Physical design & safety require serious hardware work. The code here focuses on ESP32 logic and OCPP integration. Ensure all AC / contactor / RCD connections are designed & inspected by qualified engineers according to standards (IEC 61851, IEC 60364).

---

## Features

- ✅ **EVSE State Machine** - IEC 61851 compliant state management (Idle, WaitingForCar, WaitingForAuth, Charging, Fault)
- ✅ **OCPP 1.6J Integration** - Full OCPP client with SteVe backend support
- ✅ **Remote Start/Stop** - Control charging from SteVe backend
- ✅ **Manual Buttons** - Local start/stop with 2-press safety feature
- ✅ **LCD Display** - Real-time status monitoring (state, current, energy, transaction info)
- ✅ **OTA Updates** - Over-the-air firmware updates via ArduinoOTA (local network)
- ✅ **OCPP Firmware Management** - Remote firmware updates from SteVe backend
- ✅ **Meter Simulation** - Testing meter readings (can be replaced with real Modbus/CT sensor)

---

## Documentation

### Hardware Setup
- `WIRING_DIAGRAM.md` - Complete hardware wiring instructions (actual setup)
- `CONTROL_PILOT_SETUP.md` - Control Pilot (CP) circuit setup guide
- `TERMINAL_BLOCK_NO_SPLIT.md` - Terminal block connection guide (no wire splitting)

### Firmware Updates
- `OTA_UPDATE.md` - ArduinoOTA setup and usage guide
- `OCPP_FIRMWARE_UPDATE.md` - OCPP firmware update setup guide

### Future Architecture
- `HYBRID_ARCHITECTURE.md` - Future hybrid (RPi + ESP32) architecture design
- `HYBRID_IMPLEMENTATION_ROADMAP.md` - Implementation roadmap for hybrid architecture
- `RASPBERRY_PI_CHARGER_COMPARISON.md` - ESP32 vs Raspberry Pi comparison

---

## License

See license file for details.

# 📋 Wiring Diagram - ESP32 EV Charger Setup (Actual Hardware)

## 🔌 Hardware Components (Dari Setup Sebenar)

1. **ESP32 DevKit** (dengan green breakout board & terminal blocks)
2. **Hi-Link HLK-10M05** - AC to DC Converter
   - **Confirmed:** Output = **5V DC, 2A** (10W)
   - Input: 100-240V AC, 50-60Hz
   - Perfect untuk 5V relay module (no regulator needed)
3. **4-Channel Relay Module** (Red PCB) - TONGLING JQC-3FF-S-Z
   - **Spec:** 5V DC coil, 10A 250VAC contact rating
   - 4 buah blue relays pada module
4. **GIRAELICA MKS2P** - Magnetic Contactors × 4
   - **Spec:** 240V AC coil, untuk switch AC power ke charger
5. **Button ON** - Green push-button module (3 pins: VCC, OUT, GND)
6. **Button OFF** - Black tactile switch dengan cap (2 pins)
7. **RCBO / MCB** - Circuit Breaker (240V AC input protection)

---

## ⚡ Power Supply Wiring

### Hi-Link Power Module (240V AC → DC)

```
240V AC (Live)   ──→  RCBO/MCB  ──→  Blue Terminal Block "L"
240V AC (Neutral) ──→              Blue Terminal Block "N"
240V AC (Earth)   ──→              (jika ada)

Blue Terminal Block "L" ──→  Hi-Link INPUT L (brown wire)
Blue Terminal Block "N" ──→  Hi-Link INPUT N (blue wire)

Hi-Link OUTPUT +V ──→  Power Distribution Terminal Blocks
Hi-Link OUTPUT GND ──→  Common GND
```

**✅ CONFIRMED - Power Module:**
- **HLK-10M05:** Output **5V DC, 2A** (10W)
- ✅ Perfect untuk 5V relay module (direct connection, no regulator needed)
- ✅ ESP32 boleh guna 5V via VIN pin (onboard regulator akan step down ke 3.3V)

---

## 🔌 Pin Mapping ESP32 (Current Configuration)

Semua pin configuration ada dalam **`src/HardwareConfig.h`**:

| Komponen | ESP32 Pin | Label dalam Code | Wiring Destination |
|----------|-----------|------------------|-------------------|
| **Contactor Control** | **GPIO 23** | `PIN_CONTACTOR` | → 4-channel relay module **IN1** |
| **Control Pilot PWM** | **GPIO 25** | `PIN_CP_PWM` | → (future: CP circuit) |
| **CP Sense (Analog)** | **GPIO 34** | `PIN_CP_SENSE` | → (future: CP voltage divider) |
| **RCD Status** | **GPIO 35** | `PIN_RCD_STATUS` | → (future: RCD status signal) |
| **Emergency Stop** | **GPIO 32** | `PIN_EMERGENCY_STOP` | → (future: E-stop button) |
| **Button ON** | **GPIO 18** | `PIN_BTN_ON` | → Button ON (one terminal) |
| **Button OFF** | **GPIO 19** | `PIN_BTN_OFF` | → Button OFF (one terminal) |

**⚠️ PENTING:** 
- GPIO 34 & 35 adalah input-only (ADC1), tidak boleh set `pinMode(OUTPUT)`.
- Button ON/OFF: sambung antara pin dan **GND** (INPUT_PULLUP, active LOW).

---

## 🔗 Wiring Detail (Berdasarkan Setup Sebenar)

### 1. Power Supply ke ESP32

```
Hi-Link HLK-10M05 +5V  ──→  ESP32 VIN (onboard regulator akan step down ke 3.3V)
                            atau ESP32 5V pin (jika board support direct 5V)
Hi-Link HLK-10M05 GND  ──→  ESP32 GND
```

**NOTA:** ESP32 DevKit biasanya ada onboard regulator (AMS1117) yang boleh handle 5V input pada VIN pin.

---

### 2. Power Supply ke 4-Channel Relay Module

```
Hi-Link HLK-10M05 +5V  ──→  Relay Module VCC (direct connection, perfect match!)
Hi-Link HLK-10M05 GND  ──→  Relay Module GND
```

**✅ PERFECT MATCH:** Relay module TONGLING JQC-3FF-S-Z memerlukan **5V DC** untuk coil, dan HLK-10M05 keluarkan **5V DC** - boleh connect direct tanpa regulator!

---

### 3. ESP32 → 4-Channel Relay Module Control

```
ESP32 GPIO 23 ──→  Relay Module IN1 (input channel 1)
ESP32 GND     ──→  Relay Module GND (common ground)
```

**NOTA:** 
- Relay module biasanya ada jumper untuk set active level (HIGH/LOW)
- Default: **active LOW** (LOW = relay ON, HIGH = relay OFF)
- Jika module kamu **active HIGH**: kena invert logic dalam code atau set jumper

**Check wiring:**
- Wiring dari ESP32 breakout board (terminal block) → Relay module IN1 terminal
- Common GND mesti connect antara ESP32, relay module, dan power supply

---

### 4. Relay Module → GIRAELICA MKS2P Contactor

#### Contactor Coil Control (240V AC):
```
240V AC Live   ──→  GIRAELICA MKS2P Terminal A1 (coil terminal)
240V AC Neutral ──→  Relay Module COM1 (channel 1 common)
Relay Module NO1 ──→  GIRAELICA MKS2P Terminal A2 (coil terminal)
```

**NOTA:** 
- GIRAELICA MKS2P coil rating: **240V AC**
- Relay module contact rating: **10A 250VAC** ✅ (cukup untuk coil current)
- Wiring: Blue wires dari relay module output → GIRAELICA terminal blocks (seperti dalam gambar)

#### Contactor Contact (AC Power Output ke Charger):
```
240V AC Live (main)   ──→  GIRAELICA Contact L1 (input)
240V AC Neutral (main) ──→  GIRAELICA Contact N1 (input)
                          ↓ (bila coil energized, contact close)
GIRAELICA Contact L2 (output) ──→  Charger Connector Live
GIRAELICA Contact N2 (output) ──→  Charger Connector Neutral
```

**⚠️ SAFETY:** 
- Pastikan semua AC wiring ikut standard IEC/BS
- Guna wire gauge yang sesuai untuk current rating (min 2.5mm² untuk 32A)
- Double-check polarity: Live, Neutral, Earth

---

### 5. Button ON & Button OFF

#### Button ON (Green Push-Button Module):
```
ESP32 3.3V  ──→  Green Button Module VCC
ESP32 GPIO 18 ──→  Green Button Module OUT
ESP32 GND   ──→  Green Button Module GND
```

**NOTA Green Button Module:**
- Module ni ada pull-up/down internal (check spec module)
- Biasanya **active LOW**: bila button tekan, OUT → LOW (0V), bila lepas OUT → HIGH (3.3V)
- ESP32 pin configured dengan `INPUT_PULLUP` sebagai backup
- **IMPORTANT:** Jangan connect VCC ke 5V - ESP32 GPIO max 3.3V! Guna **3.3V** sahaja.

#### Button OFF (Black Tactile Switch):
```
ESP32 GPIO 19 ──→  Black Switch Pin 1
Black Switch Pin 2 ──→  GND
```

**NOTA Black Tactile Switch:**
- Simple switch: bila tekan, connect pin 1 ke pin 2 (short ke GND)
- ESP32 pin configured dengan `INPUT_PULLUP` (internal pull-up resistor)
- Bila button ditekan: GPIO 19 → LOW (0V)
- Bila button lepas: GPIO 19 → HIGH (3.3V via pull-up)
- Sambungan: switch antara GPIO pin dan GND (active LOW)

**Wiring:**
- Green button module: connect VCC ke ESP32 3.3V (bukan 5V!), OUT ke GPIO 18, GND ke GND
- Black switch: satu pin ke GPIO 19, satu pin ke GND
- Pastikan common GND antara ESP32 dan kedua-dua button

---

## 📊 Complete Wiring Flow (Text Diagram)

```
┌─────────────────────────────────────────────────────────────┐
│                     240V AC INPUT                            │
│  Live ──┬──→ RCBO ──┬──→ Blue Terminal Block "L"            │
│  Neutral─┼──→       └──→ Blue Terminal Block "N"            │
│  Earth  └──→                                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        │   Blue Terminal Block             │
        │   L ──→ Hi-Link INPUT L (brown)   │
        │   N ──→ Hi-Link INPUT N (blue)    │
        └───────────┬───────────┬───────────┘
                    │           │
        ┌───────────▼───────────▼──────────────┐
        │   Hi-Link HLK-10M05                  │
        │   OUTPUT: 5V DC, 2A                  │
        │   +5V ──→ Power Distribution         │
        │   GND ──→ Common GND                 │
        └───────────┬───────────┬───────────┘
                    │           │
        ┌───────────▼───────────▼──────────────┐
        │         ESP32 DevKit                 │
        │   VIN ← +5V (direct from HLK-10M05) │
        │   GND ← Common GND                   │
        │   3.3V ──→ Green Button VCC          │
        │   GPIO 23 ──→ Relay Module IN1       │
        │   GPIO 18 ← Green Button OUT         │
        │   GPIO 19 ← Black Switch (to GND)    │
        └──────────────────────────────────────┘
                    │
        ┌───────────▼──────────────┐
        │  4-Channel Relay Module  │
        │  VCC: 5V (direct from    │
        │        HLK-10M05 - perfect match!)│
        │  GND: common             │
        │  IN1 ← GPIO 23           │
        │  COM1 ──→ 240V Neutral   │
        │  NO1  ──→ GIRAELICA A2   │
        └───────────┬──────────────┘
                    │
        ┌───────────▼──────────────────────────┐
        │  GIRAELICA MKS2P Contactor           │
        │  A1 ← 240V Live                      │
        │  A2 ← Relay NO1                      │
        │  L1 ← 240V Live (main AC)            │
        │  L2 ──→ Charger Connector Live       │
        │  N1 ← 240V Neutral (main AC)         │
        │  N2 ──→ Charger Connector Neutral    │
        └──────────────────────────────────────┘
```

---

## 🔧 Setup Checklist

- [ ] **Power Supply:** Hi-Link HLK-10M05 connected ke 240V AC (through RCBO)
- [ ] **ESP32 Power:** Hi-Link +5V ke ESP32 VIN/5V pin, Hi-Link GND ke ESP32 GND
- [ ] **Relay Module Power:** Hi-Link +5V ke Relay Module VCC (direct, perfect match!), Hi-Link GND ke Relay Module GND
- [ ] **GPIO 23** → Relay Module IN1
- [ ] **Relay Module COM1** → 240V Neutral
- [ ] **Relay Module NO1** → GIRAELICA MKS2P Terminal A2 (blue wire dari gambar)
- [ ] **240V Live** → GIRAELICA Terminal A1 (coil)
- [ ] **Button ON (Green Module):** ESP32 3.3V → VCC, GPIO 18 → OUT, GND → GND
- [ ] **Button OFF (Black Switch):** GPIO 19 → Switch pin 1, Switch pin 2 → GND
- [ ] **Common GND:** ESP32, relay module, buttons semua connect ke common GND

---

## ⚠️ Safety Notes

1. **240V AC Wiring:**
   - ✅ Pastikan semua AC wiring ikut standard (IEC/BS)
   - ✅ Guna wire gauge yang sesuai untuk current rating (min 2.5mm² untuk 32A)
   - ✅ Double-check polarity: Live, Neutral, Earth
   - ✅ Test dengan multimeter sebelum connect load

2. **RCBO/MCB:**
   - ✅ Install RCBO/MCB sebelum Hi-Link input untuk protection
   - ✅ Rating: 32A atau lebih (ikut charger rating)

3. **Relay Module:**
   - ✅ **PERFECT MATCH:** HLK-10M05 keluarkan 5V, relay module perlu 5V - direct connection!
   - ✅ Check active level: LOW atau HIGH? (check jumper pada relay module)
   - ✅ Rating contact: 10A 250VAC (cukup untuk coil contactor ~20-50mA)

4. **Contactor:**
   - ✅ GIRAELICA MKS2P rating: check current rating untuk AC contact
   - ✅ Pastikan contact rating ≥ charger max current (32A)
   - ✅ Test continuity sebelum connect AC load

5. **Testing Sequence:**
   - ✅ Test tanpa AC power dulu (check LED pada relay module, button response)
   - ✅ Test dengan multimeter: check continuity sebelum connect AC
   - ✅ Test relay click sound bila GPIO 23 HIGH/LOW
   - ✅ Test contactor coil dengan low power load sebelum full load

---

## 📝 Code Configuration

Semua pin configuration ada dalam **`src/HardwareConfig.h`**.

Jika kamu nak tukar pin, edit file tu:

```cpp
static const int PIN_CONTACTOR = 23;    // Relay module IN1
static const int PIN_BTN_ON = 18;       // Button ON
static const int PIN_BTN_OFF = 19;      // Button OFF
```

**Jika relay module active level berbeza:**
- Edit `setContactor()` dalam `src/EvseController.cpp`:
  - Active LOW: `digitalWrite(PIN_CONTACTOR, close ? LOW : HIGH);`
  - Active HIGH: `digitalWrite(PIN_CONTACTOR, close ? HIGH : LOW);`

---

## ✅ Confirmed Hardware

1. **Power Module:** ✅ HLK-10M05 (5V DC, 2A output)
   - Perfect untuk relay module 5V (direct connection)
   - ESP32 boleh guna 5V via VIN pin

2. **Button ON:** ✅ Green push-button module (VCC, OUT, GND)
   - Connect: ESP32 3.3V → VCC, GPIO 18 → OUT, GND → GND
   - **IMPORTANT:** Jangan connect VCC ke 5V! ESP32 GPIO max 3.3V

3. **Button OFF:** ✅ Black tactile switch (2 pins)
   - Connect: GPIO 19 → Switch pin 1, Switch pin 2 → GND
   - ESP32 internal pull-up akan handle logic

## ❓ Remaining Questions

1. **Relay Module Active Level:**
   - Active LOW atau HIGH? (check jumper pada relay module)
   - Biasanya default active LOW - bila GPIO 23 LOW, relay ON

2. **Button Module Specification:**
   - Green button module: active LOW atau HIGH? (check module spec/jumper)
   - Biasanya digital input module active LOW - bila button tekan, OUT → LOW

---

## 🔄 Next Steps

1. ✅ Verify wiring ikut checklist di atas
2. ✅ Confirm power module model dan voltage
3. ✅ Test code upload ke ESP32
4. ✅ Check Serial Monitor untuk debug messages
5. ✅ Test button ON/OFF response
6. ✅ Test relay module control (GPIO 23)
7. ✅ Test contactor switching
8. ✅ Test remote start/stop via SteVe OCPP

---

**Last Updated:** 2024  
**Hardware Config File:** `src/HardwareConfig.h`  
**Code Files:** `src/main.cpp`, `src/EvseController.cpp`

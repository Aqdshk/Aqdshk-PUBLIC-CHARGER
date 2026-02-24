as# Control Pilot Setup - Complete Step-by-Step Guide

Complete guide untuk setup Control Pilot (CP) circuit untuk ESP32 EV Charger.

---

## 📋 Prerequisites

**Hardware yang perlu:**
- ✅ ESP32 DevKit
- ✅ Breadboard
- ✅ Resistors: 1kΩ, 10kΩ, 3.3kΩ (atau 1.2kΩ × 4 kalau guna yang ada)
- ✅ Terminal block (untuk connect CP wire dari charger)
- ✅ Jumper wires
- ✅ Type 2 charger connector dengan CP wire (red wire)

**Software:**
- ✅ Code dah ada dalam project (EvseController.cpp)
- ✅ HardwareConfig.h dah configure pin mapping

---

## 🎯 CP Setup Overview

Control Pilot ada **2 bahagian**:

1. **CP PWM Output** (ESP32 → Vehicle)
   - GPIO 25 generate PWM signal
   - Communicate max charging current kepada vehicle

2. **CP Sense Input** (Vehicle → ESP32)
   - GPIO 34 read CP voltage
   - Detect vehicle connection state (A/B/C/D)

---

## Step 1: Terminal Block Setup

### Connect CP Wire dari Charger ke Terminal Block

**Berdasarkan TERMINAL_BLOCK_NO_SPLIT.md:**

```
Terminal Block (6 terminals):
┌─────────┬─────────┬─────────┐
│    1    │    2    │    3    │  Top Row
└─────────┴─────────┴─────────┘
┌─────────┬─────────┬─────────┐
│    4    │    5    │    6    │  Bottom Row
│         │         │  Red    │ ←── Red Wire (CP dari charger)
│         │         │  Wire   │
└─────────┴─────────┴─────────┘
```

**Setup:**
1. **Terminal 6:** Red Wire (CP dari charger) - dah connect ✅
2. **Terminal 1:** CP_OUT wire + Wire jumper dari Terminal 6
3. **Terminal 4:** CP_IN wire + Wire jumper dari Terminal 6

**Wire Jumper:**
- Terminal 6 → Terminal 1 (untuk CP_OUT)
- Terminal 6 → Terminal 4 (untuk CP_IN)

**✅ Red Wire TIDAK PERLU SPLIT!** Guna wire jumper sahaja.

---

## Step 2: Breadboard Setup - CP PWM Output

### Circuit: GPIO 25 → CP_OUT

```
ESP32 GPIO 25 ──[1kΩ Resistor]──> CP_OUT ──> Terminal 1 ──> Terminal 6 ──> Charger CP
```

### Breadboard Placement:

**Option 1: Guna 1kΩ Resistor (Standard)**
```
Row 11:
Column A: GPIO 25 (ESP32)
Column B: 1kΩ Resistor Leg 1
Column E: 1kΩ Resistor Leg 2 + CP_OUT wire (ke Terminal 1)
```

**Option 2: Guna 1.2kΩ Resistor (Kalau hanya ada 1.2kΩ)**
```
Row 11:
Column A: GPIO 25 (ESP32)
Column B: 1.2kΩ Resistor Leg 1
Column E: 1.2kΩ Resistor Leg 2 + CP_OUT wire (ke Terminal 1)
```

**Note:** 1.2kΩ boleh guna, tapi bukan standard (standard = 1kΩ).

### Wiring:
1. Connect **GPIO 25** ke **Row 11, Column A**
2. Place **1kΩ resistor** (atau 1.2kΩ):
   - Leg 1: Row 11, Column B
   - Leg 2: Row 11, Column E
3. Connect **CP_OUT wire** ke Row 11, Column E
4. Connect **CP_OUT wire** ke **Terminal 1** (Top Row)
5. Connect **wire jumper** dari Terminal 6 ke Terminal 1

**✅ CP PWM Output complete!**

---

## Step 3: Breadboard Setup - CP Sense Input

### Circuit: CP_IN → Voltage Divider → GPIO 34

```
CP_IN (Terminal 4) ──[10kΩ]──┬──> GPIO 34 (ESP32 ADC)
                              │
                           [3.3kΩ]
                              │
                             GND
```

### Voltage Divider Calculation:

**Goal:** Reduce 12V max to 3.3V max (safe for ESP32 ADC)

```
Input: 12V max
Output: 3.3V max

Voltage Divider Formula:
Vout = Vin × (R2 / (R1 + R2))

With R1 = 10kΩ, R2 = 3.3kΩ:
Vout = Vin × (3.3k / (10k + 3.3k))
Vout = Vin × 0.248

For 12V input:
Vout = 12V × 0.248 = 2.98V ✅ (safe for ESP32)
```

### Breadboard Placement:

**Option 1: Guna 10kΩ + 3.3kΩ (Standard)**
```
Row 17:
Column A: CP_IN wire (dari Terminal 4)
Column B: 10kΩ Resistor Leg 1
Column C: 10kΩ Resistor Leg 2 + 3.3kΩ Resistor Leg 1 + GPIO 34 (Junction Point)
Column D: 3.3kΩ Resistor Leg 2
Column E: GND (connect ke ESP32 GND)
```

**Option 2: Guna 1.2kΩ × 4 (Kalau hanya ada 1.2kΩ)**

**Problem:** 1.2kΩ sahaja tak cukup untuk voltage divider yang betul!

**Solution:** Guna combination:
- **R1 = 8 × 1.2kΩ = 9.6kΩ** (8 resistors in series) ≈ 10kΩ
- **R2 = 3 × 1.2kΩ = 3.6kΩ** (3 resistors in series) ≈ 3.3kΩ

**Atau lebih simple:**
- **R1 = 10 × 1.2kΩ = 12kΩ** (10 resistors in series)
- **R2 = 3 × 1.2kΩ = 3.6kΩ** (3 resistors in series)

**Breadboard Layout (dengan 1.2kΩ resistors):**
```
Row 17-26 (10 resistors untuk R1):
Row 17: Column A = CP_IN, Column B = 1.2kΩ Leg 1
Row 18: Column B = 1.2kΩ Leg 2, Column C = 1.2kΩ Leg 1
Row 19: Column C = 1.2kΩ Leg 2, Column D = 1.2kΩ Leg 1
... (continue sampai 10 resistors)
Row 26: Column X = 1.2kΩ Leg 2 → Junction Point

Row 27-29 (3 resistors untuk R2):
Row 27: Junction Point = 3.3kΩ Leg 1, Column Y = 3.3kΩ Leg 2
Row 28: Column Y = 3.3kΩ Leg 1, Column Z = 3.3kΩ Leg 2
Row 29: Column Z = 3.3kΩ Leg 1 → GND
```

**Ini terlalu complicated!** Better beli 10kΩ dan 3.3kΩ resistors.

### Wiring (Standard dengan 10kΩ + 3.3kΩ):

1. Connect **CP_IN wire** ke **Row 17, Column A** (dari Terminal 4)
2. Place **10kΩ resistor**:
   - Leg 1: Row 17, Column B
   - Leg 2: Row 17, Column C (Junction Point)
3. Place **3.3kΩ resistor**:
   - Leg 1: Row 17, Column C (Junction Point - sama dengan 10kΩ Leg 2)
   - Leg 2: Row 17, Column E → GND
4. Connect **GPIO 34** ke **Row 17, Column C** (Junction Point)
5. Connect **CP_IN wire** ke **Terminal 4** (Bottom Row)
6. Connect **wire jumper** dari Terminal 6 ke Terminal 4

**✅ CP Sense Input complete!**

---

## Step 4: Optional - Capacitor untuk Filtering

### Add 100nF Capacitor (Optional tapi Recommended)

```
GPIO 34 ──┬──> (ke voltage divider junction)
          │
          └──[100nF Capacitor]──> GND
```

**Wiring:**
1. Connect **100nF capacitor** dari **GPIO 34** ke **GND**
2. Parallel dengan voltage divider output

**Function:** Filter noise pada ADC reading

**✅ Capacitor complete!**

---

## Step 5: Verify Connections

### Checklist:

**Terminal Block:**
- [ ] Terminal 6: Red Wire (CP dari charger) connected
- [ ] Terminal 1: CP_OUT wire + Wire jumper dari Terminal 6
- [ ] Terminal 4: CP_IN wire + Wire jumper dari Terminal 6

**Breadboard - CP PWM Output:**
- [ ] GPIO 25 → Row 11, Column A
- [ ] 1kΩ resistor: Column B → Column E
- [ ] CP_OUT wire: Column E → Terminal 1

**Breadboard - CP Sense Input:**
- [ ] CP_IN wire: Terminal 4 → Row 17, Column A
- [ ] 10kΩ resistor: Column B → Column C (Junction)
- [ ] 3.3kΩ resistor: Column C (Junction) → Column E (GND)
- [ ] GPIO 34: Column C (Junction)
- [ ] GND: Column E → ESP32 GND

**Optional:**
- [ ] 100nF capacitor: GPIO 34 → GND

---

## Step 6: Code Configuration

### Check HardwareConfig.h:

```cpp
// CP Pin Mapping
static const int PIN_CP_PWM   = 25;  // CP PWM Output
static const int PIN_CP_SENSE  = 34;  // CP Sense Input (ADC)

// CP PWM Parameters
static const int CP_PWM_CHANNEL      = 0;
static const int CP_PWM_FREQ_HZ      = 1000;   // 1 kHz
static const int CP_PWM_RES_BITS     = 10;     // 10-bit resolution

// CP Voltage Thresholds (adjust if needed)
static const float CP_VOLTAGE_STATE_A_MAX = 13.0f;  // ~12V
static const float CP_VOLTAGE_STATE_B_MAX = 10.0f;  // ~9V
static const float CP_VOLTAGE_STATE_C_MAX = 7.0f;   // ~6V
static const float CP_VOLTAGE_STATE_D_MAX = 4.0f;   // ~3V
static const float CP_VOLTAGE_FAULT_MAX   = 0.5f;   // <0.5V

// ADC Calibration (adjust based on voltage divider)
static const float CP_ADC_TO_VOLTAGE = 3.3f / 4095.0f;
// For 10kΩ/3.3kΩ divider: (3.3 / 4095) × (13.3k / 3.3k) = 0.00322
```

**✅ Code dah ready!**

---

## Step 7: Testing

### Upload Code ke ESP32:

```bash
pio run -t upload
```

### Monitor Serial Monitor:

```
[EVSE] CP Current limit: 32A, Duty: 50.0%, ADC duty value: 512
[EVSE] CP Voltage: 12.0V, State: StateA
[EVSE] CP Voltage: 9.0V, State: StateB
[EVSE] CP Voltage: 6.0V, State: StateC
[EVSE] CP Voltage: 3.0V, State: StateD
```

### Test Scenarios:

1. **No Vehicle (State A):**
   - CP voltage: ~12V (atau ~3V kalau guna 3.3V PWM)
   - State: StateA

2. **Vehicle Connected (State B):**
   - Connect vehicle (atau simulate dengan resistor)
   - CP voltage: ~9V (atau ~2.5V kalau guna 3.3V PWM)
   - State: StateB

3. **Vehicle Ready (State C):**
   - Vehicle ready to charge
   - CP voltage: ~6V (atau ~1.6V kalau guna 3.3V PWM)
   - State: StateC

4. **Vehicle Charging (State D):**
   - Vehicle charging
   - CP voltage: ~3V (atau ~0.8V kalau guna 3.3V PWM)
   - State: StateD

---

## Troubleshooting

### Problem: CP Voltage reading salah

**Solution:**
1. Check voltage divider resistors (10kΩ + 3.3kΩ)
2. Calibrate `CP_ADC_TO_VOLTAGE` dalam HardwareConfig.h
3. Measure actual voltage dengan multimeter

### Problem: CP PWM tak function

**Solution:**
1. Check GPIO 25 connection
2. Check 1kΩ resistor
3. Monitor Serial Monitor untuk PWM duty cycle

### Problem: CP Sense tak detect vehicle

**Solution:**
1. Check GPIO 34 connection
2. Check voltage divider circuit
3. Check terminal block connections
4. Verify CP wire dari charger connected

---

## Summary

**Complete CP Setup:**

1. ✅ **Terminal Block:** Connect CP wire dari charger
2. ✅ **CP PWM Output:** GPIO 25 → 1kΩ → CP_OUT → Terminal 1
3. ✅ **CP Sense Input:** CP_IN → 10kΩ/3.3kΩ divider → GPIO 34
4. ✅ **Optional:** 100nF capacitor untuk filtering
5. ✅ **Code:** Dah configure dalam HardwareConfig.h
6. ✅ **Testing:** Upload code dan monitor Serial Monitor

**✅ CP Setup Complete!**

---

## Related Documentation

- `CONTROL_PILOT_SETUP.md` - Detailed CP circuit guide
- `TERMINAL_BLOCK_NO_SPLIT.md` - Terminal block connection guide
- `CP_PWM_EXPLAINED.md` - PWM explanation
- `CP_VOLTAGE_SOURCE.md` - Voltage source explanation
- `CAPACITOR_EXPLANATION.md` - Capacitor guide





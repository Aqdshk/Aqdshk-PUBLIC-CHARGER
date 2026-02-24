# Control Pilot (CP) Hardware Setup Guide

Complete guide for adding Control Pilot circuit to your ESP32 EV Charger breadboard setup.

---

## 📋 Control Pilot Hardware List

### Essential Components for CP Circuit

1. **Resistors**
   - **1x 1kΩ resistor** (CP PWM output current limiting)
   - **1x 10kΩ resistor** (Voltage divider - R1)
   - **1x 3.3kΩ resistor** (Voltage divider - R2)

2. **Capacitors (Optional but Recommended)**
   - **1x 100nF ceramic capacitor** (CP Sense filtering)

3. **LED (for Testing)**
   - **1x LED (any color)** - Visual indicator for CP PWM signal

4. **Jumper Wires**
   - 5-10 pieces for connections

### Optional Components

5. **Oscilloscope or Multimeter** (for testing/debugging)
6. **Variable Power Supply 0-12V** (for testing CP Sense)

**Estimated Cost:** $2-5 USD

---

## 🔌 Control Pilot Pin Mapping

| Function | ESP32 Pin | Type | Notes |
|----------|-----------|------|-------|
| **CP PWM Output** | GPIO 25 | Output | Generates 1 kHz PWM signal |
| **CP Sense Input** | GPIO 34 | ADC Input | Reads CP voltage (0-12V) |

---

## 🔧 Control Pilot Circuit Overview

Control Pilot has TWO parts:

### Part 1: CP PWM Output (ESP32 → EV)
- **Purpose:** Send PWM signal to EV to communicate available charging current
- **Signal:** 1 kHz PWM, duty cycle 0-90% (maps to 6A-63A)

### Part 2: CP Sense Input (EV → ESP32)
- **Purpose:** Detect CP voltage to determine connection state
- **Voltage Levels (IEC 61851):**
  - State A: ~12V (no vehicle)
  - State B: ~9V (vehicle connected, not ready)
  - State C: ~6V (vehicle ready)
  - State D: ~3V (vehicle charging)
- **Needs:** Voltage divider (12V max → 3.3V for ESP32 ADC)

---

## 📐 CP PWM Output Circuit (GPIO 25 → EV)

### Circuit Diagram

```
ESP32 GPIO 25 (PWM Output)
    │
    ├─[1kΩ Resistor]─┐
    │                 │
    │                 ├─> CP_OUT (to EV connector CP pin)
    │                 │
    │                 └─> LED Anode ──> LED Cathode ──> GND
    │                     (optional, for visual feedback)
    │
```

### Breadboard Layout (Top View)

```
┌─────────────────────────────────────────┐
│                                         │
│  ESP32 GPIO 25                         │
│      │                                  │
│      ├─[Resistor 1kΩ]─┬─> CP_OUT       │
│      │                 │                │
│      │                 └─> LED ──> GND  │
│      │                                 │
└─────────────────────────────────────────┘
```

### Step-by-Step Wiring

1. **Place 1kΩ resistor on breadboard**
   - One end connects to ESP32 GPIO 25
   - Other end goes to CP_OUT point

2. **For Testing (Visual Indicator):**
   - Connect LED anode to CP_OUT point (after resistor)
   - Connect LED cathode to GND
   - LED will blink/flicker showing PWM activity

3. **For Real EVSE:**
   - CP_OUT connects to Control Pilot pin in charging connector
   - Remove LED (not needed in real setup)

### Testing CP PWM Output

- **With LED:** LED should flicker/blink (PWM frequency 1 kHz is too fast to see, but you'll see dimmed LED)
- **With Multimeter:** Measure voltage on CP_OUT - should see average voltage based on duty cycle
- **With Oscilloscope:** See clean 1 kHz square wave PWM signal

---

## 📐 CP Sense Input Circuit (EV → GPIO 34)

### Circuit Diagram

```
CP_IN (0-12V from CP line / EV)
    │
    ├─[10kΩ Resistor]─┬─> ESP32 GPIO 34 (ADC)
    │                  │
    │                  └─[3.3kΩ Resistor]─> GND
    │
    └─[100nF Capacitor]─> GND (optional filtering)
```

### Voltage Divider Calculation

**Goal:** Reduce 12V max to 3.3V max (safe for ESP32 ADC)

```
Input Voltage: 12V max
Output Voltage: 3.3V max (ESP32 ADC limit)

Voltage Divider Formula:
Vout = Vin × (R2 / (R1 + R2))

With R1 = 10kΩ, R2 = 3.3kΩ:
Vout = Vin × (3.3k / (10k + 3.3k))
Vout = Vin × (3.3k / 13.3k)
Vout = Vin × 0.248

For 12V input:
Vout = 12V × 0.248 = 2.98V ✅ (safe for ESP32)
```

### Breadboard Layout (Top View)

```
┌─────────────────────────────────────────┐
│                                         │
│  CP_IN (from EV / test source)         │
│      │                                  │
│      ├─[10kΩ Resistor]─┬─> GPIO 34     │
│      │                  │               │
│      │               [3.3kΩ]            │
│      │                  │               │
│      │                  └─> GND         │
│      │                                 │
│      └─[100nF Cap]──────> GND          │
│                                         │
└─────────────────────────────────────────┘
```

### Step-by-Step Wiring

1. **Build Voltage Divider:**
   - Place 10kΩ resistor: CP_IN → middle junction point
   - Place 3.3kΩ resistor: middle junction point → GND
   - Connect middle junction point to ESP32 GPIO 34

2. **Add Filtering (Optional):**
   - Connect 100nF capacitor from GPIO 34 to GND
   - This filters noise from ADC reading

3. **For Testing:**
   - Connect CP_IN to variable power supply (0-12V)
   - Or use jumper wires to simulate different voltages:
     - 12V → State A (no vehicle)
     - 9V → State B (vehicle connected)
     - 6V → State C (vehicle ready)
     - 3V → State D (vehicle charging)

### Testing CP Sense Input

1. **Connect test voltage to CP_IN:**
   - Use variable power supply or voltage source
   - Start with 12V (simulates State A - no vehicle)

2. **Check Serial Monitor:**
   - Code will print CP voltage readings
   - Should see detected CP state

3. **Calibrate if needed:**
   - Adjust `CP_ADC_TO_VOLTAGE` in `HardwareConfig.h`
   - Formula: `CP_ADC_TO_VOLTAGE = 3.3 / 4095 × divider_ratio`
   - With 10kΩ/3.3kΩ divider: `= (3.3 / 4095) × (13.3k / 3.3k) = 0.00322`

---

## 🎯 Complete CP Circuit on Breadboard

### Full Layout

```
╔═══════════════════════════════════════════════════════════════╗
║                    BREADBOARD (Top View)                      ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  ┌──────────────┐                                            ║
║  │   ESP32      │                                            ║
║  │              │                                            ║
║  │ GPIO 25 ─────┼──[1kΩ]──┬── CP_OUT                        ║
║  │              │          │                                 ║
║  │              │          └── LED ── GND                    ║
║  │              │                                            ║
║  │ GPIO 34 ─────┼──┬──[10kΩ]──┬── CP_IN                     ║
║  │              │  │           │                            ║
║  │              │  │        [3.3kΩ]                         ║
║  │              │  │           │                            ║
║  │              │  │           └── GND                      ║
║  │              │  │                                        ║
║  │              │  └──[100nF]── GND                         ║
║  │              │                                            ║
║  │ GND ─────────┼─────────────────────── GND                ║
║  └──────────────┘                                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### Detailed Component Placement

```
Component Placement Guide:

1. ESP32 (Left side of breadboard)
   ├─ GPIO 25 (row A)
   ├─ GPIO 34 (row B)
   └─ GND (row C)

2. CP PWM Circuit (Center-left)
   ├─ 1kΩ resistor: Connect GPIO 25 → Junction 1
   ├─ Junction 1 → CP_OUT (to EV/test)
   └─ LED: Junction 1 → LED anode → LED cathode → GND

3. CP Sense Circuit (Center-right)
   ├─ CP_IN (from EV/test source)
   ├─ 10kΩ resistor: CP_IN → Junction 2
   ├─ 3.3kΩ resistor: Junction 2 → GND
   ├─ Junction 2 → GPIO 34
   └─ 100nF capacitor: GPIO 34 → GND
```

---

## 🔍 Component Specifications

### Resistors

| Value | Purpose | Tolerance | Power Rating |
|-------|---------|-----------|--------------|
| 1kΩ | CP PWM current limiting | ±5% | 1/4W (0.25W) |
| 10kΩ | Voltage divider (R1) | ±5% | 1/4W (0.25W) |
| 3.3kΩ | Voltage divider (R2) | ±5% | 1/4W (0.25W) |

**Recommended:** 1/4W through-hole resistors (standard breadboard size)

### Capacitor

| Value | Type | Purpose | Voltage Rating |
|-------|------|---------|----------------|
| 100nF | Ceramic | ADC filtering | 50V+ |

**Recommended:** Ceramic capacitor (small, easy to place on breadboard)

### LED (for Testing)

| Type | Forward Voltage | Forward Current |
|------|----------------|-----------------|
| Standard LED | ~2V | 20mA |

**Note:** Add 220Ω resistor in series with LED if direct connection (but 1kΩ from GPIO 25 is usually sufficient)

---

## ✅ Step-by-Step Assembly

### Step 1: Prepare Breadboard

1. Place ESP32 on left side of breadboard
2. Connect ESP32 GND to breadboard GND rail
3. Ensure power rails are connected (if using)

### Step 2: CP PWM Output Circuit

1. **Place 1kΩ resistor:**
   - One leg in same row as ESP32 GPIO 25
   - Other leg in adjacent row (create junction point)

2. **Add LED (for testing):**
   - LED anode to junction point (after 1kΩ resistor)
   - LED cathode to GND rail
   - **Note:** LED will show PWM activity (may appear dim/flickering)

3. **Mark CP_OUT point:**
   - Junction point after 1kΩ resistor = CP_OUT
   - In real setup, this connects to EV charging connector CP pin

### Step 3: CP Sense Input Circuit

1. **Build voltage divider:**
   - Place 10kΩ resistor on breadboard
   - One end: CP_IN (will connect to test source/EV)
   - Other end: Junction point (middle of divider)

2. **Add 3.3kΩ resistor:**
   - One end: Junction point (same as 10kΩ connection)
   - Other end: GND rail

3. **Connect to ESP32:**
   - Junction point (middle of divider) → ESP32 GPIO 34

4. **Add filtering capacitor (optional):**
   - 100nF capacitor: One leg to GPIO 34, other leg to GND
   - This smooths ADC readings

### Step 4: Testing Setup

1. **For CP PWM testing:**
   - Power on ESP32
   - Observe LED (should be dim/flickering if PWM active)
   - Use multimeter to measure CP_OUT voltage
   - Use oscilloscope for detailed PWM waveform

2. **For CP Sense testing:**
   - Connect test voltage to CP_IN:
     - 0V → Fault state
     - 3V → State D (charging)
     - 6V → State C (ready)
     - 9V → State B (connected)
     - 12V → State A (no vehicle)
   - Monitor Serial Monitor for CP voltage and state detection

---

## 🔧 Calibration & Configuration

### Code Configuration

Edit `src/HardwareConfig.h`:

```cpp
// CP Voltage thresholds (adjust if needed based on measurements)
static const float CP_VOLTAGE_STATE_A_MAX = 13.0f;  // ~12V
static const float CP_VOLTAGE_STATE_B_MAX = 10.0f;  // ~9V
static const float CP_VOLTAGE_STATE_C_MAX = 7.0f;   // ~6V
static const float CP_VOLTAGE_STATE_D_MAX = 4.0f;   // ~3V
static const float CP_VOLTAGE_FAULT_MAX   = 0.5f;   // <0.5V

// ADC to Voltage conversion factor
// Formula: (3.3V / 4095) × divider_ratio
// For 10kΩ/3.3kΩ divider: (13.3k / 3.3k) = 4.03
static const float CP_ADC_TO_VOLTAGE = (3.3f / 4095.0f) * (13.3f / 3.3f);
// = 0.00322 × 4.03 = 0.01298 (approximately)

// Or measure and calibrate:
// static const float CP_ADC_TO_VOLTAGE = 0.01298f; // Calibrated value
```

### Calibration Procedure

1. **Apply known voltage to CP_IN:**
   - Use 12V power supply
   - Measure actual voltage with multimeter

2. **Read ADC value:**
   - Check Serial Monitor for ADC reading
   - Or add debug code to print raw ADC value

3. **Calculate calibration factor:**
   ```
   CP_ADC_TO_VOLTAGE = Actual_Voltage / ADC_Reading
   
   Example:
   - Applied: 12.0V to CP_IN
   - Measured at GPIO 34: 2.98V (after divider)
   - ADC reading: 3690 (out of 4095)
   - CP_ADC_TO_VOLTAGE = 2.98 / 3690 = 0.000808
   - But this is after divider, so actual CP_IN = 2.98 × (13.3/3.3) = 12.02V ✓
   ```

---

## 📊 Expected Measurements

### CP PWM Output (GPIO 25)

| Current Limit | PWM Duty Cycle | CP_OUT Average Voltage (3.3V logic) |
|---------------|----------------|-------------------------------------|
| 6A | 0% | ~0V |
| 16A | ~16% | ~0.53V |
| 20A | ~25% | ~0.83V |
| 32A | ~50% | ~1.65V |
| 63A | 90% | ~2.97V |

**Note:** These are approximate. Actual voltage depends on load.

### CP Sense Input (GPIO 34 ADC)

| CP State | CP_IN Voltage | After Divider | ADC Reading (approx) |
|----------|---------------|---------------|---------------------|
| State A | 12V | 2.98V | ~3690 |
| State B | 9V | 2.23V | ~2765 |
| State C | 6V | 1.49V | ~1845 |
| State D | 3V | 0.74V | ~920 |
| Fault | <0.5V | <0.12V | ~150 |

---

## ⚠️ Important Notes

1. **Voltage Levels:**
   - CP_IN can be up to 12V
   - ESP32 GPIO max input: 3.3V
   - **ALWAYS use voltage divider for CP_SENSE** (GPIO 34)

2. **PWM Signal:**
   - Frequency: 1 kHz (IEC 61851 standard)
   - Duty cycle: 0-90% (maps to 6A-63A)
   - GPIO 25 outputs 0-3.3V logic level
   - In real EVSE, may need level shifting/buffering

3. **Testing Safety:**
   - Breadboard setup uses low voltages (3.3V, 5V, 12V max)
   - No high-voltage AC on breadboard
   - Real EVSE requires proper isolation and protection

4. **Real EVSE Installation:**
   - All circuits must be designed by qualified engineer
   - Follow IEC 61851, IEC 60364 standards
   - Proper isolation, protection, and safety circuits required

---

## 🧪 Testing Checklist

- [ ] CP PWM circuit assembled (1kΩ resistor + optional LED)
- [ ] CP Sense circuit assembled (voltage divider: 10kΩ + 3.3kΩ)
- [ ] All connections verified with multimeter
- [ ] ESP32 powers up correctly
- [ ] Serial Monitor shows CP readings
- [ ] CP PWM signal visible (LED flickering or oscilloscope)
- [ ] CP Sense detects different voltage levels (test with variable supply)
- [ ] CP state detection works (State A/B/C/D/Fault)
- [ ] Calibration values correct (adjust if needed)

---

## 🔗 Related Documentation

- `HARDWARE_SETUP.md` - Complete hardware setup guide
- `BREADBOARD_WIRING_ASCII.md` - Full breadboard wiring diagram
- `src/HardwareConfig.h` - Pin configuration and CP parameters
- `src/EvseController.cpp` - CP implementation code

---

## 💡 Quick Reference

**CP PWM Output:**
```
GPIO 25 → [1kΩ] → CP_OUT → (to EV connector)
```

**CP Sense Input:**
```
CP_IN → [10kΩ] ─┬→ GPIO 34
                │
             [3.3kΩ]
                │
               GND
```

**Component Cost:** ~$2-5 USD
**Assembly Time:** 15-30 minutes
**Difficulty:** Beginner to Intermediate









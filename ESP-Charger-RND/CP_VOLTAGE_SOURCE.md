# Control Pilot Voltage Source - Dari Charger atau Vehicle?

## Jawapan Pendek: **12V dari CHARGER (EVSE), BUKAN dari vehicle!** ✅

---

## CP Signal Flow (IEC 61851)

### Standard IEC 61851 CP Circuit:

```
EVSE (Charger) Side:
┌─────────────────────────────────┐
│  12V Power Supply               │
│      │                          │
│      ├─[1kΩ Resistor]─┬─> CP_OUT│
│      │                │         │
│      └─[PWM Switch]───┘         │
│                                 │
│  CP_OUT ────────────────────────┼──> CP Wire ──> Vehicle
│                                 │
└─────────────────────────────────┘
                                  │
                                  │
Vehicle Side:                     │
┌─────────────────────────────────┐
│  Vehicle hanya provide          │
│  RESISTANCE, bukan voltage!    │
│                                 │
│  CP_IN ──[Resistor]──> GND      │
│  (Vehicle resistance ubah       │
│   voltage level)                │
└─────────────────────────────────┘
```

**Key Point:**
- **12V dari EVSE (Charger)** - EVSE generate voltage
- **Vehicle hanya provide resistance** - ubah voltage level
- **CP voltage berubah** berdasarkan vehicle connection state

---

## CP Voltage Levels (IEC 61851)

### State A: ~12V (No Vehicle)
```
EVSE: 12V ──[1kΩ]──> CP_OUT ──> (open circuit, no vehicle)
Voltage: ~12V (no load)
```

### State B: ~9V (Vehicle Connected, Not Ready)
```
EVSE: 12V ──[1kΩ]──> CP_OUT ──> Vehicle ──[2.74kΩ]──> GND
Voltage: ~9V (voltage drop due to vehicle resistance)
```

### State C: ~6V (Vehicle Ready)
```
EVSE: 12V ──[1kΩ]──> CP_OUT ──> Vehicle ──[1.3kΩ]──> GND
Voltage: ~6V (lower resistance = lower voltage)
```

### State D: ~3V (Vehicle Charging)
```
EVSE: 12V ──[1kΩ]──> CP_OUT ──> Vehicle ──[0.88kΩ]──> GND
Voltage: ~3V (even lower resistance = even lower voltage)
```

**Vehicle ubah voltage dengan provide different resistance!**

---

## Your ESP32 Setup

### Current Setup (Breadboard):

**Problem:** ESP32 GPIO output = **3.3V**, bukan 12V!

```
ESP32 GPIO 25 ──[1kΩ]──> CP_OUT ──> Vehicle
         │
     (3.3V PWM)
```

**Ini bukan standard IEC 61851!** Standard require 12V.

### Standard Setup (Production):

```
12V Power Supply ──[1kΩ]──> CP_OUT ──> Vehicle
         │
    ESP32 GPIO 25 (PWM control switch)
```

**ESP32 control PWM switch untuk turn 12V on/off, bukan generate 3.3V PWM!**

---

## Voltage Source Summary

### Standard IEC 61851:
- **12V dari EVSE (Charger)** ✅
- Vehicle hanya provide resistance
- CP voltage berubah: 12V → 9V → 6V → 3V

### Your Current Setup:
- **3.3V dari ESP32 GPIO 25** ⚠️ (bukan standard, tapi boleh untuk testing)
- Vehicle masih provide resistance
- CP voltage berubah: 3.3V → ~2.5V → ~1.6V → ~0.8V (scaled down)

---

## For Your Setup

### Current (Breadboard Testing):
- ESP32 GPIO 25 generate 3.3V PWM
- Voltage divider untuk CP Sense (GPIO 34)
- **Boleh function untuk testing**, tapi bukan standard voltage

### Production (Standard IEC 61851):
- Need **12V power supply** untuk CP circuit
- ESP32 control PWM switch (bukan generate voltage)
- CP voltage = 12V (standard)

---

## Answer to Your Question

**"12V tu dari charger or vehicle?"**

**Answer: 12V dari CHARGER (EVSE), BUKAN dari vehicle!**

**Vehicle hanya provide resistance yang ubah voltage level.**

**Dalam setup anda sekarang:**
- ESP32 generate 3.3V PWM (bukan 12V)
- Masih boleh function untuk testing
- Untuk production, perlu 12V power supply

---

## Quick Reference

| Component | Voltage Source | Function |
|-----------|---------------|----------|
| **EVSE (Charger)** | 12V power supply | Generate CP voltage |
| **ESP32 GPIO 25** | 3.3V PWM (current) | Control CP signal |
| **Vehicle** | No voltage! | Provide resistance only |
| **CP Voltage** | Changes based on vehicle resistance | 12V → 9V → 6V → 3V |

**12V = Dari Charger, Bukan dari Vehicle!** ✅





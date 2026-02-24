# Control Pilot: 12V dari Charger & PWM Explained

## Soalan 1: 12V tu dari Charger?

**Ya, betul! 12V dari CHARGER (EVSE), bukan dari vehicle!** ✅

### Standard IEC 61851 CP Circuit:

```
┌─────────────────────────────────────┐
│  CHARGER (EVSE)                     │
│                                     │
│  12V Power Supply ──[1kΩ]──> CP_OUT│
│         │                          │
│    ESP32 GPIO 25                   │
│    (PWM Control Switch)            │
│                                     │
│  CP_OUT ───────────────────────────┼──> CP Wire ──> Vehicle
└─────────────────────────────────────┘
                                     │
                                     │
┌─────────────────────────────────────┐
│  VEHICLE                             │
│                                     │
│  CP_IN ──[Resistance]──> GND        │
│  (Vehicle hanya provide resistance, │
│   bukan voltage!)                  │
└─────────────────────────────────────┘
```

**Key Points:**
- ✅ **12V dari Charger** - Charger ada 12V power supply
- ✅ **Vehicle hanya provide resistance** - ubah voltage level
- ✅ **CP voltage berubah** berdasarkan vehicle connection state

---

## Soalan 2: PWM tu Apa?

**PWM = Pulse Width Modulation** (Modulasi Lebar Denyut)

### Apa itu PWM?

**PWM = Signal yang ON/OFF dengan cepat, macam switch yang buka/tutup berulang-ulang.**

```
PWM Signal:
┌─┐     ┌─┐     ┌─┐     ┌─┐
│ │     │ │     │ │     │ │  ← ON (HIGH)
│ └─────┘ └─────┘ └─────┘ └── ← OFF (LOW)
│
Time ───────────────────────────>
```

**PWM = Signal yang berulang-ulang ON/OFF dengan cepat!**

---

## PWM dalam Control Pilot

### Function PWM dalam CP:

**PWM digunakan untuk communicate "maximum charging current" kepada vehicle.**

### PWM Frequency & Duty Cycle:

**Frequency:** 1 kHz (1000 kali per second ON/OFF)
- Standard IEC 61851: 1 kHz
- ESP32 generate 1 kHz PWM

**Duty Cycle:** Percentage of time signal is ON
- 0% = Selalu OFF (0A)
- 16% = ON 16% of time (16A max)
- 50% = ON 50% of time (32A max)
- 90% = ON 90% of time (63A max)

### PWM Duty Cycle → Current Limit Mapping:

```
Duty Cycle  →  Maximum Current
─────────────────────────────────
0%          →  6A (minimum)
16%         →  16A
25%         →  20A
50%         →  32A
90%         →  63A (maximum)
```

**Vehicle baca PWM duty cycle untuk tahu berapa maximum current boleh charge!**

---

## Visual PWM Example

### 50% Duty Cycle (32A max):

```
Signal:
┌─────┐     ┌─────┐     ┌─────┐
│ ON  │ OFF │ ON  │ OFF │ ON  │
└─────┘     └─────┘     └─────┘
│<───>│     │<───>│     │<───>│
 50%   50%   50%   50%   50%   50%

ON time = 50% of period
OFF time = 50% of period
→ Vehicle tahu: 32A max current
```

### 90% Duty Cycle (63A max):

```
Signal:
┌───────────────┐ ┌───────────────┐
│      ON       │ │      ON       │
└───────────────┘ └───────────────┘
│<─────────────>│ │<─────────────>│
     90%             90%

ON time = 90% of period
OFF time = 10% of period
→ Vehicle tahu: 63A max current
```

---

## Complete CP Circuit dengan PWM

### Standard Setup:

```
┌─────────────────────────────────────┐
│  CHARGER (EVSE)                     │
│                                     │
│  12V Power Supply                   │
│      │                              │
│      ├─[1kΩ Resistor]─┬─> CP_OUT    │
│      │                │             │
│      └─[PWM Switch]───┘             │
│         │                           │
│    ESP32 GPIO 25                   │
│    (Control PWM Switch)            │
│                                     │
│  CP_OUT ────────────────────────────┼──> CP Wire
└─────────────────────────────────────┘
                                     │
                                     │
┌─────────────────────────────────────┐
│  VEHICLE                             │
│                                     │
│  CP_IN ──[Resistance]──> GND        │
│                                     │
│  Vehicle baca PWM duty cycle        │
│  untuk tahu max charging current    │
└─────────────────────────────────────┘
```

**How it works:**
1. **Charger generate 12V** dengan PWM switch
2. **ESP32 control PWM switch** (GPIO 25) untuk set duty cycle
3. **Vehicle baca PWM duty cycle** untuk tahu max current
4. **Vehicle provide resistance** untuk ubah CP voltage (State A/B/C/D)

---

## Your ESP32 Setup

### Current Setup (Breadboard):

```
ESP32 GPIO 25 ──[1kΩ]──> CP_OUT ──> Vehicle
     │
  (3.3V PWM)
```

**ESP32 generate 3.3V PWM langsung dari GPIO 25**
- ✅ Boleh function untuk testing
- ⚠️ Bukan standard (standard require 12V)

### Production Setup (Standard):

```
12V Power Supply ──[1kΩ]──> CP_OUT ──> Vehicle
         │
    ESP32 GPIO 25
    (Control PWM Switch)
```

**ESP32 control switch untuk turn 12V on/off dengan PWM**
- ✅ Standard IEC 61851
- ✅ 12V voltage level

---

## PWM dalam Code

### ESP32 Generate PWM:

```cpp
// Setup PWM channel
ledcSetup(CP_PWM_CHANNEL, 1000, 10);  // 1 kHz, 10-bit resolution
ledcAttachPin(PIN_CP_PWM, CP_PWM_CHANNEL);

// Set duty cycle untuk 32A max (50% duty cycle)
int dutyCycle = 512;  // 50% of 1024 (10-bit)
ledcWrite(CP_PWM_CHANNEL, dutyCycle);
```

**ESP32 generate PWM signal dengan frequency 1 kHz dan duty cycle 0-90%**

---

## Summary

### Soalan 1: 12V tu dari Charger?
**✅ Ya, betul! 12V dari CHARGER (EVSE), bukan dari vehicle!**

### Soalan 2: PWM tu Apa?
**PWM = Pulse Width Modulation**
- Signal yang ON/OFF dengan cepat (1 kHz)
- Duty cycle = percentage of time signal is ON
- Vehicle baca duty cycle untuk tahu max charging current
- 0% = 6A, 16% = 16A, 50% = 32A, 90% = 63A

**PWM = Cara charger communicate max current kepada vehicle!** ✅

---

## Quick Answer

**12V dari Charger?** ✅ **Ya, betul!**

**PWM tu apa?** 
- **PWM = Pulse Width Modulation**
- **Signal ON/OFF dengan cepat (1 kHz)**
- **Duty cycle = percentage ON time**
- **Vehicle baca duty cycle untuk tahu max current**

**PWM = Cara charger cakap kepada vehicle: "Saya boleh bagi maximum 32A!"** ✅





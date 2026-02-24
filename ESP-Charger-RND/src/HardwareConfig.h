#pragma once

#include <Arduino.h>

// ============================
//  Pin mapping & hardware cfg
// ============================
//
// NOTE:
// - Tukar nilai pin ikut PCB / wiring sebenar.
// - Semua pin di sini adalah contoh untuk board ESP32-DevKit.

// Output untuk mengawal contactor / relay utama AC
static const int PIN_CONTACTOR       = 23;

// Output PWM untuk Control Pilot (CP) ke kereta (melalui rangkaian op-amp & resistor)
static const int PIN_CP_PWM          = 25;

// Input analog untuk baca voltage di talian CP (melalui divider & protection)
static const int PIN_CP_SENSE        = 34;

// Input digital status RCD / RCBO (HIGH = OK, LOW = trip)
static const int PIN_RCD_STATUS      = 35;

// Input digital butang Emergency Stop (ACTIVE LOW)
static const int PIN_EMERGENCY_STOP  = 32;

// Butang manual (untuk prototaip / test sahaja)
// PIN_BTN_ON:  Tekan untuk START charging (Green Button Module dengan VCC/OUT/GND)
// PIN_BTN_OFF: Tekan untuk STOP charging (Black Tactile Switch antara pin dan GND)
static const int PIN_BTN_ON          = 18;  // Green Button Module OUT → GPIO 18
static const int PIN_BTN_OFF         = 19;  // Black Tactile Switch → GPIO 19, other pin → GND

// I2C LCD Display (I2C LCD Adapter dengan PCF8574T)
// Standard ESP32 I2C pins:
static const int PIN_I2C_SDA         = 21;  // I2C Data line
static const int PIN_I2C_SCL         = 22;  // I2C Clock line
// I2C LCD Address (biasanya 0x27 atau 0x3F, check dengan I2C scanner)
static const uint8_t LCD_I2C_ADDRESS = 0x27; // Tukar ikut address LCD kamu (0x27 atau 0x3F)
static const int LCD_COLUMNS         = 16;   // 16x2 LCD (biasa)
static const int LCD_ROWS            = 2;    // 16x2 LCD (biasa)

// Channel PWM & parameter untuk CP
static const int CP_PWM_CHANNEL      = 0;
static const int CP_PWM_FREQ_HZ      = 1000;   // 1 kHz typical untuk CP (IEC 61851)
static const int CP_PWM_RES_BITS     = 10;     // 10-bit resolution

// CP Voltage thresholds untuk IEC 61851 state detection (ADC readings)
// NOTE: These values need to be calibrated based on your voltage divider circuit
// Typical CP voltages: State A=12V, State B=9V, State C=6V, State D=3V
// If using voltage divider (e.g., R1=100k, R2=27k), ADC reading = CP_voltage * (27k/(100k+27k)) * (4095/3.3V)
// For 12V CP -> ~1.0V after divider -> ADC ~1240 (assuming 3.3V ref)
static const float CP_VOLTAGE_STATE_A_MAX = 13.0f;  // State A: 12V (no vehicle)
static const float CP_VOLTAGE_STATE_B_MAX = 10.0f;  // State B: 9V (vehicle connected, not ready)
static const float CP_VOLTAGE_STATE_C_MAX = 7.0f;   // State C: 6V (vehicle ready)
static const float CP_VOLTAGE_STATE_D_MAX = 4.0f;   // State D: 3V (vehicle charging)
static const float CP_VOLTAGE_FAULT_MAX   = 0.5f;   // Fault: < 0.5V (short circuit)

// ADC calibration (adjust based on your voltage divider)
// Typical: ESP32 ADC max = 3.3V, 12-bit = 4095 counts
// If using voltage divider ratio, multiply ADC reading by this factor
static const float CP_ADC_TO_VOLTAGE = 3.3f / 4095.0f; // Default: direct ADC reading
// If using voltage divider (e.g., 12V -> 1.0V), adjust:
// static const float CP_ADC_TO_VOLTAGE = (3.3f / 4095.0f) * (12.0f / 1.0f);

// Parameter grid asas
static const float GRID_VOLTAGE      = 230.0f; // volt
static const int   MAX_CURRENT_AMP   = 32;     // arus maks charger (ubah ikut rating, max 63A per IEC 61851)
static const int   MIN_CURRENT_AMP   = 6;      // arus minimum IEC 61851

// Sampling interval untuk meter (ms) – sesuaikan ikut keperluan OCPP MeterValues
// Nota: tulis 10000UL (tanpa pemisah digit) supaya serasi dengan compiler lama.
static const unsigned long METER_SAMPLE_INTERVAL_MS = 10000UL; // 10 s

// Simulation parameters untuk testing (akan diganti dengan real meter reading)
// Untuk testing dengan powerbank/low voltage device, guna current dan voltage yang lebih rendah
static const float SIMULATED_CURRENT_AMP = 1.5f; // Ampere untuk simulation (ubah ikut device test)
static const float SIMULATED_VOLTAGE_V = 5.0f;    // Voltage untuk simulation (ubah ikut device test: 5V untuk powerbank, 230V untuk EV)
// NOTE: Untuk real EV charging, guna CT sensor atau Modbus meter untuk actual reading



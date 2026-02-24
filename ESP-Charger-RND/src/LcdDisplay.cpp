#include "LcdDisplay.h"
#include "EvseController.h"
#include <Wire.h>
#include <cstdio>

void LcdDisplay::begin() {
    // Wait untuk ESP32 fully stabilize
    delay(500);
    
    // Initialize I2C dengan SDA dan SCL pins
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(100000); // Set I2C clock to 100kHz (more stable than default)
    delay(100); // Wait for I2C bus to stabilize
    
    // Initialize I2C LCD dengan address, columns, rows
    lcd = new LiquidCrystal_I2C(LCD_I2C_ADDRESS, LCD_COLUMNS, LCD_ROWS);
    
    // Reinitialize function dengan proper delays
    reinitialize();
    
    Serial.print(F("[LCD] Initialized at 0x"));
    Serial.println(LCD_I2C_ADDRESS, HEX);
}

void LcdDisplay::reinitialize() {
    if (!lcd) return;
    
    // Full re-initialization sequence dengan proper delays
    lcd->init();
    delay(100); // Wait for LCD to stabilize after init
    
    lcd->backlight();
    delay(100); // Wait for backlight to turn on
    
    // Clear display
    lcd->clear();
    delay(50); // Wait for clear to complete
    
    // Display startup message
    lcd->setCursor(0, 0);
    lcd->print("Sayang Elisa comel");
    delay(10);
    
    lcd->setCursor(0, 1);
    lcd->print("                ");  // Clear line 2
    delay(10);
}

void LcdDisplay::loop(EvseController* evse, bool ocppConnected, const char* txIdTag, int txId) {
    unsigned long now = millis();
    
    // Periodic I2C connection check (kurang aggressive - setiap 30 saat)
    // Disable untuk test - uncomment jika perlu
    /*
    if (now - lastReinitCheckMs >= REINIT_CHECK_INTERVAL_MS) {
        lastReinitCheckMs = now;
        if (!checkI2CConnection()) {
            Serial.println(F("[LCD] I2C connection lost, reinitializing..."));
            reinitialize();
            return; // Skip update kali ini, akan update dalam next cycle
        }
    }
    */
    
    // Update display setiap UPDATE_INTERVAL_MS
    if (now - lastUpdateMs >= UPDATE_INTERVAL_MS) {
        lastUpdateMs = now;
        updateDisplay(evse, ocppConnected, txIdTag, txId);
    }
}

bool LcdDisplay::checkI2CConnection() {
    if (!lcd) return false;
    
    // Check I2C connection dengan quick scan
    Wire.beginTransmission(LCD_I2C_ADDRESS);
    byte error = Wire.endTransmission();
    return (error == 0); // 0 = success
}

void LcdDisplay::updateDisplay(EvseController* evse, bool ocppConnected, const char* txIdTag, int txId) {
    if (!lcd || !evse) return;
    
    // Get current state
    EvseState state = evse->getState();
    const char* stateStr = getStateString(state);
    const auto& meter = evse->getLastMeterSample();
    
    // Build display strings
    char line1[17] = {0};
    char line2[17] = {0};
    
    // Line 1: State + OCPP status
    strncpy(line1, stateStr, 12);
    
    // Line 2: Current/Energy or Transaction info
    if (state == EvseState::Charging) {
        snprintf(line2, sizeof(line2), "%.1fA %.2fkWh", meter.current, meter.energy);
    } else {
        if (txId > 0) {
            snprintf(line2, sizeof(line2), "I:%dA TX:%d", evse->getOfferedCurrent(), txId);
        } else {
            snprintf(line2, sizeof(line2), "I:%dA", evse->getOfferedCurrent());
        }
    }
    
    // Update display dengan error handling
    // Try-catch equivalent: check if LCD operations succeed
    lcd->clear();
    
    // Line 1: State
    lcd->setCursor(0, 0);
    lcd->print(line1);
    
    // Add OCPP status (right align)
    lcd->setCursor(14, 0);
    lcd->print(ocppConnected ? "OC" : "--");
    
    // Line 2 - ensure display even after stop
    lcd->setCursor(0, 1);
    lcd->print(line2);
    
    // Force display update untuk ensure text muncul
    // (Some LCD libraries need explicit refresh)
}

const char* LcdDisplay::getStateString(EvseState state) {
    switch (state) {
        case EvseState::Disabled:     return "Disabled";
        case EvseState::Idle:         return "Idle";
        case EvseState::WaitingForCar: return "Waiting Car";
        case EvseState::WaitingForAuth: return "Waiting Auth";
        case EvseState::Charging:     return "Charging";
        case EvseState::Fault:        return "Fault";
        default:                      return "Unknown";
    }
}


#pragma once

#include <Arduino.h>
#include "HardwareConfig.h"
#include "EvseController.h"
#include <LiquidCrystal_I2C.h>

class LcdDisplay {
public:
    void begin();
    void loop(EvseController* evse, bool ocppConnected, const char* txIdTag, int txId);

private:
    LiquidCrystal_I2C* lcd = nullptr;
    unsigned long lastUpdateMs = 0;
    unsigned long lastReinitCheckMs = 0;
    static const unsigned long UPDATE_INTERVAL_MS = 2000; // Update setiap 2 saat (kurang frequent untuk stability)
    static const unsigned long REINIT_CHECK_INTERVAL_MS = 30000; // Check I2C setiap 30 saat (kurang aggressive)
    
    void updateDisplay(EvseController* evse, bool ocppConnected, const char* txIdTag, int txId);
    const char* getStateString(EvseState state);
    bool checkI2CConnection();
    void reinitialize();
};


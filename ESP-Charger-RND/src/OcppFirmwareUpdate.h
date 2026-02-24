#pragma once

#include <Arduino.h>

// OCPP Firmware Update Handler
// Handle UpdateFirmware command dari OCPP server (SteVe)
// Download firmware dari URL dan install menggunakan ESP32 Update library

class OcppFirmwareUpdate {
public:
    // Initialize firmware update service
    // Mesti dipanggil selepas WiFi connected dan sebelum mocpp_initialize
    static void begin();
    
    // Loop function untuk handle firmware download progress
    // Mesti dipanggil dalam main loop()
    static void loop();
    
    // Check kalau firmware update sedang berlaku
    static bool isUpdating();
    
    // Get download progress (0-100)
    static unsigned int getProgress();
};








#pragma once

#include <Arduino.h>

// OTA Manager untuk Over-The-Air firmware update
// Menggunakan ArduinoOTA (built-in ESP32)
// 
// Penggunaan:
// 1. Initialize dengan OtaManager::begin() dalam setup()
// 2. Panggil OtaManager::loop() dalam loop()
// 3. Upload firmware via PlatformIO: pio run -t upload -e esp32dev --upload-port <IP_ADDRESS>
//    Atau guna Arduino IDE: Tools > Port > Network Ports > ESP32 at <IP_ADDRESS>

class OtaManager {
public:
    // Initialize OTA dengan hostname (optional, default = "ESP32-EV-Charger")
    // Password optional untuk security (default = no password)
    static void begin(const char* hostname = "ESP32-EV-Charger", const char* password = nullptr);
    
    // Loop function - mesti dipanggil dalam main loop()
    static void loop();
    
    // Check kalau OTA sedang aktif (updating)
    static bool isUpdating();
    
    // Get current progress (0-100) bila updating
    static unsigned int getProgress();

private:
    static bool initialized;
    static bool updating;
    static unsigned int progress;
};








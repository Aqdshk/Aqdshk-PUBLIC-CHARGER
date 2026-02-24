#include "OtaManager.h"
#include <ArduinoOTA.h>

bool OtaManager::initialized = false;
bool OtaManager::updating = false;
unsigned int OtaManager::progress = 0;

void OtaManager::begin(const char* hostname, const char* password) {
    if (initialized) {
        return;
    }

    Serial.print(F("[OTA] Initializing ArduinoOTA"));
    if (hostname) {
        Serial.print(F(" with hostname: "));
        Serial.print(hostname);
    }
    Serial.println();

    // Set hostname (default: "ESP32-EV-Charger")
    ArduinoOTA.setHostname(hostname);

    // Set password (optional, untuk security)
    if (password && strlen(password) > 0) {
        ArduinoOTA.setPassword(password);
        Serial.println(F("[OTA] Password protection enabled"));
    } else {
        Serial.println(F("[OTA] No password set (unsecured - for development only)"));
    }


    // Callback: Start update
    ArduinoOTA.onStart([]() {
        updating = true;
        progress = 0;
        String type;
        if (ArduinoOTA.getCommand() == U_FLASH) {
            type = "sketch";
        } else { // U_SPIFFS
            type = "filesystem";
        }
        
        // NOTE: Serial print mungkin tidak muncul bila updating
        Serial.print(F("[OTA] Start updating "));
        Serial.println(type);
        
    });

    // Callback: End update
    ArduinoOTA.onEnd([]() {
        updating = false;
        Serial.println(F("\n[OTA] Update completed. Restarting..."));
    });

    // Callback: Progress update
    ArduinoOTA.onProgress([](unsigned int current, unsigned int total) {
        progress = (current * 100) / total;
        
        // Print progress setiap 10%
        static unsigned int lastProgress = 0;
        if (progress >= lastProgress + 10) {
            Serial.print(F("[OTA] Progress: "));
            Serial.print(progress);
            Serial.println(F("%"));
            lastProgress = progress;
        }
    });

    // Callback: Error
    ArduinoOTA.onError([](ota_error_t error) {
        updating = false;
        Serial.print(F("[OTA] Error["));
        Serial.print(error);
        Serial.print(F("]: "));
        
        if (error == OTA_AUTH_ERROR) {
            Serial.println(F("Authentication failed"));
        } else if (error == OTA_BEGIN_ERROR) {
            Serial.println(F("Begin failed"));
        } else if (error == OTA_CONNECT_ERROR) {
            Serial.println(F("Connection failed"));
        } else if (error == OTA_RECEIVE_ERROR) {
            Serial.println(F("Receive failed"));
        } else if (error == OTA_END_ERROR) {
            Serial.println(F("End failed"));
        }
    });

    // Start OTA service
    ArduinoOTA.begin();
    initialized = true;
    
    Serial.print(F("[OTA] Ready for OTA updates"));
    Serial.print(F(" | IP address: "));
    Serial.println(ArduinoOTA.getHostname());
}

void OtaManager::loop() {
    if (initialized) {
        ArduinoOTA.handle();
    }
}

bool OtaManager::isUpdating() {
    return updating;
}

unsigned int OtaManager::getProgress() {
    return progress;
}


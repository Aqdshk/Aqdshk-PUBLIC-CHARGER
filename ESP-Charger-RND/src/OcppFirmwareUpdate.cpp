#include "OcppFirmwareUpdate.h"
#include <MicroOcpp.h>
#include <MicroOcpp/Model/FirmwareManagement/FirmwareService.h>
#include <Update.h>
#include <HTTPClient.h>
#include <WiFi.h>

using namespace MicroOcpp;

static bool updating = false;
static unsigned int progress = 0;
static bool initialized = false;
static FirmwareService *fwService = nullptr;

// HTTP download handler untuk download firmware dari URL
// Note: This is blocking, but that's OK for firmware update
static bool httpDownloadFirmware(const char *location) {
    Serial.print(F("[FW-OCPP] Starting firmware download from: "));
    Serial.println(location);
    
    updating = true;
    progress = 0;
    
    HTTPClient http;
    http.begin(location);
    http.setTimeout(60000); // 60 seconds timeout
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    
    int httpCode = http.GET();
    
    if (httpCode != HTTP_CODE_OK) {
        Serial.print(F("[FW-OCPP] HTTP GET failed, code: "));
        Serial.println(httpCode);
        http.end();
        updating = false;
        return false;
    }
    
    // Get file size
    int contentLength = http.getSize();
    if (contentLength <= 0) {
        Serial.println(F("[FW-OCPP] Invalid content length"));
        http.end();
        updating = false;
        return false;
    }
    
    Serial.print(F("[FW-OCPP] Firmware size: "));
    Serial.print(contentLength);
    Serial.println(F(" bytes"));
    
    // Start ESP32 Update
    if (!Update.begin(contentLength)) {
        Serial.print(F("[FW-OCPP] Update.begin failed: "));
        Serial.println(Update.errorString());
        http.end();
        updating = false;
        return false;
    }
    
    // Download and write firmware (blocking)
    WiFiClient *stream = http.getStreamPtr();
    uint8_t buffer[1024];
    size_t totalWritten = 0;
    
    Serial.println(F("[FW-OCPP] Downloading firmware..."));
    
    while (http.connected() && (totalWritten < (size_t)contentLength)) {
        size_t available = stream->available();
        if (available) {
            size_t bytesToRead = (available > sizeof(buffer)) ? sizeof(buffer) : available;
            size_t bytesRead = stream->readBytes(buffer, bytesToRead);
            
            if (bytesRead > 0) {
                size_t bytesWritten = Update.write(buffer, bytesRead);
                if (bytesWritten != bytesRead) {
                    Serial.print(F("[FW-OCPP] Write failed, written: "));
                    Serial.print(bytesWritten);
                    Serial.print(F(", expected: "));
                    Serial.println(bytesRead);
                    Update.abort();
                    http.end();
                    updating = false;
                    return false;
                }
                
                totalWritten += bytesWritten;
                progress = (totalWritten * 100) / contentLength;
                
                // Print progress setiap 10%
                static unsigned int lastProgress = 0;
                if (progress >= lastProgress + 10) {
                    Serial.print(F("[FW-OCPP] Progress: "));
                    Serial.print(progress);
                    Serial.println(F("%"));
                    lastProgress = progress;
                }
            }
        } else {
            delay(10);
        }
    }
    
    http.end();
    
    if (totalWritten != (size_t)contentLength) {
        Serial.print(F("[FW-OCPP] Download incomplete, got: "));
        Serial.print(totalWritten);
        Serial.print(F(", expected: "));
        Serial.println(contentLength);
        Update.abort();
        updating = false;
        return false;
    }
    
    // Finish update
    if (Update.end()) {
        Serial.println(F("[FW-OCPP] Firmware download completed successfully"));
        progress = 100;
        updating = false; // Download done, install will be triggered separately
        return true;
    } else {
        Serial.print(F("[FW-OCPP] Update.end failed: "));
        Serial.println(Update.errorString());
        updating = false;
        return false;
    }
}

// Installation handler - restart ESP32 selepas download complete
static bool installFirmware(const char *location) {
    Serial.println(F("[FW-OCPP] Installing firmware..."));
    
    // Firmware dah downloaded dan verified dalam httpDownloadFirmware()
    // Sekarang restart ESP32 untuk apply new firmware
    Serial.println(F("[FW-OCPP] Firmware ready, restarting ESP32 in 2 seconds..."));
    delay(2000);
    ESP.restart();
    
    return true; // Won't reach here
}

void OcppFirmwareUpdate::begin() {
    if (initialized) {
        return;
    }
    
    Serial.println(F("[FW-OCPP] Initializing OCPP Firmware Management..."));
    
    // Get FirmwareService - will auto-create if not exists
    fwService = getFirmwareService();
    if (!fwService) {
        Serial.println(F("[FW-OCPP] ERROR: Failed to get FirmwareService"));
        return;
    }
    
    // Setup custom HTTP download handler (override default FTP)
    fwService->setOnDownload(httpDownloadFirmware);
    
    // Setup installation handler
    fwService->setOnInstall(installFirmware);
    
    // Setup download status (optional, for better status reporting)
    fwService->setDownloadStatusInput([]() -> DownloadStatus {
        // Download status is managed by FirmwareService internally
        // We just need to provide status when asked
        if (updating && Update.isRunning()) {
            return DownloadStatus::NotDownloaded; // Still downloading
        } else if (updating && !Update.isRunning() && progress == 100) {
            return DownloadStatus::Downloaded; // Download complete
        } else {
            return DownloadStatus::NotDownloaded;
        }
    });
    
    // Setup installation status
    fwService->setInstallationStatusInput([]() -> InstallationStatus {
        // If we reach here, installation already triggered restart
        return InstallationStatus::NotInstalled;
    });
    
    initialized = true;
    Serial.println(F("[FW-OCPP] Firmware Management initialized (HTTP download enabled)"));
}

void OcppFirmwareUpdate::loop() {
    // FirmwareService loop is handled by MicroOcpp internally
    // Download is blocking and handled in httpDownloadFirmware()
}

bool OcppFirmwareUpdate::isUpdating() {
    return updating || Update.isRunning();
}

unsigned int OcppFirmwareUpdate::getProgress() {
    return progress;
}


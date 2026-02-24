#include <Arduino.h>

#include "HardwareConfig.h"
#include "EvseController.h"
#include "OcppClient.h"
#include "LcdDisplay.h"
#include "OtaManager.h"
#include "OcppFirmwareUpdate.h"
#include <MicroOcpp.h>  // Untuk getTransactionIdTag() dan isTransactionActive()
#include <WiFi.h>       // Untuk check WiFi status dalam setup()

EvseController evse;
OcppClient ocpp;
LcdDisplay lcd;

void printBanner() {
    Serial.println();
    Serial.println(F("========================================"));
    Serial.println(F("   Sayang Elisa        "));
    Serial.println(F("========================================"));
    Serial.println();
}

void setup() {
    Serial.begin(115200);
    delay(2000); // Delay for ESP32 to stabilize

    printBanner();

    // Konfigurasi butang manual (pull-up dalaman, butang ke GND, active LOW)
    pinMode(PIN_BTN_ON, INPUT_PULLUP);
    pinMode(PIN_BTN_OFF, INPUT_PULLUP);

    Serial.println(F("[MAIN] Initializing EVSE controller ..."));
    evse.begin();
    delay(500); // Small delay between initializations

    Serial.println(F("[MAIN] Initializing LCD display ..."));
    delay(500); // Delay before LCD initialization
    lcd.begin();
    delay(1500); // Allow LCD time to fully initialize and display startup message

    Serial.println(F("[MAIN] Initializing OCPP client ..."));
    ocpp.begin(&evse);

    // Initialize OCPP Firmware Update (HTTP download from OCPP server)
    Serial.println(F("[MAIN] Initializing OCPP Firmware Management..."));
    OcppFirmwareUpdate::begin();

    // Initialize ArduinoOTA after WiFi is connected (via OCPP)
    // OTA requires WiFi to be connected first
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(F("[MAIN] Initializing OTA ..."));
        OtaManager::begin("ESP32-EV-Charger"); // Optional: add password for security
        // OtaManager::begin("ESP32-EV-Charger", "your_ota_password"); // Uncomment and set password for security
    } else {
        Serial.println(F("[MAIN] WiFi not connected, OTA disabled"));
    }

    Serial.println(F("[MAIN] Setup complete."));
}

void loop() {
    // Handle OTA updates (mesti dipanggil frequently)
    OtaManager::loop();
    
    // Handle OCPP firmware updates
    OcppFirmwareUpdate::loop();
    
    // Skip normal operation during OTA or OCPP firmware update to avoid conflicts
    if (OtaManager::isUpdating() || OcppFirmwareUpdate::isUpdating()) {
        delay(10); // Give CPU time for updates
        return;
    }
    
    // Process OCPP first (remote commands) before state machine
    ocpp.loop();
    evse.loop();

    // Update LCD display
    const char* txIdTag = getTransactionIdTag();
    int txId = 0;
    auto tx = getTransaction();
    if (tx) {
        txId = tx->getTransactionId();
    }
    lcd.loop(&evse, ocpp.isConnected(), txIdTag ? txIdTag : "None", txId);

    // Manual control: 2 separate buttons for start/stop charging
    // Connection: button between pin and GND (INPUT_PULLUP, active LOW)
    
    // Get current time once for all button checks
    unsigned long now = millis();
    
    // Button ON (Start Charging) - Safety feature: 2-press required
    // Press 1: Idle -> WaitingForAuth (authorization requested)
    // Press 2: WaitingForAuth -> Charging (authorization granted)
    static int lastBtnOnState = HIGH;
    static unsigned long lastPressOnTime = 0;
    int curBtnOnState = digitalRead(PIN_BTN_ON);
    
    // Detect button press (handle both active LOW and active HIGH)
    if ((lastBtnOnState == HIGH && curBtnOnState == LOW) ||  // Active LOW
        (lastBtnOnState == LOW && curBtnOnState == HIGH)) {  // Active HIGH
        // Debounce: minimum 200ms between button presses
        if (now - lastPressOnTime > 200) {
            lastPressOnTime = now;
            Serial.print(F("[MAIN] Button ON pressed | State="));
            Serial.println((int)evse.getState());
            evse.startChargingRequest();
            ocpp.beginTransaction(nullptr);
        }
    }
    lastBtnOnState = curBtnOnState;

    // Button OFF (Stop Charging) - Immediate stop
    static int lastBtnOffState = HIGH;
    static unsigned long lastPressOffTime = 0;
    int curBtnOffState = digitalRead(PIN_BTN_OFF);
    
    // Detect button press (handle both active LOW and active HIGH)
    if ((lastBtnOffState == HIGH && curBtnOffState == LOW) ||  // Active LOW
        (lastBtnOffState == LOW && curBtnOffState == HIGH)) {  // Active HIGH
        // Debounce: minimum 200ms between button presses
        if (now - lastPressOffTime > 200) {
            lastPressOffTime = now;
            Serial.println(F("[MAIN] Button OFF pressed: STOP charging"));
            evse.stopChargingRequest();
            ocpp.endTransaction();
        }
    }
    lastBtnOffState = curBtnOffState;

    // Status print every 5 seconds
    static unsigned long lastPrint = 0;
    if (now - lastPrint > 5000) {
        lastPrint = now;

        EvseState st = evse.getState();
        const char *stateStr = "";
        switch (st) {
            case EvseState::Disabled:      stateStr = "Disabled"; break;
            case EvseState::Idle:          stateStr = "Idle"; break;
            case EvseState::WaitingForCar: stateStr = "WaitingForCar"; break;
            case EvseState::WaitingForAuth:stateStr = "WaitingForAuth"; break;
            case EvseState::Charging:      stateStr = "Charging"; break;
            case EvseState::Fault:         stateStr = "Fault"; break;
        }

        const auto &m = evse.getLastMeterSample();

        // Check transaction status
        const char *txIdTag = getTransactionIdTag();
        bool txActive = isTransactionActive();
        
        Serial.print(F("[STATUS] State="));
        Serial.print(stateStr);
        Serial.print(F("  I_offered="));
        Serial.print(evse.getOfferedCurrent());
        Serial.print(F("A  I_meas="));
        Serial.print(m.current, 1);
        Serial.print(F("A  E="));
        Serial.print(m.energy, 3);
        Serial.print(F("kWh  TX="));
        if (txActive && txIdTag) {
            Serial.print(F("Active("));
            Serial.print(txIdTag);
            Serial.print(F(")"));
        } else {
            Serial.print(F("None"));
        }
        Serial.println();
    }

    delay(10); // Reduce CPU load
}
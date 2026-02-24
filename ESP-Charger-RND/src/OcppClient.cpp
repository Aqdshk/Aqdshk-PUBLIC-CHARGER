#include "OcppClient.h"
#include "EvseController.h"
#include "HardwareConfig.h"

#include <WiFi.h>

// ==============================
//  WiFi & OCPP configuration
// ==============================
//
// EDIT: masukkan SSID, password dan ID charge point yang sama dengan
// yang kau set dalam steve (`ChargeBoxId`).

static const char *WIFI_SSID     = "MESRA DECO";
static const char *WIFI_PASSWORD = "mesb1234";

// WebSocket URL ke pelayan steve (OCPP 1.6J)
// Contoh asas MicroOcpp: ws://host:port/steve/websocket/CentralSystemService
// Charge Point ID dihantar berasingan, jadi TIDAK perlu tambah di hujung URL.
static const char *OCPP_WS_URL   = "ws://34.143.146.176:8180/steve/websocket/CentralSystemService";

// MESTI sama dengan ChargeBoxId dalam konfigurasi steve
static const char *CHARGE_POINT_ID = "ESP32-CP-01";

// IdTag untuk button manual transaction
// NOTE: IdTag ni MESTI valid dalam steve (dah register dalam OCPP Tags)
// Kalau idTag invalid, StartTransaction akan reject, tapi charger masih boleh charging
// Untuk remote stop, idTag mesti valid supaya transaction berjaya
// 
// IdTags yang valid dalam steve:
//   - TESTCARD01
//   - BUTTON001  ← Recommended untuk button manual
//   - TEST001
static const char *BUTTON_IDTAG = "BUTTON001"; // Guna idTag yang dah register dalam steve

// Guna MicroOcpp sebagai client OCPP
#include <MicroOcpp.h>

void OcppClient::begin(EvseController *evse) {
    evseCtrl = evse;

    Serial.println(F("[OCPP] Initializing WiFi ..."));
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int retry = 0;
    while (WiFi.status() != WL_CONNECTED && retry < 60) { // ~30s timeout
        delay(500);
        Serial.print('.');
        retry++;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print(F("[OCPP] WiFi connected, IP: "));
        Serial.println(WiFi.localIP());
    } else {
        Serial.println(F("[OCPP] WiFi connect FAILED"));
        return;
    }

    // =============================
    //  Integrasi MicroOcpp (OCPP 1.6J)
    // =============================
    //
    // mocpp_initialize akan buka WebSocket ke pelayan steve dan uruskan
    // BootNotification, Heartbeat, RemoteStartTransaction, dsb.
    // Kita akan guna ocppPermitsCharge() dalam loop untuk ON/OFF contactor.

    mocpp_initialize(OCPP_WS_URL, CHARGE_POINT_ID, "ESP32 Charger", "YourCompany");

    ocppConnected = true;
}

void OcppClient::loop() {
    mocpp_loop();

    if (!evseCtrl) return;
    
    // Monitor transaction state change untuk detect remote start
    static bool lastTxActive = false;
    static bool initialized = false;
    
    // Initialize pada first run
    if (!initialized) {
        lastTxActive = isTransactionActive();
        initialized = true;
        Serial.print(F("[OCPP] Initial transaction state: "));
        Serial.println(lastTxActive ? "Active" : "None");
    }
    
    // Check transaction state change
    bool currentTxActive = isTransactionActive();
    
    if (currentTxActive && !lastTxActive) {
        // New transaction started (boleh jadi dari remote start atau button)
        auto tx = getTransaction();
        if (tx) {
            // Check kalau ini remote start (transaction ada tapi EVSE belum charging)
            EvseState evseState = evseCtrl->getState();
            if (evseState != EvseState::Charging) {
                // Remote start detected - start charging
                Serial.println(F("[OCPP] Remote transaction started - starting charger"));
                Serial.print(F("[OCPP] Transaction ID: "));
                Serial.println(tx->getTransactionId());
                evseCtrl->startChargingRemote();
            }
        }
    } else if (!currentTxActive && lastTxActive) {
        // Transaction stopped
        Serial.println(F("[OCPP] Transaction stopped - stopping charger"));
        evseCtrl->stopChargingRequest();
    }
    
    lastTxActive = currentTxActive;
    
    // Also monitor ocppPermitsCharge() untuk additional safety
    static bool lastOcppPermit = false;
    bool currentPermit = ocppPermitsCharge();
    
    if (!currentPermit && lastOcppPermit) {
        // OCPP permission revoked (additional safety check)
        Serial.println(F("[OCPP] OCPP permission revoked - stopping charger"));
        evseCtrl->stopChargingRequest();
    }
    
    lastOcppPermit = currentPermit;
}

// Note: Remote start/stop is handled automatically in loop() via transaction state monitoring
// These functions are kept for potential future use but are not currently called
void OcppClient::onRemoteStartTransaction() {
    if (!evseCtrl) return;

    Serial.println(F("[OCPP] RemoteStartTransaction received"));

    // Set current limit (can be read from OCPP message in future)
    int limitA = 16;
    evseCtrl->setCurrentLimit(limitA);
    
    // Use startChargingRemote() to bypass safety feature (direct start)
    Serial.println(F("[OCPP] Calling startChargingRemote() from onRemoteStartTransaction"));
    evseCtrl->startChargingRemote();
}

void OcppClient::onRemoteStopTransaction() {
    if (!evseCtrl) return;

    Serial.println(F("[OCPP] RemoteStopTransaction received"));
    evseCtrl->stopChargingRequest();
}

void OcppClient::beginTransaction(const char *idTag) {
    if (!idTag) {
        idTag = BUTTON_IDTAG; // guna default kalau idTag null
    }
    
    // Check kalau ada transaction aktif dulu
    if (isTransactionActive()) {
        Serial.println(F("[OCPP] WARN: Transaction already active, skip begin"));
        return;
    }
    
    Serial.print(F("[OCPP] Starting transaction with idTag: "));
    Serial.println(idTag);
    
    // Use beginTransaction_authorized() to skip local authorization check
    // SteVe will still validate idTag in StartTransaction response
    // If idTag invalid, transaction will reject but charger can still charge
    auto tx = beginTransaction_authorized(idTag);
    if (tx) {
        Serial.println(F("[OCPP] Transaction process started"));
        Serial.println(F("[OCPP] Waiting for StartTransaction response from steve..."));
    } else {
        Serial.println(F("[OCPP] ERROR: Failed to create transaction process"));
    }
}

void OcppClient::endTransaction() {
    // Check kalau ada transaction aktif
    if (!isTransactionActive()) {
        Serial.println(F("[OCPP] No active transaction to stop"));
        return;
    }
    
    Serial.println(F("[OCPP] Stopping transaction"));
    
    // Trigger StopTransaction in MicroOcpp
    // stopTransaction() will send StopTransaction to SteVe
    bool result = stopTransaction(nullptr, nullptr, nullptr, nullptr, 0);
    if (result) {
        Serial.println(F("[OCPP] StopTransaction request sent"));
    } else {
        Serial.println(F("[OCPP] WARN: Failed to send StopTransaction"));
    }
}
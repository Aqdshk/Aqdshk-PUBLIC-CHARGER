#include "OcppClient.h"
#include "EvseController.h"
#include "HardwareConfig.h"
#include "EvseConfig.h"  // WiFi & OCPP config (avoids Windows build_flags quoting issues)

#include <WiFi.h>
#include <Arduino.h>

// ==============================
//  WiFi & OCPP configuration
// ==============================
// EvseConfig.h defines EV_* macros. Fallbacks below if not defined.
#ifndef EV_WIFI_SSID
#define EV_WIFI_SSID "CHANGE_WIFI_SSID"
#endif

#ifndef EV_WIFI_PASSWORD
#define EV_WIFI_PASSWORD "CHANGE_WIFI_PASSWORD"
#endif

#ifndef EV_OCPP_HOST
#define EV_OCPP_HOST "192.168.0.100"
#endif

#ifndef EV_OCPP_PORT
#define EV_OCPP_PORT 9000
#endif

#ifndef EV_OCPP_USE_TLS
#define EV_OCPP_USE_TLS 0
#endif

// Optional prefix before charge point id.
// Example for custom endpoint path:
//   EV_OCPP_PATH_PREFIX "ocpp"
// resulting URL: ws://host:port/ocpp/<cpid>?token=...
#ifndef EV_OCPP_PATH_PREFIX
#define EV_OCPP_PATH_PREFIX ""
#endif

#ifndef EV_OCPP_TOKEN
#define EV_OCPP_TOKEN ""
#endif

// Must match charge point id expected on backend
#ifndef EV_CHARGE_POINT_ID
#define EV_CHARGE_POINT_ID "ESP32-CP-01"
#endif

// IdTag untuk button manual transaction
// NOTE: IdTag ni MESTI valid dalam steve (dah register dalam OCPP Tags)
// Kalau idTag invalid, StartTransaction akan reject, tapi charger masih boleh charging
// Untuk remote stop, idTag mesti valid supaya transaction berjaya
// 
// IdTags yang valid dalam steve:
//   - TESTCARD01
//   - BUTTON001  ← Recommended untuk button manual
//   - TEST001
#ifndef EV_BUTTON_IDTAG
#define EV_BUTTON_IDTAG "BUTTON001"
#endif

static const char *WIFI_SSID = EV_WIFI_SSID;
static const char *WIFI_PASSWORD = EV_WIFI_PASSWORD;
static const char *CHARGE_POINT_ID = EV_CHARGE_POINT_ID;
static const char *BUTTON_IDTAG = EV_BUTTON_IDTAG;
static String OCPP_WS_URL;

// Guna MicroOcpp sebagai client OCPP
#include <MicroOcpp.h>

static String buildOcppWsUrl() {
    String scheme = (EV_OCPP_USE_TLS == 1) ? "wss://" : "ws://";
    String host = String(EV_OCPP_HOST);
    String pathPrefix = String(EV_OCPP_PATH_PREFIX);
    pathPrefix.trim();
    while (pathPrefix.startsWith("/")) {
        pathPrefix.remove(0, 1);
    }
    while (pathPrefix.endsWith("/")) {
        pathPrefix.remove(pathPrefix.length() - 1);
    }

    String path = "/";
    if (pathPrefix.length() > 0) {
        path += pathPrefix + "/";
    }
    path += CHARGE_POINT_ID;

    String url = scheme + host + ":" + String(EV_OCPP_PORT) + path;
    String token = String(EV_OCPP_TOKEN);
    token.trim();
    if (token.length() > 0) {
        url += "?token=" + token;
    }
    return url;
}

void OcppClient::begin(EvseController *evse) {
    evseCtrl = evse;

    if (String(WIFI_SSID) == "CHANGE_WIFI_SSID") {
        Serial.println(F("[OCPP] WARNING: EV_WIFI_SSID not configured"));
    }
    if (String(WIFI_PASSWORD) == "CHANGE_WIFI_PASSWORD") {
        Serial.println(F("[OCPP] WARNING: EV_WIFI_PASSWORD not configured"));
    }

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
    OCPP_WS_URL = buildOcppWsUrl();
    Serial.print(F("[OCPP] WS URL: "));
    Serial.println(OCPP_WS_URL);
    Serial.print(F("[OCPP] Charge Point ID: "));
    Serial.println(CHARGE_POINT_ID);

    mocpp_initialize(OCPP_WS_URL.c_str(), CHARGE_POINT_ID, "ESP32 Charger", "YourCompany");

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
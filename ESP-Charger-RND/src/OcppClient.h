#pragma once

#include <Arduino.h>

class EvseController;

// OCPP Client wrapper untuk sambungan ke SteVe OCPP server
// Menggunakan MicroOcpp library untuk OCPP 1.6J protocol
class OcppClient {
public:
    void begin(EvseController *evse);
    void loop();

    // Check OCPP connection status
    bool isConnected() const { return ocppConnected; }

    // Start OCPP transaction (idTag must be valid in SteVe)
    // If idTag is nullptr, uses default BUTTON_IDTAG
    void beginTransaction(const char *idTag = nullptr);
    void endTransaction();

private:
    EvseController *evseCtrl = nullptr;
    bool ocppConnected = false;

    void onRemoteStartTransaction();
    void onRemoteStopTransaction();
};




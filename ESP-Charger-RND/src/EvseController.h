#pragma once

#include <Arduino.h>
#include "HardwareConfig.h"

// State asas untuk EVSE (charger)
enum class EvseState {
    Disabled,
    Idle,
    WaitingForCar,
    WaitingForAuth,
    Charging,
    Fault
};

// IEC 61851 Control Pilot states (CP voltage levels)
enum class CpState {
    StateA,  // ~12V: No vehicle connected
    StateB,  // ~9V:  Vehicle connected, not ready to charge
    StateC,  // ~6V:  Vehicle ready, ventilation not required
    StateD,  // ~3V:  Vehicle ready, ventilation required OR charging
    Fault    // <0.5V: Short circuit or fault
};

// Struktur mudah untuk data meter (boleh dihubungkan ke Modbus / pulse meter sebenar)
struct EvseMeterSample {
    float voltage = GRID_VOLTAGE;
    float current = 0.0f;   // ampere
    float power   = 0.0f;   // watt
    float energy  = 0.0f;   // kWh terkumpul
};

class EvseController {
public:
    void begin();
    void loop();

    // Kawalan daripada OCPP / UI
    void setEnabled(bool en);
    void setCurrentLimit(int amps);       // had arus dari OCPP / config
    void startChargingRequest();          // Manual button press (2-press safety feature)
    void startChargingRemote();           // Remote start dari OCPP (bypass safety, direct start)
    void stopChargingRequest();           // panggil bila StopTransaction / user stop

    EvseState getState() const { return state; }
    int getOfferedCurrent() const { return offeredCurrentA; }
    const EvseMeterSample &getLastMeterSample() const { return lastSample; }

private:
    EvseState state = EvseState::Disabled;
    bool chargeRequested = false;
    bool stopRequested   = false;
    int  offeredCurrentA = 16;

    unsigned long lastMeterSampleMs = 0;
    unsigned long lastEnergyUpdateMs = 0;   // untuk pengiraan tenaga (kWh)
    EvseMeterSample lastSample;

    void updateCpPwm();
    void setContactor(bool close);
    bool isCarConnected();
    bool isSafetyOk();
    void sampleMeter();
    
    // Control Pilot (CP) functions
    float readCpVoltage();
    CpState getCpState();
};





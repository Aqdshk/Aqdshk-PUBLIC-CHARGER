# PlagSini — OCPP 1.6J Integration Guide

**Document Version:** 1.0
**Date:** 1 July 2026
**Issued by:** C Zero Sdn Bhd (PlagSini EV Charging Platform)
**Audience:** Charger hardware vendors integrating with PlagSini CSMS

---

## 1. Document control

| Field | Value |
|---|---|
| **Operator** | C Zero Sdn Bhd |
| **Trading brand** | PlagSini |
| **Protocol** | OCPP 1.6J (JSON over WebSocket) |
| **Specification reference** | Open Charge Alliance — OCPP 1.6 Edition 2 |
| **Public spec URL** | https://www.openchargealliance.org/protocols/ocpp-16/ |
| **Production CSMS (WSS, recommended)** | wss://charger.czeros.tech/ocpp/{charge_point_id} — port 443, TLS-terminated via nginx |
| **Production CSMS (WS, fallback)** | ws://charger.czeros.tech:9000/{charge_point_id} — port 9000, plain-text (only for firmware that cannot do TLS) |
| **Testing CSMS** | Same endpoints (test-mode charge points assigned per partner) |
| **Primary contact** | Aqid — aqidishak28@gmail.com |
| **Technical contact** | engineering@plagsini.com |

---

## 2. Protocol overview

PlagSini implements the **Central System** role per OCPP 1.6J.

- Transport: **WebSocket Secure (wss://)** — TLS 1.2 or higher
- Message format: **JSON** (per OCPP 1.6J specification)
- Framing: **OCPP Call / CallResult / CallError** structure
- Sub-protocol header required: `Sec-WebSocket-Protocol: ocpp1.6`
- Charge points connect as **client**, PlagSini CSMS acts as **server**

---

## 3. Connection setup

### 3.1 Endpoint

PlagSini exposes two OCPP endpoints. Choose based on charger firmware capability:

**Option A — WSS (encrypted, recommended for production)**

```
wss://charger.czeros.tech/ocpp/{charge_point_id}
```

- Port: 443 (standard HTTPS)
- TLS terminated at Nginx reverse proxy
- Firmware must support TLS 1.2 or higher
- Server certificate: Let's Encrypt (widely trusted CA)

**Option B — WS (plain, fallback for firmware without TLS)**

```
ws://charger.czeros.tech:9000/{charge_point_id}
```

- Port: 9000 (direct to CSMS container)
- Plain-text WebSocket, no TLS
- Suitable for firmware that does not implement TLS
- Not recommended for production over untrusted networks — use only if firmware constraint requires it

Where `{charge_point_id}` is the unique identifier assigned by PlagSini during provisioning (Section 4). Examples:

```
wss://charger.czeros.tech/ocpp/TRANSSEMI-22KW-001
ws://charger.czeros.tech:9000/TRANSSEMI-22KW-001
```

### 3.2 TLS / certificate

- Server certificate: Let's Encrypt (widely trusted CA — no additional root cert needed on charger firmware if it uses standard CA bundle)
- Minimum TLS version: **1.2**
- Cipher suites: ECDHE-based, forward secrecy

If your firmware runs on an older embedded platform without recent CA roots, request the `ISRG Root X1` root certificate from us and pre-load it.

### 3.3 Authentication

PlagSini enforces per-charger token authentication in production. Two authentication modes are supported (choose based on firmware capability):

**Mode A — HTTP Basic Auth in WebSocket handshake (recommended)**
```
Authorization: Basic <base64(charge_point_id:token)>
```

**Mode B — Bearer token subprotocol negotiation**
```
Sec-WebSocket-Protocol: ocpp1.6
Authorization: Bearer <token>
```

The token is a random 64-character string issued to your team per charger, kept secret. Rotate on request; no need to hardcode in mass-production firmware if a provisioning mechanism is available.

### 3.4 Connection flow

```
    Charger                              PlagSini CSMS
       |                                       |
       |----- WebSocket upgrade ---------------|
       |         + Authorization header        |
       |         + Sec-WebSocket-Protocol      |
       |                                       |
       |<---- 101 Switching Protocols ---------|
       |                                       |
       |----- BootNotification ----------------|
       |                                       |
       |<---- BootNotification.conf -----------|
       |         (interval, status: Accepted)  |
       |                                       |
       |----- Heartbeat (every N seconds) ---->|
       |<---- Heartbeat.conf ------------------|
       |                                       |
```

If BootNotification returns `status: Rejected`, charger should retry after the returned interval. If `status: Pending`, use TriggerMessage to re-send.

---

## 4. Charger provisioning process

Before your charger can connect, PlagSini must provision the unit in our database.

### 4.1 What you send us
- Charger model & manufacturer
- Firmware version
- Rated power (kW)
- Connector type (Type 2, CCS2, CHAdeMO, GB/T)
- Number of connectors
- Charger serial number (for record only)
- Preferred `charge_point_id` (optional — otherwise we generate one)

### 4.2 What we send back
- Assigned `charge_point_id`
- Authentication token
- Endpoint URL confirmation
- Test / production flag

### 4.3 Firmware configuration on your side

Configure the charger via its local UI, CLI, or configuration file with:

| Config key | Value |
|---|---|
| `OcppServerUrl` (or vendor-equivalent) | `wss://charger.czeros.tech/ocpp` (WSS) *or* `ws://charger.czeros.tech:9000` (WS) |
| `ChargePointId` | (from provisioning) |
| `AuthorizationKey` (basic-auth token) | (from provisioning) |
| `HeartbeatInterval` | 60 seconds (recommended) |
| `MeterValueSampleInterval` | 60 seconds (recommended) |
| `WebSocketPingInterval` | 30 seconds |
| `ConnectionTimeOut` | 60 seconds |

---

## 5. Supported OCPP messages

PlagSini implements the full OCPP 1.6J Core Profile plus commonly requested Firmware and Remote profiles.

### 5.1 Charger → CSMS (initiated by charger)

| Message | Support | Notes |
|---|---|---|
| BootNotification | ✅ Required on connect | Response contains interval, status |
| Heartbeat | ✅ Required periodic | Every 60 seconds recommended |
| StatusNotification | ✅ Required on state change | Connector state machine |
| StartTransaction | ✅ | Session start, returns transactionId |
| StopTransaction | ✅ | Session end, meter reading |
| MeterValues | ✅ | Periodic energy / power reporting |
| Authorize | ✅ | RFID / token validation |
| DataTransfer | ✅ | Vendor-specific extensions |
| FirmwareStatusNotification | ✅ | Firmware update progress |
| DiagnosticsStatusNotification | ✅ | Diagnostics upload progress |

### 5.2 CSMS → Charger (initiated by PlagSini)

| Message | Support | Notes |
|---|---|---|
| RemoteStartTransaction | ✅ | Trigger session start from app / dashboard |
| RemoteStopTransaction | ✅ | Trigger session stop |
| ChangeConfiguration | ✅ | Runtime config update |
| GetConfiguration | ✅ | Read charger configuration keys |
| ChangeAvailability | ✅ | Set connector Operative / Inoperative |
| Reset | ✅ | Soft / Hard reboot |
| UnlockConnector | ✅ | Release cable lock |
| TriggerMessage | ✅ | Force charger to send a specific message |
| ClearCache | ✅ | Clear local authorisation cache |
| UpdateFirmware | ✅ | OTA firmware download instruction |
| GetDiagnostics | ✅ | Upload diagnostics file |
| ReserveNow | ✅ | Reservation support |
| CancelReservation | ✅ | Cancel active reservation |

If your firmware does not support one of the CSMS-initiated messages, PlagSini gracefully handles the error response — the charger simply returns `NotImplemented` or `NotSupported` per spec.

---

## 6. Sample message sequences

All examples are OCPP 1.6J JSON on the WebSocket.

### 6.1 Boot on connect

```json
// Charger → CSMS
[2, "unique-message-id-1", "BootNotification", {
  "chargePointVendor": "Transsemi",
  "chargePointModel": "22kW-AC",
  "chargePointSerialNumber": "TS22-2026-0001",
  "firmwareVersion": "1.0.0"
}]

// CSMS → Charger
[3, "unique-message-id-1", {
  "status": "Accepted",
  "currentTime": "2026-07-01T08:30:00Z",
  "interval": 60
}]
```

### 6.2 Heartbeat

```json
// Charger → CSMS
[2, "msg-id-2", "Heartbeat", {}]

// CSMS → Charger
[3, "msg-id-2", { "currentTime": "2026-07-01T08:31:00Z" }]
```

### 6.3 Status notification (plug in)

```json
// Charger → CSMS
[2, "msg-id-3", "StatusNotification", {
  "connectorId": 1,
  "errorCode": "NoError",
  "status": "Preparing",
  "timestamp": "2026-07-01T08:35:00Z"
}]

// CSMS → Charger
[3, "msg-id-3", {}]
```

### 6.4 Full charging session

```json
// 1. User authorises (or dashboard triggers RemoteStartTransaction)
[2, "id-4", "Authorize", { "idTag": "APP_USER_001" }]
[3, "id-4", { "idTagInfo": { "status": "Accepted" } }]

// 2. StartTransaction
[2, "id-5", "StartTransaction", {
  "connectorId": 1,
  "idTag": "APP_USER_001",
  "meterStart": 12345,
  "timestamp": "2026-07-01T08:36:00Z"
}]
[3, "id-5", {
  "transactionId": 101,
  "idTagInfo": { "status": "Accepted" }
}]

// 3. MeterValues (every 60s during session)
[2, "id-6", "MeterValues", {
  "connectorId": 1,
  "transactionId": 101,
  "meterValue": [{
    "timestamp": "2026-07-01T08:37:00Z",
    "sampledValue": [
      { "value": "12500", "measurand": "Energy.Active.Import.Register", "unit": "Wh" },
      { "value": "22000", "measurand": "Power.Active.Import", "unit": "W" }
    ]
  }]
}]
[3, "id-6", {}]

// 4. StopTransaction
[2, "id-7", "StopTransaction", {
  "transactionId": 101,
  "idTag": "APP_USER_001",
  "meterStop": 22345,
  "timestamp": "2026-07-01T09:36:00Z",
  "reason": "EVDisconnected"
}]
[3, "id-7", { "idTagInfo": { "status": "Accepted" } }]
```

### 6.5 Server-initiated Remote Start

```json
// CSMS → Charger
[2, "srv-id-1", "RemoteStartTransaction", {
  "connectorId": 1,
  "idTag": "APP_USER_001"
}]

// Charger → CSMS
[3, "srv-id-1", { "status": "Accepted" }]

// Charger then follows the normal session flow (Authorize → StartTransaction → ...)
```

### 6.6 Server-initiated Reset

```json
// CSMS → Charger
[2, "srv-id-2", "Reset", { "type": "Soft" }]

// Charger → CSMS
[3, "srv-id-2", { "status": "Accepted" }]
```

---

## 7. Charger state machine

PlagSini expects the charger to report state via `StatusNotification` with one of these values (per OCPP spec):

| Status | Meaning |
|---|---|
| `Available` | Idle, ready for use |
| `Preparing` | Plug inserted, waiting for authorisation |
| `Charging` | Session active, energy flowing |
| `SuspendedEV` | Session paused by vehicle (SOC full etc.) |
| `SuspendedEVSE` | Session paused by charger |
| `Finishing` | Session ending, plug still inserted |
| `Reserved` | Reserved for a user |
| `Unavailable` | Manually disabled or configured Inoperative |
| `Faulted` | Hardware error |

Report transitions promptly so the dashboard reflects live state.

---

## 8. Security requirements

### 8.1 TLS
- Minimum TLS 1.2 (TLS 1.3 preferred)
- Server certificate verification MUST be enabled on charger firmware
- Do not disable certificate validation in production

### 8.2 Authentication
- Never share tokens across chargers — one token per unit
- Store token in secure firmware storage (encrypted, not plain-text file)
- Rotate token on physical decommission of charger

### 8.3 Message integrity
- Charger must handle CallError responses gracefully — do not treat as fatal
- Reconnect on WebSocket close with exponential backoff (start 2s, cap 60s)
- Do not spam server on error — respect the returned interval

---

## 9. Testing checklist (docking certification)

Complete the following checks during joint docking test to certify a charger model:

- [ ] WebSocket handshake succeeds with correct token
- [ ] BootNotification sent within 30 seconds of connection
- [ ] BootNotification.conf received and interval respected
- [ ] Heartbeat sent at configured interval
- [ ] StatusNotification sent on plug-in (Available → Preparing)
- [ ] Authorize request handled by app-side auth (RFID or app trigger)
- [ ] StartTransaction returns valid `transactionId`
- [ ] MeterValues sent at configured interval during session
- [ ] Values include Energy.Active.Import.Register (Wh) and Power.Active.Import (W)
- [ ] StopTransaction sent on plug-out with correct meterStop
- [ ] RemoteStartTransaction (server → charger) accepted and executes
- [ ] RemoteStopTransaction (server → charger) accepted and executes
- [ ] Reset (Soft) command reboots charger cleanly
- [ ] UnlockConnector command releases cable
- [ ] ChangeAvailability (Inoperative → Operative) works
- [ ] Reconnect on network loss with backoff (verified by pulling ethernet for 30s)
- [ ] Vendor DataTransfer messages (if any) documented and accepted

---

## 10. Troubleshooting common issues

| Symptom | Likely cause | Resolution |
|---|---|---|
| WebSocket 401 Unauthorized | Wrong token or wrong Authorization header format | Verify token, check header case-sensitivity |
| WebSocket 400 Bad Request | Missing Sec-WebSocket-Protocol: ocpp1.6 header | Add the sub-protocol header |
| TLS handshake fails | Missing / expired CA bundle on charger | Update charger firmware CA store to include Let's Encrypt ISRG Root X1 |
| BootNotification rejected | Charger not provisioned in PlagSini DB | Contact PlagSini for provisioning |
| No response to CSMS commands | Charger not sending Heartbeat / stale WebSocket | Check network, firewall, keepalive settings |
| MeterValues missing key measurands | Incomplete OCPP profile support | Enable Energy.Active.Import.Register and Power.Active.Import at minimum |
| Frequent reconnects | Firewall dropping idle WebSockets | Reduce WebSocketPingInterval to 20 seconds |
| Charger shows Offline in dashboard | Missed heartbeat for > 5 minutes | Verify network stability |

---

## 11. Service level & availability

| Metric | Target |
|---|---|
| CSMS availability | 99.5% (excluding scheduled maintenance) |
| WebSocket accept latency | ≤ 500 ms (95th percentile) |
| BootNotification response latency | ≤ 500 ms |
| CDR generation after StopTransaction | ≤ 60 s |
| Scheduled maintenance | Announced 48 hours in advance, off-peak hours (MYT) |

---

## 12. Contact & support

For technical questions, provisioning requests, or docking coordination:

- **Project Lead:** Aqid — aqidishak28@gmail.com
- **Engineering:** engineering@plagsini.com
- **Production CSMS (WSS):** wss://charger.czeros.tech/ocpp/{charge_point_id}
- **Production CSMS (WS):** ws://charger.czeros.tech:9000/{charge_point_id}
- **Status endpoint:** https://charger.czeros.tech/health
- **Company:** C Zero Sdn Bhd

Typical response time: within 1 business day (MYT).

---

## 13. Change log

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 1 July 2026 | C Zero Engineering | Initial release |

---

*This document is issued by C Zero Sdn Bhd and remains the intellectual property of the company. Confidential — for partner use under signed NDA where applicable.*

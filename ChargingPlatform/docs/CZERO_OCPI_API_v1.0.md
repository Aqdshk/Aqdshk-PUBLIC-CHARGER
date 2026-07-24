# C Zero Sdn Bhd — OCPI 2.2.1 API Specification

**Document Version:** 1.0
**Date:** 25 June 2026
**Issued by:** C Zero Sdn Bhd (PlagSini EV Charging Platform)
**Status:** Production-ready (Sandbox available on request)

---

## 1. Document Control

| Field | Value |
|---|---|
| **Operator (Legal Entity)** | C Zero Sdn Bhd |
| **Operator Registered Address** | 2, Jalan Gergaji 15/14, Seksyen 15, 40200 Shah Alam, Selangor, Malaysia |
| **Trading Brand** | PlagSini |
| **OCPI Party ID** | `PLG` (3-letter) |
| **OCPI Country Code** | `MY` (ISO 3166-1 alpha-2) |
| **OCPI Role** | CPO (Charge Point Operator) |
| **Protocol Version** | OCPI 2.2.1 |
| **Production Base URL** | `https://charger.czeros.tech/ocpi` |
| **Sandbox Base URL** | Available on request after eRoaming agreement signed |

---

## 2. Overview

C Zero Sdn Bhd operates the **PlagSini EV Charging Platform**, exposing its charging stations to roaming partners (EMSPs, Hubs, OEMs) through a fully compliant **OCPI 2.2.1 CPO interface**.

This document covers all endpoints required for an eRoaming partner integration, including:

- Discovery (`versions`, `credentials`)
- Location & equipment data (`locations`, `EVSEs`, `connectors`)
- Pricing (`tariffs`, `tariff_groups`, `taxes`)
- Session lifecycle (`sessions`, `cdrs`)
- Authentication (`tokens`)
- Remote control (`commands` — `START_SESSION`, `STOP_SESSION`)
- Partner governance (`roaming_operators`)

All endpoints conform to the OCPI 2.2.1 specification published by the EVRoaming Foundation.

---

## 3. Authentication

All authenticated endpoints require an HTTP header:

```
Authorization: Token <your-token>
```

The token may be sent either as a plain string or base64-encoded per OCPI 2.2.1 §7.1 — the server accepts both. It is exchanged during the OCPI credentials handshake (`POST /2.2.1/credentials`). Until the handshake completes, partners may use a pre-shared bootstrap token issued by C Zero Sdn Bhd upon agreement execution.

**Token rotation:** supported per OCPI spec via subsequent `PUT /credentials`.

---

## 4. Response Envelope

All endpoints return the standard OCPI response envelope:

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-06-25T06:47:54Z",
  "data": { ... }
}
```

### 4.1 Status Codes

| Code | Meaning |
|---|---|
| `1000` | Success |
| `2000` | Generic client error |
| `2001` | Invalid or missing parameters |
| `2002` | Not enough information |
| `2003` | Unknown location |
| `2004` | Unknown EVSE |
| `3000` | Generic server error |
| `3001` | Unable to use the client's API |
| `3002` | Unsupported version |

---

## 5. Endpoint Reference

### 5.1 Versions — Discovery

#### `GET /ocpi/versions`

List all OCPI versions supported by C Zero Sdn Bhd.

**Authentication:** None (public discovery).

**Response example:**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-06-25T06:47:54Z",
  "data": [
    { "version": "2.2.1", "url": "https://charger.czeros.tech/ocpi/2.2.1" }
  ]
}
```

---

#### `GET /ocpi/2.2.1`

List all modules supported in version 2.2.1.

**Response example:**

```json
{
  "status_code": 1000,
  "data": {
    "version": "2.2.1",
    "endpoints": [
      { "identifier": "credentials", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/credentials" },
      { "identifier": "locations", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/locations" },
      { "identifier": "sessions", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/sessions" },
      { "identifier": "cdrs", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/cdrs" },
      { "identifier": "tokens", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/tokens" },
      { "identifier": "tariffs", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/tariffs" },
      { "identifier": "commands", "role": "RECEIVER", "url": "https://charger.czeros.tech/ocpi/2.2.1/commands" },
      { "identifier": "tariff_groups", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/tariff_groups" },
      { "identifier": "taxes", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/taxes" },
      { "identifier": "roaming_operators", "role": "SENDER", "url": "https://charger.czeros.tech/ocpi/2.2.1/roaming_operators" }
    ]
  }
}
```

---

### 5.2 Credentials — Registration Handshake

#### `POST /ocpi/2.2.1/credentials`

Initial credentials exchange. The partner sends their token + version URL; C Zero responds with our token + version URL. Standard OCPI handshake per spec section 7.1.

---

### 5.3 Locations — `getLocationsEndPoint`

#### `GET /ocpi/2.2.1/locations`

Paginated list of all charging locations operated by C Zero.

**Authentication:** Required.

**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `offset` | int | `0` | Pagination offset |
| `limit` | int | `100` | Max items per page (max 1000) |
| `date_from` | ISO 8601 | — | Return locations updated after this date |
| `date_to` | ISO 8601 | — | Return locations updated before this date |

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "MYPLG-DC3001",
      "publish": true,
      "name": "DC3001",
      "address": "Charging Station",
      "city": "Kuala Lumpur",
      "postal_code": "50000",
      "country": "MY",
      "coordinates": { "latitude": 3.1390, "longitude": 101.6869 },
      "evses": [
        {
          "uid": "MYPLG-DC3001-EVSE1",
          "evse_id": "MY*PLG*E*DC3001",
          "status": "AVAILABLE",
          "connectors": [
            {
              "id": "1",
              "standard": "IEC_62196_T2",
              "format": "SOCKET",
              "power_type": "AC_1_PHASE",
              "voltage": 230,
              "amperage": 32,
              "max_electric_power": 7360,
              "last_updated": "2026-07-23T01:46:23Z"
            }
          ],
          "last_updated": "2026-07-23T01:46:23Z"
        }
      ],
      "time_zone": "Asia/Kuala_Lumpur",
      "last_updated": "2026-07-23T01:46:23Z"
    }
  ]
}
```

---

#### `GET /ocpi/2.2.1/locations/{location_id}`

Retrieve a single location by ID. Returns full nested EVSE + connector data (same schema as above, single object instead of array).

---

### 5.4 EVSEs — `getEvseEndPoint` / `getChargePointsEndPoint`

EVSE data is **nested inside `/locations`** responses per OCPI 2.2.1 spec — there is no separate `/evses` endpoint. To fetch EVSEs for a location, call `GET /locations/{location_id}` and read the `evses` array.

The same applies to `getChargePointsEndPoint` and `getEvseConnectorsEndPoint`: connectors are nested inside each EVSE's `connectors` array.

**EVSE statuses returned:** `AVAILABLE`, `BLOCKED`, `CHARGING`, `INOPERATIVE`, `PLANNED`, `REMOVED`, `RESERVED`, `UNKNOWN`.

**Connector standards supported:** `IEC_62196_T2` (Type 2 AC), `IEC_62196_T2_COMBO` (CCS2 DC), `CHADEMO`.

---

### 5.5 Tariffs — `getTariffsEndPoint`

#### `GET /ocpi/2.2.1/tariffs`

Paginated list of all active tariffs.

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "default-dc",
      "currency": "MYR",
      "elements": [
        {
          "price_components": [
            { "type": "ENERGY", "price": 0.50, "step_size": 1 }
          ]
        }
      ],
      "last_updated": "2026-06-25T06:47:54Z"
    }
  ]
}
```

---

### 5.6 Tariff Groups — `getTariffGroupsEndPoint`

#### `GET /ocpi/2.2.1/tariff_groups`

Logical grouping of tariffs (currently bucketed by AC vs DC).

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "ac-default",
      "name": "AC Charging",
      "description": "Slow + medium AC tariffs",
      "tariff_ids": ["ac-7kw", "ac-22kw"],
      "last_updated": "2026-06-25T06:47:54Z"
    },
    {
      "id": "dc-default",
      "name": "DC Fast Charging",
      "description": "DC fast-charge tariffs",
      "tariff_ids": ["dc-30kw", "dc-60kw"],
      "last_updated": "2026-06-25T06:47:54Z"
    }
  ]
}
```

---

### 5.7 Taxes — `getTaxesEndPoint`

#### `GET /ocpi/2.2.1/taxes`

Tax rules applied on top of tariff prices.

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "sst-my",
      "name": "SST",
      "rate": 6.0,
      "applies_to": "TOTAL",
      "country_code": "MY",
      "last_updated": "2026-06-25T06:47:54Z"
    }
  ]
}
```

| Field | Description |
|---|---|
| `rate` | Percentage (e.g. `6.0` = 6%) |
| `applies_to` | One of `ENERGY`, `TIME`, `PARKING`, `FLAT`, `TOTAL` |

---

### 5.8 Sessions — `getSessionEndPoint`

#### `GET /ocpi/2.2.1/sessions`

Active and recently completed charging sessions.

**Query parameters:** `offset`, `limit`, `date_from`, `date_to`.

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "179",
      "start_datetime": "2026-06-25T08:15:00Z",
      "end_datetime": null,
      "kwh": 12.4,
      "cdr_token": {
        "uid": "ROAMING-VLT-001",
        "type": "APP_USER",
        "contract_id": "VLT-CONTRACT-001"
      },
      "auth_method": "AUTH_REQUEST",
      "location_id": "MYPLG-DC3001",
      "evse_uid": "DC3001",
      "connector_id": "1",
      "currency": "MYR",
      "total_cost": 6.20,
      "status": "ACTIVE",
      "last_updated": "2026-06-25T08:35:00Z"
    }
  ]
}
```

**Session statuses:** `ACTIVE`, `COMPLETED`, `INVALID`, `PENDING`, `RESERVATION`.

---

### 5.9 CDRs — Charge Detail Records

#### `GET /ocpi/2.2.1/cdrs`

Final billing records for completed sessions. CDRs are immutable; once created they cannot be modified.

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "id": "CDR-179",
      "start_datetime": "2026-06-25T08:15:00Z",
      "end_datetime": "2026-06-25T09:02:00Z",
      "auth_id": "ROAMING-VLT-001",
      "auth_method": "AUTH_REQUEST",
      "location_id": "MYPLG-DC3001",
      "evse_uid": "DC3001",
      "connector_id": "1",
      "currency": "MYR",
      "total_energy": 24.6,
      "total_time": 0.78,
      "total_cost": 12.30,
      "cdr_token": {
        "uid": "ROAMING-VLT-001",
        "type": "APP_USER",
        "contract_id": "VLT-CONTRACT-001"
      },
      "last_updated": "2026-06-25T09:02:00Z"
    }
  ]
}
```

---

### 5.10 Tokens

#### `GET /ocpi/2.2.1/tokens`

List of tokens (authorisation credentials) valid for use at our charging stations.

---

### 5.11 Commands — `getStartSessionEndPoint` / `getStopSessionEndPoint`

OCPI Commands are **eMSP-initiated** remote-control requests. C Zero responds synchronously with a `CommandResponse` (`ACCEPTED` / `REJECTED`), then asynchronously POSTs a `CommandResult` to the caller's `response_url` once the physical charger has confirmed.

#### `POST /ocpi/2.2.1/commands/START_SESSION`

Start a charging session remotely on behalf of an eMSP user.

**Request body:**

```json
{
  "response_url": "https://emsp.example.com/commands/result/abc123",
  "token": {
    "uid": "ROAMING-USER-001",
    "type": "APP_USER",
    "contract_id": "EMSP-CONTRACT-001",
    "issuer": "Voltality",
    "is_valid": true,
    "whitelist": "ALWAYS",
    "last_updated": "2026-06-25T08:00:00Z"
  },
  "location_id": "MYPLG-DC3001",
  "evse_uid": "DC3001",
  "connector_id": "1",
  "authorization_reference": "AUTH-REF-XYZ"
}
```

**Synchronous response (immediate):**

```json
{
  "status_code": 1000,
  "data": { "result": "ACCEPTED", "timeout": 30 }
}
```

**Asynchronous callback (POSTed to `response_url` within 30s):**

```json
{
  "result": "ACCEPTED",
  "message": [{ "language": "en", "text": "Session started" }]
}
```

**Possible async `result` values:** `ACCEPTED`, `CANCELED_RESERVATION`, `EVSE_OCCUPIED`, `EVSE_INOPERATIVE`, `FAILED`, `NOT_SUPPORTED`, `REJECTED`, `TIMEOUT`, `UNKNOWN_RESERVATION`.

---

#### `POST /ocpi/2.2.1/commands/STOP_SESSION`

Stop an active charging session by session ID.

**Request body:**

```json
{
  "response_url": "https://emsp.example.com/commands/result/abc124",
  "session_id": "179"
}
```

**Synchronous + asynchronous responses follow the same pattern as `START_SESSION`.**

---

#### `POST /ocpi/2.2.1/commands/UNLOCK_CONNECTOR`

Currently returns `NOT_SUPPORTED`. Will be enabled once the underlying OCPP `UnlockConnector` plumbing is exposed (planned next quarter). Contact us if your integration depends on this.

---

### 5.12 Roaming Operators — `getRoamingOperatorsEndPoint`

#### `GET /ocpi/2.2.1/roaming_operators`

Operators authorised to consume our roaming traffic.

**Response example:**

```json
{
  "status_code": 1000,
  "data": [
    {
      "party_id": "VLT",
      "country_code": "SG",
      "name": "Voltality Pte Ltd",
      "role": "HUB",
      "status": "ALLOWED",
      "last_updated": "2026-06-25T06:47:54Z"
    }
  ]
}
```

**Statuses:** `ALLOWED`, `BLOCKED`, `PENDING`.

---

## 5.13 AION Vendor Extension

Non-standard modules mounted under the OCPI namespace at `/ocpi/2.2.1/aion/*`. These expose AION-specific charger controls that are not part of the OCPI 2.2.1 specification but are required for fleet operators managing the AION E7-A hardware family.

**Firmware requirement:** `TK-AMC003-LCD_V2.0.04` or later.

**Authentication:** same `Authorization: Token …` header used across all OCPI endpoints.

**Response envelope:** identical to standard OCPI (§4).

**Common request pattern:** `POST` endpoints only apply fields that are supplied — omit a field to leave it unchanged. All `POST` endpoints return `applied: [<keys changed>]` so the caller can audit what was actually written to the charger.

**Common error responses:**

| HTTP | Meaning |
|---|---|
| 400 | No field supplied in POST body |
| 403 | Missing / invalid OCPI token |
| 404 | Unknown `charger_id` |
| 502 | Charger rejected the OCPP command (returned `Rejected` or `NotSupported`) |
| 503 | Charger's OCPP WebSocket is not currently connected |

---

### 5.13.1 Lights — Front-panel LEDs

Toggle the three AION front-housing LEDs individually.

#### `POST /ocpi/2.2.1/aion/lights`

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `charger_id` | string | Yes | Physical charger ID |
| `status_light` | boolean | No | Status ring LED on/off |
| `logo_light` | boolean | No | Logo backlight LED on/off |
| `background_light` | boolean | No | Background accent LED on/off |

**Example**

```bash
curl -X POST https://charger.czeros.tech/ocpi/2.2.1/aion/lights \
  -H "Authorization: Token $OCPI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"charger_id":"0748911403000093","status_light":true,"logo_light":false}'
```

**Response 200**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-07-15T03:09:38Z",
  "data": {
    "charger_id": "0748911403000093",
    "applied": ["StatusLight", "LogoLight"]
  }
}
```

#### `GET /ocpi/2.2.1/aion/lights?charger_id={id}`

Returns current LED states. Response `data`:

```json
{
  "charger_id": "0748911403000093",
  "status_light": true,
  "logo_light": true,
  "background_light": true
}
```

---

### 5.13.2 Display — LCD text and wallpaper

The AION LCD shows a customisable header text (`home_number`) and a background wallpaper selected from a preset library (`background`).

#### `POST /ocpi/2.2.1/aion/display`

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `charger_id` | string | Yes | Physical charger ID |
| `home_number` | string | No | LCD header text, max 24 characters |
| `background` | string | No | Wallpaper preset name (e.g. `Verdant Pulse`, `Eco Wave`, `Nature`, `Aurora`, `Ocean`, `Neon`, `Classic`) |

**Example**

```bash
curl -X POST https://charger.czeros.tech/ocpi/2.2.1/aion/display \
  -H "Authorization: Token $OCPI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"charger_id":"0748911403000093","home_number":"PLAGSINI KL","background":"Aurora"}'
```

**Response 200**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-07-15T03:09:38Z",
  "data": {
    "charger_id": "0748911403000093",
    "applied": ["HomeNumber", "BackSelection"]
  }
}
```

#### `GET /ocpi/2.2.1/aion/display?charger_id={id}`

```json
{
  "charger_id": "0748911403000093",
  "home_number": "PLAGSINI KL",
  "background": "Aurora"
}
```

---

### 5.13.3 Local Admin Credentials

Change the credentials used to log in to the AION on-device web console (used by technicians on site). These credentials are **unrelated** to the OCPI token or OCPP authentication key.

#### `POST /ocpi/2.2.1/aion/credentials`

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `charger_id` | string | Yes | Physical charger ID |
| `username` | string | No | New username, max 32 chars |
| `password` | string | No | New password, max 32 chars |

**Response 200**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-07-15T03:09:38Z",
  "data": {
    "charger_id": "0748911403000093",
    "applied": ["UserName", "UserPass"]
  }
}
```

#### `GET /ocpi/2.2.1/aion/credentials?charger_id={id}`

Returns username only. **Password is never echoed** — rotate via POST if the password is lost.

```json
{
  "charger_id": "0748911403000093",
  "username": "admin"
}
```

---

### 5.13.4 Schedule — Auto start/stop window

Configure the single auto start/stop window supported by AION firmware v2.0.04.

Sends `Sch_State`, `Sch_Day`, `Sch_StartTime`, `Sch_StopTime` via OCPP `ChangeConfiguration`.

#### `POST /ocpi/2.2.1/aion/schedule`

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `charger_id` | string | Yes | Physical charger ID |
| `enabled` | boolean | No | `true` to activate the schedule, `false` to disable |
| `day` | integer | No | `0` Sunday … `6` Saturday |
| `start_time` | string | No | `HH:MM` (24-hour) |
| `stop_time` | string | No | `HH:MM` (24-hour) |

**Example**

```bash
curl -X POST https://charger.czeros.tech/ocpi/2.2.1/aion/schedule \
  -H "Authorization: Token $OCPI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"charger_id":"0748911403000093","enabled":true,"day":1,"start_time":"10:00","stop_time":"18:00"}'
```

**Response 200**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-07-15T03:09:48Z",
  "data": {
    "charger_id": "0748911403000093",
    "applied": ["Sch_State", "Sch_Day", "Sch_StartTime", "Sch_StopTime"]
  }
}
```

#### `GET /ocpi/2.2.1/aion/schedule?charger_id={id}`

```json
{
  "charger_id": "0748911403000093",
  "enabled": true,
  "day": 1,
  "start_time": "10:00",
  "stop_time": "18:00"
}
```

**Limitation:** AION firmware v2.0.04 supports one schedule window per charger. Multiple schedules or per-day windows are not currently supported.

---

### 5.13.5 Lock — Availability toggle

Lock or unlock a charger (or a specific connector) via OCPP `ChangeAvailability`. Active sessions are **not** interrupted; only new sessions are affected.

- `lock` → `Inoperative` (charger refuses new sessions)
- `unlock` → `Operative` (normal operation)

#### `POST /ocpi/2.2.1/aion/lock`

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `charger_id` | string | Yes | Physical charger ID |
| `action` | string | Yes | `lock` or `unlock` |
| `connector_id` | integer | No | `0` (default) locks the whole charger; `1..N` locks a specific connector |

**Example**

```bash
curl -X POST https://charger.czeros.tech/ocpi/2.2.1/aion/lock \
  -H "Authorization: Token $OCPI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"charger_id":"0748911403000093","action":"lock"}'
```

**Response 200**

```json
{
  "status_code": 1000,
  "status_message": "Success",
  "timestamp": "2026-07-15T03:09:38Z",
  "data": {
    "charger_id": "0748911403000093",
    "connector_id": 0,
    "action": "lock",
    "ocpp_status": "Accepted"
  }
}
```

#### `GET /ocpi/2.2.1/aion/lock?charger_id={id}`

```json
{
  "charger_id": "0748911403000093",
  "locked": false,
  "availability": "available"
}
```

---

## 6. Integration Checklist (for Partner Onboarding)

1. **Sign eRoaming Agreement** with C Zero Sdn Bhd (template provided separately).
2. **Receive bootstrap token** from C Zero.
3. **Initiate OCPI handshake** — `POST /ocpi/2.2.1/credentials` with your party details.
4. **Verify version discovery** — `GET /ocpi/2.2.1` returns 10 module endpoints.
5. **Pull initial data** — `GET /locations`, `GET /tariffs`, `GET /taxes`.
6. **Test remote control** — `POST /commands/START_SESSION` against sandbox charger ID `DC3001-TEST`.
7. **Verify CDR delivery** — complete one session, confirm CDR appears in `GET /cdrs`.
8. **Go-live sign-off** — joint test session signed off in writing by both parties.

Typical onboarding timeline: **5–7 business days** from token issuance to production go-live.

---

## 7. Service Levels

| Metric | Target |
|---|---|
| **Endpoint availability** | 99.5% (excluding scheduled maintenance) |
| **Sync command response latency** | ≤ 500 ms (95th percentile) |
| **Async CommandResult callback** | ≤ 30 s |
| **CDR generation** | ≤ 60 s after `StopTransaction` |
| **Tariff change propagation** | ≤ 6 weeks per eRoaming clause |

---

## 8. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 25 June 2026 | C Zero Engineering | Initial release covering 10 standard OCPI modules |
| 1.1 | 15 July 2026 | C Zero Engineering | Added §5.13 AION Vendor Extension — 5 new modules (lights, display, credentials, schedule, lock) under `/ocpi/2.2.1/aion/*` for AION E7-A firmware ≥ TK-AMC003-LCD_V2.0.04 |
| 1.2 | 23 July 2026 | C Zero Engineering | Accuracy sweep: Party ID corrected to `PLG`, EVSE / Location ID format aligned with live endpoint output (`MYPLG-<id>-EVSE1`, `MYPLG-<id>`), authentication note updated (plain-string token, not base64). |

---

*This document is issued by C Zero Sdn Bhd and remains the intellectual property of the company. Confidential — for partner use under signed NDA only.*

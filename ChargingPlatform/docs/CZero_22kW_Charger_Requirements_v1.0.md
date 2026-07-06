# 22kW AC Public EV Charger — Technical Requirements Specification

**Document Version:** 1.0
**Date:** 2 July 2026
**Issued by:** C Zero Sdn Bhd (PlagSini EV Charging Platform)
**Recipient:** Charger hardware vendor (Transsemi)
**Purpose:** Procurement specification for 22kW AC public charging units

---

## 1. Document control

| Field | Value |
|---|---|
| **Buyer / Operator** | C Zero Sdn Bhd |
| **Trading brand** | PlagSini |
| **Deployment context** | Public EV charging network — Malaysia |
| **Target charger model** | 22kW AC 3-phase, Type 2 tethered |
| **Primary contact** | Aqid — aqidishak28@gmail.com |
| **Technical contact** | engineering@plagsini.com |

---

## 2. Overview

This document specifies the mandatory and preferred features for 22kW AC public EV chargers to be procured by C Zero Sdn Bhd for deployment across the PlagSini charging network in Malaysia. The specification aligns with international standards (IEC 61851, OCPP 1.6J, ISO 15118 partial) and Malaysian regulatory requirements (Suruhanjaya Tenaga, SIRIM/MCM).

Compliance categories used throughout this document:

- **Mandatory** — non-negotiable, unit will be rejected if missing
- **Preferred** — strongly desired, weighted favourably during evaluation
- **Optional** — bonus feature, no penalty if absent

---

## 3. Electrical & charging specification

### 3.1 Power delivery

| Specification | Requirement | Compliance |
|---|---|---|
| Rated output power | 22 kW AC | Mandatory |
| Input phase | 3-phase, 400 V AC (nominal) | Mandatory |
| Rated current | 32 A per phase | Mandatory |
| Input frequency | 50 Hz | Mandatory |
| Alternative single-phase variant | 7.4 kW (32 A × 230 V) | Preferred |
| Charging mode | Mode 3 per IEC 61851-1 | Mandatory |

### 3.2 Connector & cable

| Specification | Requirement | Compliance |
|---|---|---|
| Connector type | Type 2 (IEC 62196-2 / Mennekes) | Mandatory |
| Cable configuration | Tethered, fixed cable | Mandatory |
| Cable length | Minimum 5 metres | Mandatory |
| Cable rating | 32 A, 5-core, 600 V insulation | Mandatory |
| Connector auto-lock | Yes, during active charging session | Mandatory |
| Remote unlock capability | Via OCPP UnlockConnector command | Mandatory |
| Cable holder / hook | Integrated on housing | Mandatory |

### 3.3 Safety & protection

| Feature | Requirement | Compliance |
|---|---|---|
| RCD Type A | Integrated | Mandatory |
| DC leakage detection | 6 mA sensitivity, integrated | Mandatory |
| Over-current protection | Built-in circuit breaker | Mandatory |
| Over-voltage protection | Surge arrester, Class II minimum | Mandatory |
| Over-temperature shutdown | Automatic, per IEC 61851 | Mandatory |
| Emergency stop button | Physical red button, latching, front-mounted | Mandatory |
| Earth continuity monitoring | Continuous during charging | Mandatory |
| Ground fault interrupt | Automatic trip within 30 ms | Mandatory |
| Vehicle presence detection | Control Pilot per Type 2 spec | Mandatory |
| Anti-vandalism enclosure | IK10 impact resistance | Mandatory |

### 3.4 Energy metering

| Specification | Requirement | Compliance |
|---|---|---|
| Integrated energy meter | Yes, kWh cumulative + session | Mandatory |
| Accuracy class | ±1% (billing grade) | Mandatory |
| MID (EU) or equivalent certification | Module B + D | Mandatory |
| Measurement parameters | Energy (kWh), power (kW), voltage (V), current (A) per phase | Mandatory |
| Reporting interval | Configurable, default 10–60 seconds | Mandatory |
| Storage of unbilled sessions | Non-volatile, minimum 30 days | Mandatory |

---

## 4. Communication & connectivity

### 4.1 OCPP protocol

| Specification | Requirement | Compliance |
|---|---|---|
| OCPP version | **1.6J (JSON over WebSocket)** | Mandatory |
| OCPP version alternative | 2.0.1 | Preferred |
| Transport | WebSocket Secure (WSS) with TLS 1.2 minimum | Mandatory |
| Plain WebSocket (WS) fallback | Configurable, per site policy | Mandatory |
| Sub-protocol header | `Sec-WebSocket-Protocol: ocpp1.6` | Mandatory |
| Auto-reconnect on network loss | Exponential backoff (2s → 60s cap) | Mandatory |
| Authentication | Bearer token, per-charger, configurable | Mandatory |

### 4.2 Supported OCPP messages

**Charger → Server (client-initiated):**

| Message | Requirement |
|---|---|
| BootNotification | Mandatory |
| Heartbeat | Mandatory |
| StatusNotification | Mandatory |
| Authorize | Mandatory |
| StartTransaction | Mandatory |
| StopTransaction | Mandatory |
| MeterValues | Mandatory |
| DataTransfer (vendor extensions) | Preferred |
| FirmwareStatusNotification | Mandatory |
| DiagnosticsStatusNotification | Mandatory |

**Server → Charger (accepted commands):**

| Message | Requirement |
|---|---|
| RemoteStartTransaction | Mandatory |
| RemoteStopTransaction | Mandatory |
| ChangeConfiguration | Mandatory |
| GetConfiguration | Mandatory |
| ChangeAvailability | Mandatory |
| Reset (Soft, Hard) | Mandatory |
| UnlockConnector | Mandatory |
| TriggerMessage | Mandatory |
| ClearCache | Mandatory |
| UpdateFirmware | Mandatory |
| GetDiagnostics | Mandatory |
| ReserveNow / CancelReservation | Preferred |

### 4.3 Endpoint configuration (**critical for PlagSini deployment**)

| Requirement | Compliance |
|---|---|
| **OCPP server URL must be configurable in the field, without laptop or vendor tools** | Mandatory |
| Configuration channels (any one acceptable, all preferred): | |
| — Via Bluetooth mobile-app pairing | Preferred |
| — Via local WiFi hotspot + web configuration page | Preferred |
| — Via QR code scan (charger displays QR, mobile fills fields) | Preferred |
| URL format supported | `wss://{host}[:port]/{path}/{charge_point_id}` | Mandatory |
| Charge Point ID reconfigurable in field | Mandatory |
| Authorization token reconfigurable in field | Mandatory |
| Heartbeat interval reconfigurable | Mandatory |

### 4.4 Network connectivity

| Interface | Requirement | Compliance |
|---|---|---|
| WiFi 2.4 / 5 GHz (b/g/n/ac) | Yes | Mandatory |
| Ethernet RJ45 | Yes, fallback | Mandatory |
| 4G / LTE cellular (SIM slot) | Yes, fallback | Preferred |
| WiFi hotspot / AP mode | For local commissioning | Preferred |
| NTP time synchronisation | Yes, auto | Mandatory |
| DNS over TCP support | Yes | Mandatory |
| IPv6 support | Yes | Preferred |

### 4.5 Bluetooth (**mandatory for PlagSini deployment**)

| Requirement | Compliance |
|---|---|
| **Bluetooth 5.0 LE** | Mandatory |
| Purpose: local commissioning by installer | Mandatory |
| Purpose: end-user mobile pairing (start/stop session) | Preferred |
| Security: encrypted pairing with rotating PIN | Mandatory |
| Range: minimum 10 metres line-of-sight | Mandatory |

---

## 5. Authentication

| Feature | Requirement | Compliance |
|---|---|---|
| **RFID reader** | **ISO/IEC 14443 A/B** — MIFARE Classic 1K/4K, MIFARE DESFire, NFC-A | Mandatory |
| RFID range | 3–5 cm | Mandatory |
| RFID feedback | Audio beep + LED colour change on tap | Mandatory |
| App-initiated start | Via OCPP RemoteStartTransaction | Mandatory |
| QR code scan-to-start | Charger displays / prints QR; app deep-links to server | Preferred |
| Free vend mode | Configurable — no authentication required (for private sites) | Mandatory |
| PIN pad | For local ad-hoc user | Optional |

---

## 6. User interface

### 6.1 Display

| Requirement | Compliance |
|---|---|
| **No touch screen** | Mandatory (cost + reliability preference) |
| Read-only OLED or LCD display | Mandatory |
| Screen size | 2.0 – 3.5 inches |
| Content: session status, energy delivered (kWh), duration, error codes | Mandatory |
| Multi-language: English, Bahasa Melayu, Chinese | Mandatory |
| Brightness | Auto-adjusting for outdoor visibility | Preferred |

### 6.2 Status LED indicator

| Requirement | Compliance |
|---|---|
| RGB LED strip on housing front | Mandatory |
| Colour scheme: | |
| — White = idle / available | Mandatory |
| — Blue = preparing (plug inserted, awaiting auth) | Mandatory |
| — Green = charging | Mandatory |
| — Amber = finishing / session ending | Mandatory |
| — Red flashing = fault | Mandatory |
| — Purple = reserved | Preferred |
| Brightness | Visible in direct sunlight and at night | Mandatory |

### 6.3 Physical controls

| Control | Requirement |
|---|---|
| Emergency stop button | Mandatory |
| Navigation buttons | Not required (no touch UI) |
| Cable release button | Only if required by mechanical design |

### 6.4 Audio feedback

| Sound | Purpose |
|---|---|
| Short beep | RFID tap accepted |
| Double beep | RFID rejected |
| Alarm | Fault / emergency stop |
| Muted mode | Configurable via OCPP |

---

## 7. Enclosure & environmental

| Specification | Requirement | Compliance |
|---|---|---|
| Ingress protection | **IP54 minimum**, IP65 preferred | Mandatory |
| Impact rating | **IK10** | Mandatory |
| Operating temperature | **-25 °C to +55 °C** | Mandatory |
| Humidity | 5–95% RH non-condensing | Mandatory |
| Altitude | Up to 2000 m | Mandatory |
| Housing material | Powder-coated steel or anodised aluminium | Mandatory |
| Corrosion resistance | Salt-spray tested (ISO 9227) | Preferred |
| Colour | Customisable; PlagSini brand green + charcoal specified separately | Preferred |
| Mounting options | Pole-mount + wall-mount (both included in delivery) | Mandatory |
| Dimensions | Compact — target under 40 × 30 × 20 cm | Preferred |
| Weight | Under 15 kg | Preferred |
| Anti-theft mounting hardware | Tamper-proof screws | Mandatory |

---

## 8. Maintenance, diagnostics, and firmware

| Feature | Requirement | Compliance |
|---|---|---|
| Firmware update (OTA) | Via OCPP UpdateFirmware, HTTPS URL source | Mandatory |
| Firmware rollback | Two-slot A/B firmware storage | Preferred |
| Remote diagnostics | GetDiagnostics uploads log file to server via HTTPS | Mandatory |
| Local log storage | Non-volatile, minimum **30 days rolling** | Mandatory |
| Self-test on boot | Report health via BootNotification | Mandatory |
| Fault reporting | StatusNotification with IEC 61851 error codes | Mandatory |
| Access panel | Tool-free or single-screw access for service | Preferred |
| Modular component design | RFID module, comms module, meter — field-replaceable | Preferred |

---

## 9. Certifications (**mandatory for Malaysia public deployment**)

| Certification | Compliance |
|---|---|
| CE marking (European conformity) | Mandatory |
| CB Scheme (IECEE) | Mandatory |
| TÜV or UL electrical safety certification | Mandatory |
| MID Module B + D (energy meter billing accuracy) | Mandatory |
| SIRIM / MCM certification (Malaysia radio module) | Mandatory |
| Suruhanjaya Tenaga (ST) approval | Mandatory prior to deployment |
| MS IEC 61851-1 conformance | Mandatory |
| RoHS + REACH compliance | Mandatory |
| EMC (electromagnetic compatibility) certification | Mandatory |

Vendor must provide copies of all certificates prior to shipment. C Zero reserves the right to reject shipment lacking any mandatory certification.

---

## 10. Warranty & after-sales

| Item | Requirement | Compliance |
|---|---|---|
| Standard warranty | **2 years minimum**, 3 years preferred | Mandatory |
| MTBF (Mean Time Between Failures) | 50,000 hours target | Preferred |
| Warranty extension option | Available up to 5 years | Preferred |
| Spare parts availability | **5 years minimum** post-purchase | Mandatory |
| Technical support hotline | 8×5 minimum, 24/7 preferred | Mandatory |
| RMA turnaround | **≤ 14 days** replacement | Mandatory |
| Field service support | Vendor engineer available on-call during commissioning | Preferred |
| Documentation package (per unit): | |
| — Installation manual | Mandatory |
| — User manual (English + Bahasa) | Mandatory |
| — OCPP profile mapping | Mandatory |
| — Wiring diagram | Mandatory |
| — Firmware release notes | Mandatory |

---

## 11. Deliverables per unit

Each shipped charger unit must include:

- Charger unit with tethered Type 2 cable (5m minimum)
- Wall-mount + pole-mount kit
- Anti-tamper mounting hardware
- Installation manual (printed + digital)
- User manual (printed + digital)
- OCPP configuration guide
- Bluetooth commissioning app (iOS + Android download link)
- Certificate of conformity
- Serial number & QR label (for asset tracking)
- Test report (factory acceptance test)

---

## 12. Sample procurement and testing

| Phase | Deliverable | Timing |
|---|---|---|
| **Phase 1: Sample** | 1 unit for evaluation | Week 1–4 |
| **Phase 2: OCPP docking** | Joint test with PlagSini CSMS | Week 5–6 |
| **Phase 3: Field trial** | 3 units deployed at pilot site | Week 7–10 |
| **Phase 4: Bulk procurement** | Volume purchase decision | Week 11+ |

C Zero reserves the right to conduct random quality checks on any shipment lot.

---

## 13. Custom requirements summary (**PlagSini-specific**)

The following items are unusual for standard vendor offerings and must be explicitly confirmed by Transsemi in writing:

1. **OCPP endpoint URL fully configurable in the field** — no laptop, no vendor tools required. Bluetooth or local WiFi hotspot acceptable.
2. **RFID reader ISO/IEC 14443 A/B** — MIFARE Classic + DESFire + NFC-A compatible.
3. **No touch screen** — LED status strip + read-only OLED/LCD sufficient.
4. **Bluetooth 5.0 LE mandatory** — for local commissioning and mobile app pairing.
5. **Tethered cable, 5 metres minimum** — no socket-only variant accepted for public deployment.
6. **All Malaysia certifications** — SIRIM, MCM, Suruhanjaya Tenaga, MS IEC 61851 — must be confirmed before shipment.
7. **Two-year warranty minimum** — with 5-year spare parts availability guarantee.

---

## 14. Sign-off

**Prepared by:**
C Zero Sdn Bhd — Engineering Team
Date: 2 July 2026

**To be countersigned by vendor:**
Vendor company: _______________________________
Sales / Engineering representative: _______________________________
Date: _______________________________
Signature: _______________________________

By signing, the vendor confirms all mandatory items above are met (or explicitly waived in writing), and agrees to the phased sample-test-deployment schedule.

---

## 15. Appendix A — General Specification Summary

Adopting the standard datasheet layout used by charger OEMs, the required 22kW unit must meet the following consolidated specification. This appendix is intended as a factory-datasheet-style summary that vendors can print directly.

| Parameter | Requirement |
|---|---|
| **Model reference** | 22kW AC Public Charger (PlagSini spec) |
| **Output Power** | 22 kW |
| **Rated Voltage** | 400 V AC (3-phase, line-to-line) / 230 V AC per phase |
| **Rated Current** | 32 A per phase (3-phase) |
| **Frequency** | 50 Hz |
| **User Authentication** | Mobile App + RFID (ISO/IEC 14443 A/B) |
| **Communication Protocol** | OCPP 1.6J (WebSocket, JSON) |
| **Connectivity** | Wi-Fi (2.4 / 5 GHz) + Bluetooth 5.0 LE + Ethernet RJ45 (4G optional) |
| **Display** | LED status strip + small read-only OLED / LCD (no touch screen) |
| **Charging Connector** | Type 2 (IEC 62196-2), tethered |
| **Residual Current Protection** | 30 mA Type A + 6 mA DC leakage |
| **Charging Cable Length** | 5 metres minimum |
| **Ingress Protection** | IP54 minimum (IP65 preferred) |
| **Impact Protection** | IK10 |
| **Electrical Protection** | Overvoltage / undervoltage protection, over-current protection, leakage protection, grounding protection, lightning / surge protection, emergency stop, over-temperature protection, output relay adhesion detection |
| **Operating Temperature** | -25 °C to +55 °C |
| **Operating Humidity** | 5% – 95% RH non-condensing |
| **Operating Altitude** | ≤ 2000 m |
| **Installation Method** | Wall mount / Pole stand (both hardware kits included) |
| **Endpoint Configuration** | User-changeable in field via Bluetooth or local WiFi hotspot |
| **Firmware Update** | OTA via OCPP UpdateFirmware |
| **Warranty** | 2 years minimum (5 years spare-parts availability) |

---

## 16. Appendix B — LED Status Display

The LED status strip is the primary user-facing indicator (no touch screen used). The vendor must implement the following colour and blink patterns.

### 16.1 Normal Charging Status

| Charger Status | LED Colour | LED Pattern |
|---|---|---|
| Standby (idle) | Ice Blue | Solid |
| Plugged | Green | Solid |
| Awaiting Charge (awaiting authorisation) | Green | Blinking |
| Charging (session active) | Green | Chasing with gradient effect |
| RFID Card Read Success | Ice Blue | Blinks 3 times (0.25 s on, 0.25 s off) |
| RFID Card Read Failed | Yellow | Blinks 3 times (0.25 s on, 0.25 s off) |
| Fault / Warning | Red / Yellow | Blinking |

### 16.2 Fault Codes (LED blink patterns)

Faults must be indicated via the LED strip using discrete blink counts so operators can identify the fault type without external tools. Simultaneously, the fault code must be reported to the CSMS via OCPP `StatusNotification`.

| Charger Status | LED Colour | LED Pattern |
|---|---|---|
| Emergency Stop | Red | Blinks 1 time (0.5 s on, 0.5 s off) |
| Leakage Fault | Red | Blinks 2 times (0.5 s on, 0.5 s off) |
| Overvoltage | Red | Blinks 3 times (0.5 s on, 0.5 s off) |
| Overcurrent | Red | Blinks 4 times (0.5 s on, 0.5 s off) |
| Relay Sticking | Red | Blinks 6 times (0.5 s on, 0.5 s off) |
| Not Grounded | Yellow | Blinks 1 time (0.5 s on, 0.5 s off) |
| Undervoltage | Yellow | Blinks 3 times (0.5 s on, 0.5 s off) |
| Relay Fault | Yellow | Blinks 4 times (0.5 s on, 0.5 s off) |
| CP (Control Pilot) Abnormal | Yellow | Blinks 5 times (0.5 s on, 0.5 s off) |
| CP Ground Fault | Yellow | Blinks 6 times (0.5 s on, 0.5 s off) |
| Relay Overtemperature | Yellow | Blinks 7 times (0.5 s on, 0.5 s off) |

Each blink sequence must pause 2 seconds before repeating so field technicians can count blinks reliably. Fault indication continues until the fault is cleared (via reset, remediation, or OCPP ChangeAvailability).

---

## 17. Contact

For clarification or technical discussion:

- **Project Lead:** Aqid — aqidishak28@gmail.com
- **Engineering:** engineering@plagsini.com
- **Company:** C Zero Sdn Bhd
- **Address:** 2, Jalan Gergaji 15/14, Seksyen 15, 40200 Shah Alam, Selangor, Malaysia

---

*This document is issued by C Zero Sdn Bhd for prospective hardware vendors. Confidential — for procurement negotiation purposes.*

# PlagSini EV Charging Platform — Overview

**Document Version:** 1.0
**Date:** 1 July 2026
**Issued by:** C Zero Sdn Bhd
**Audience:** Partner / Hardware vendor introduction

---

## 1. Company

| Field | Value |
|---|---|
| **Legal entity** | C Zero Sdn Bhd |
| **Registered address** | 2, Jalan Gergaji 15/14, Seksyen 15, 40200 Shah Alam, Selangor, Malaysia |
| **Brand** | PlagSini |
| **Country of operations** | Malaysia |
| **Website** | https://plagsini.com |
| **Support portal** | https://charger.czeros.tech |
| **Primary contact** | Aqid — aqidishak28@gmail.com |
| **Technical contact** | engineering@plagsini.com |

---

## 2. Platform in one paragraph

PlagSini is a full-stack EV charging management platform built by C Zero Sdn Bhd. It combines a cloud CSMS (Charge Station Management System), a customer mobile app, self-service kiosk terminals, and a payment layer wired to Malaysian rails (Touch 'n Go eWallet, Billplz, OCBC), plus an OCPI 2.2.1 roaming interface for eMobility partners. Chargers connect over OCPP 1.6J WebSocket and are visible in real time on the operator dashboard.

---

## 3. What the platform does

### 3.1 Fleet & site management
- Register and provision charging stations
- Real-time charger status (Online / Offline / Available / Charging / Faulted)
- GPS coordinates, location metadata, connector specifications
- Fleet-wide health monitoring with automatic alerts

### 3.2 Charging session control
- Start / stop sessions remotely from admin dashboard
- Live metering: instantaneous power (kW), energy delivered (kWh), voltage, current, SOC
- Session history with billing detail
- Automatic session settlement + refund workflow for deposit/refund flows

### 3.3 Payments
- Touch 'n Go eWallet (TNG TPA — direct integration, verified sender status)
- Billplz gateway
- OCBC merchant integration
- Prepaid wallet with top-up management
- Idle-fee (anti-hogging) support
- Charging invoice emails to customers

### 3.4 Customer channels
- **AppEV mobile app** (Flutter, iOS + Android + web) — find chargers, start/stop, view history, top-up wallet
- **Self-service kiosk terminals** — Honor tablets at unmanned sites, deposit/refund payment flow, receipt printing
- **Web dashboard** — customer portal for wallet, invoices, support tickets

### 3.5 Roaming
- **OCPI 2.2.1 CPO interface** — full compliance
- Modules: Versions, Credentials, Locations, EVSEs, Connectors, Tariffs, Tariff Groups, Taxes, Sessions, CDRs, Tokens, Commands (Start/Stop), Roaming Operators
- Existing eRoaming partner discussion: Voltality (Singapore) → TNG eWallet ecosystem

### 3.6 Analytics & reporting
- Revenue by day / month / all-time
- Energy delivered (kWh, MWh)
- Fleet utilisation
- CO₂ emissions saved (Malaysia grid factor 0.585 kg/kWh)
- Peak-hour analysis
- Per-charger performance ranking

### 3.7 Support & operations
- Ticket system with staff auto-assignment by department
- SLA tracking (open / in-progress / resolved / near-SLA / overdue)
- Email notification to assigned staff
- Maintenance mode & disable-temporarily flag per charger
- Full audit logging of admin actions

---

## 4. Architecture (simplified)

```
    ┌──────────────────┐        OCPP 1.6J             ┌─────────────────┐
    │   Charging       │ ◄──── WebSocket (wss) ─────► │   PlagSini      │
    │   Station        │                              │   CSMS (Cloud)  │
    │   (Hardware)     │                              └────────┬────────┘
    └──────────────────┘                                       │
                                                               │
     ┌──────────────────┬───────────────────┬──────────────────┴──────────────┐
     │                  │                   │                                 │
     ▼                  ▼                   ▼                                 ▼
┌──────────┐    ┌──────────────┐    ┌─────────────┐                ┌──────────────────┐
│ AppEV    │    │ Kiosk        │    │ Admin       │                │ OCPI 2.2.1 Hub  │
│ Mobile   │    │ Terminal     │    │ Dashboard   │                │ (Voltality,      │
│ (iOS/And)│    │ (Honor tab)  │    │ (Web)       │                │ TNG eWallet,     │
└──────────┘    └──────────────┘    └─────────────┘                │ Vehicle OEMs)    │
                                                                   └──────────────────┘
```

---

## 5. Technology stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic |
| **Database** | MySQL 8.0 |
| **CSMS Protocol** | OCPP 1.6J (JSON over WebSocket) |
| **Roaming Protocol** | OCPI 2.2.1 (REST + JSON) |
| **Mobile app** | Flutter (Dart) — cross-platform iOS / Android / Web |
| **Web dashboard** | Vanilla HTML/CSS/JS + Chart.js |
| **Deployment** | Docker Compose on Ubuntu 24.04 LTS |
| **Reverse proxy** | Nginx (TLS 1.2/1.3, HSTS, CSP) |
| **TLS certificates** | Let's Encrypt (auto-renew) |
| **Monitoring** | Grafana 11 + Loki + Promtail |
| **Log storage** | Loki (30-day retention) |
| **DB backups** | Daily encrypted dump → Google Drive |
| **Email delivery** | Brevo SMTP |

---

## 6. Security posture

- **TLS 1.2/1.3** on all external endpoints (Let's Encrypt certificates, auto-renewal)
- **SSH root login disabled**, key-based auth only
- **Fail2ban** for brute-force protection
- **UFW firewall** with strict port allow-list
- **CSP + HSTS + X-Frame-Options** headers on all web responses
- **JWT + staff-token** authentication for admin/staff endpoints
- **Audit logging** middleware records all privileged actions (who, when, what, from where)
- **OCPP charger authentication** via per-device tokens
- **Payment callback signature verification** (HMAC / RSA depending on gateway)
- **Daily encrypted backup** to offsite cloud storage (Google Drive)
- **Rate limiting** on authentication endpoints (5 req/min per IP)
- **Regular OS + container updates** for security patches

---

## 7. Operational maturity

| Metric | Current state |
|---|---|
| **Deployment status** | Production live at charger.czeros.tech since 2026 |
| **Uptime target** | 99.5% (excluding scheduled maintenance) |
| **Chargers supported** | 473+ registered, mixed AC + DC |
| **Monitoring** | 24/7 Grafana dashboards, log aggregation, alerting |
| **Incident response** | Documented playbook, ~2 minute self-healing for OCPP state mismatch |
| **Auto-recovery** | Background healer for zombie WebSocket state, orphan session cleanup |
| **Compliance** | Malaysia PDPA aligned, PDPA-conformant data handling |

---

## 8. Integration options for hardware vendors

Two integration paths are available depending on charger firmware capability:

### 8.1 OCPP 1.6J (recommended, standard)
- Vendor firmware supports OCPP 1.6J → connect directly to PlagSini CSMS
- Zero custom firmware development required
- Standard test-then-certify process (see the OCPP Integration Guide document)

### 8.2 OCPP 2.0.1 (planned Q4 2026)
- Vendor firmware supports OCPP 2.0.1 → PlagSini roadmap-planned support
- Contact us for early-access participation

---

## 9. Existing partnerships & ecosystem

- **Touch 'n Go eWallet** — payment integration via TPA (Third-Party Access) direct link, live production
- **Voltality (Singapore)** — OCPI 2.2.1 eRoaming discussions in progress
- **Perodua / Proton EV owners** — target customer base for personal EV charging
- **Multiple charger vendors** — AION and other Chinese OEMs successfully deployed with OCPP 1.6J
- **VPS Malaysia** — hosting partner

---

## 10. Next steps

For hardware vendors interested in docking:

1. Confirm OCPP version supported by your firmware (1.6J or 2.0.1)
2. Confirm list of supported OCPP messages (see integration guide)
3. Receive PlagSini OCPP Integration Guide + provisioning package
4. Provisioning: PlagSini issues test `charge_point_id` + auth token
5. Vendor configures firmware with PlagSini endpoint + token
6. Joint docking test session (~1–2 days per model)
7. Certification sign-off → production readiness

---

## 11. Contact

For hardware integration, roaming partnerships, or commercial discussion:

- **Project Lead:** Aqid — aqidishak28@gmail.com
- **Engineering:** engineering@plagsini.com
- **Company:** C Zero Sdn Bhd
- **Production endpoint:** https://charger.czeros.tech
- **Status:** https://charger.czeros.tech/health

---

*This document is issued by C Zero Sdn Bhd for prospective hardware and roaming partners. Confidential — for partner use under mutual NDA where applicable.*

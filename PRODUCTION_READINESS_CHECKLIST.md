# PUBLIC CHARGER RND - Production Readiness Checklist

Status legend:
- `[ ]` Not started
- `[-]` In progress
- `[x]` Done

## 1) Release Decision

- [ ] **Launch mode decided**: `Pilot (soft launch)` or `Full public launch`
- [ ] **Scope frozen** for release candidate (no new features during hardening)
- [ ] **Owner assigned** for each area: Backend, App, Infra, Security, Ops

---

## 2) Critical Blockers (Must pass before public launch)

### 2.1 Payment (Provider-agnostic gateway integration)
- [x] Gateway abstraction supports multi-provider plug-in (Fiuu/TnG/OCBC/Billplz/manual)
- [ ] Map gateway statuses to internal statuses (`pending/success/failed/expired/refunded`)
- [x] Enforce callback authenticity (signature/secret validation per provider spec)
- [x] Idempotency protection for callback retries (no duplicate wallet credit)
- [x] Reconciliation script/report (gateway settlements vs `payment_transactions`)
- [ ] Refund and chargeback flow tested end-to-end

**Pass criteria**
- 0 duplicate credits in repeated callback simulation
- 100% traceability from gateway ref to wallet transaction
- Reconciliation variance = 0 for test window

### 2.2 Database migrations
- [x] Introduce formal migration workflow (versioned migrations)
- [x] Baseline migration generated from current schema
- [x] Staging migration dry-run completed
- [x] Rollback procedure documented and tested

**Pass criteria**
- Fresh DB + migrated DB both pass smoke tests
- Rollback tested at least once in staging

### 2.3 Auth/session hardening
- [ ] Staff auth/session made production-safe for multi-instance deployment
- [ ] Token/session expiry and invalidation behavior verified
- [ ] Access control matrix validated (admin/manager/staff/user)

**Pass criteria**
- No unauthorized access in role tests
- Session behavior consistent after restart/deploy

### 2.4 Security baseline
- [-] All secrets loaded from env/secret manager (no hardcoded secrets)
- [ ] OCPP over secure channel (`wss`) in production
- [x] Rate limiting enabled for sensitive endpoints
- [ ] Final security test pass (critical/high findings closed)

**Pass criteria**
- Critical vulnerabilities = 0
- High vulnerabilities = 0 (or accepted with explicit sign-off)

---

## 3) Reliability and Operations

### 3.1 Backups and recovery
- [ ] Automated DB backup schedule active
- [ ] Retention policy defined
- [ ] Restore drill performed (prove recoverability)

**Pass criteria**
- Point-in-time restore proven in staging
- Restore time objective documented

### 3.2 Monitoring and alerting
- [ ] Centralized logs for all services
- [ ] Metrics dashboard for API, DB, OCPP, payment callbacks
- [ ] Alerts configured (5xx spike, DB down, queue/backlog, callback failures)

**Pass criteria**
- Alerts tested and routed to on-call owner

### 3.3 Runbooks
- [ ] Incident runbook for payment failures
- [ ] Incident runbook for OCPP disconnect storm
- [ ] Incident runbook for DB recovery

**Pass criteria**
- Team can execute runbook without guessing

---

## 4) Environment and Infrastructure

### 4.1 Environment separation
- [-] Distinct `dev`, `staging`, `production` configs
- [-] Production env audited for required variables
- [-] TLS certificates and renewals validated

### 4.2 Capacity sizing
- [ ] Pilot server sizing approved
- [ ] Production sizing approved
- [ ] Load assumptions documented (users, chargers, peak tx/min)

**Baseline recommendation**
- Pilot: 4 vCPU / 8 GB RAM / 120 GB SSD
- Production split: app node + dedicated DB node

---

## 5) App and API Quality Gates

### 5.1 Core smoke tests
- [ ] `AppEV` loads and can complete core user path
- [ ] `ChargingPlatform` API health/docs reachable
- [ ] `CustomerService` health and escalation path works
- [ ] Admin login and analytics pages function end-to-end

### 5.2 Business flow tests
- [ ] Register/login user
- [ ] Start charging / stop charging
- [ ] Payment process and callback settlement
- [ ] Ticket escalation from chatbot to support

**Pass criteria**
- All core flows pass in staging with real-like data

---

## 6) Go-Live Gates

- [-] Change freeze enabled 24-48h before launch
- [-] Final backup taken before release
- [-] Rollback release plan prepared
- [ ] Launch day owner roster confirmed
- [-] Post-launch monitoring war-room active for first 24h

**Go decision**
- [ ] `GO` approved by Product + Engineering + Ops + Security

---

## 7) Immediate Next Actions (Recommended this week)

1. ~~Convert ad-hoc schema patching to formal migrations.~~ (baseline + Alembic scaffold added)
2. ~~Finalize payment callback verification + idempotency test suite.~~ (callback verification + regression tests added)
3. ~~Add reconciliation report for payment settlements.~~ (settlement-aware reconciliation script added)
4. Complete backup restore drill and write runbook.
5. Run final staging UAT and security regression check.


# TNG OrderCode API — Integration Analysis for PlagSini EV Charging Platform

**Document:** OrderCode Creation API v1.04 (07 Feb 2024)  
**Phase:** Payment integration (current)  
**Future:** POS machine (debit/credit, QR display)

---

## 1. TNG OrderCode Flow (per spec)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  PlagSini   │     │  TNG OrderCode    │     │  User TNG App    │
│  Backend    │     │  API              │     │                 │
└──────┬──────┘     └────────┬──────────┘     └────────┬────────┘
       │                     │                         │
       │ 1. POST create order │                         │
       │    (signed request)  │                         │
       │ ───────────────────►│                         │
       │                     │                         │
       │ 2. orderQrCode      │                         │
       │ ◄───────────────────│                         │
       │                     │                         │
       │ 3. Show QR to user  │                         │
       │ ─────────────────────────────────────────────►│
       │                     │                         │
       │                     │ 4. User scans QR, pays   │
       │                     │ ◄───────────────────────│
       │                     │                         │
       │ 5. POST notifyUrl   │                         │
       │    (callback)       │                         │
       │ ◄───────────────────│                         │
       │                     │                         │
       │ 6. Verify signature, credit wallet           │
       │                     │                         │
```

**Key difference vs Billplz/FPX:** TNG returns **QR code data** (`orderQrCode`), not a payment URL. User must **scan QR with TNG app** to pay.

---

## 2. Current Implementation Status

### 2.1 Backend (ChargingPlatform) — ✅ Mostly ready

| Component | Status | Notes |
|-----------|--------|-------|
| `TngGateway.create_payment` | ✅ | Request format, signing, amount in sen, product codes |
| `TngGateway.verify_callback` | ✅ | RSA verify, parse merchantTransId, acquirementId |
| `POST /api/payment/topup` | ✅ | Returns `qr_code` when TNG success |
| `POST /api/payment/callback/tng` | ✅ | TNG bypasses X-Callback-Secret, uses RSA |
| `get_gateway("tng")` | ✅ | TNG registered in GATEWAY_REGISTRY |

### 2.2 Gaps to close

| Gap | Action |
|-----|--------|
| **Base URL** | Get from TNGD. Env: `PAYMENT_TNG_API_URL` |
| **Credentials** | clientId, merchantId from TNG. Sandbox: doc values |
| **TNG public key** | Get from TNGD for callback verification |
| **Callback URL** | Must be publicly reachable. Set in PaymentGatewayConfig |
| **AppEV QR display** | App expects `payment_url`; TNG returns `qr_code` — **need to handle** |

---

## 3. Integration Architecture

### 3.1 Current phase: App + Web

```
User (App)                    ChargingPlatform              TNG API
    │                                │                         │
    │ POST /api/payment/topup         │                         │
    │ {user_id, amount, payment_method: "tng"}                  │
    │ ──────────────────────────────►│                         │
    │                                │ POST ordercode.create    │
    │                                │ (signed) ───────────────►│
    │                                │                         │
    │                                │ orderQrCode ◄────────────│
    │                                │                         │
    │ {success, qr_code, txn_ref}    │                         │
    │ ◄──────────────────────────────│                         │
    │                                │                         │
    │ Display QR (from qr_code)      │                         │
    │ User scans with TNG app        │                         │
    │                                │                         │
    │                                │ POST /callback/tng       │
    │                                │ ◄────────────────────────│ (TNG server)
    │                                │ Verify → Credit wallet   │
    │                                │                         │
    │ Poll /transactions/{ref}       │                         │
    │ ◄──────────────────────────────│                         │
```

### 3.2 Future phase: POS machine

```
POS Machine (future)              ChargingPlatform              TNG API
    │                                    │                         │
    │ Same flow as app                    │                         │
    │ - Display QR on screen              │                         │
    │ - Or: debit/credit terminal         │                         │
    │   (different TNG product if any)   │                         │
```

- **QR display:** Same `orderQrCode` flow — POS gets `qr_code` from API, renders QR on screen.
- **Debit/credit:** Would need separate TNG product/API (not in current OrderCode doc).

---

## 4. Request/Response Mapping (TNG spec → PlagSini)

### 4.1 Create order request

| TNG Field | PlagSini Source | Notes |
|-----------|-----------------|-------|
| `head.version` | `"1.0"` | Fixed |
| `head.function` | `"alipayplus.acquiring.ordercode.create"` | Fixed |
| `head.clientId` | `PAYMENT_TNG_API_KEY` / sandbox | From TNGD |
| `head.reqTime` | `datetime.utcnow()` | ISO 8601 +08:00 |
| `head.reqMsgId` | UUID | Unique per request |
| `body.merchantId` | `PAYMENT_TNG_MERCHANT_ID` | From TNGD |
| `body.subMerchantName` | `"PlagSini EV"` | Configurable |
| `body.mcc` | `5732` (default) | EV charging |
| `body.orderTitle` | `"PlagSini EV Top-Up RM50.00"` | From description |
| `body.orderAmount` | `{"value":"5000","currency":"MYR"}` | **value in sen** |
| `body.merchantTransId` | `transaction_ref` (TXN-xxx) | Our ref |
| `body.productCode` | `51051000101000100046` (TNGD) or `51051000101000300048` (DuitNow) | Configurable |
| `body.envinfo` | `{"terminalType":"SYSTEM","orderTerminalType":"WEB"}` | WEB for app |
| `body.notifyUrl` | `callback_url` from gateway config | Must be HTTPS in prod |
| `body.effectiveSeconds` | `"600"` | 10 min expiry |

### 4.2 Create order response

| TNG Field | PlagSini Use |
|-----------|--------------|
| `orderQrCode` | Show as QR for user to scan |
| `acquirementId` | Store as `gateway_transaction_id` |
| `merchantTransId` | Echo of our `transaction_ref` |
| `resultInfo.resultStatus` | S = success |

### 4.3 Callback (notifyUrl)

| TNG Sends | PlagSini Action |
|-----------|-----------------|
| `{"response":{"head":{...},"body":{...}},"signature":"..."}` | Verify RSA with TNG public key |
| `body.merchantTransId` | Match to `PaymentTransaction.transaction_ref` |
| `body.acquirementId` | Fallback lookup |
| `body.orderAmount.value` | Amount in sen → RM |
| `resultInfo.resultStatus` | S = success → credit wallet |

---

## 5. Product codes (per spec)

| Product | Code | Use case |
|---------|------|----------|
| TNGD QR | `51051000101000100046` | User pays via TNG app |
| DuitNow QR | `51051000101000300048` | User pays via any DuitNow app |

Default: TNGD QR. Override via `PAYMENT_TNG_PRODUCT_CODE` or `extra_config.product_code`.

---

## 6. Terminal type for future POS

| Scenario | `envinfo` |
|----------|-----------|
| App / Web | `{"terminalType":"SYSTEM","orderTerminalType":"WEB"}` |
| POS (future) | `{"terminalType":"SYSTEM","orderTerminalType":"..."}` — confirm with TNG for POS |

---

## 7. Action Items for Phase 1 (Payment integration)

### 7.1 Backend (ChargingPlatform)

1. **Env vars** (from TNGD):
   - `PAYMENT_TNG_API_URL` — Base URL (e.g. `https://api.tng.com.my` or sandbox)
   - `PAYMENT_TNG_API_KEY` — clientId
   - `PAYMENT_TNG_MERCHANT_ID` — merchantId
   - `PAYMENT_TNG_PRIVATE_KEY` — Partner private key (PKCS8 PEM)
   - `PAYMENT_TNG_PUBLIC_KEY` — TNGD public key (PKCS8 PEM)

2. **PaymentGatewayConfig** (DB / Admin UI):
   - Add gateway `tng`, `supports_ewallet=True`
   - `callback_url` = `https://your-domain.com/api/payment/callback/tng`
   - `sandbox_url` / `production_url` if not using env

3. **Callback reachability:** TNG must reach `callback_url` — use ngrok for local dev.

### 7.2 App (AppEV)

1. **Handle `qr_code` in top-up flow:**
   - If `qr_code` present and `payment_url` empty → show QR instead of opening URL
   - Use `qr_flutter` or similar to render `orderQrCode` as QR image
   - Keep polling `/transactions/{ref}` until success/failed

2. **Gateway selection:**
   - Use `GET /api/payment/methods` to get available methods
   - Pass `gateway_name: "tng"` when user selects TNG/DuitNow

3. **UX:** Show “Scan with TNG app” when displaying QR.

### 7.3 TNGD

1. Register merchant, get clientId, merchantId, base URL
2. Exchange keys: send partner public key, receive TNGD public key
3. Confirm callback payload format for `notifyUrl` (if different from create response)

---

## 8. Future: POS machine

| Feature | Approach |
|---------|----------|
| **QR display** | POS calls same `POST /api/payment/topup` (or dedicated endpoint), gets `qr_code`, renders on screen |
| **Debit/credit** | Requires separate TNG product; not in current OrderCode doc |
| **Charging at POS** | POS can trigger charging + top-up in one flow (backend orchestrates) |

---

## 9. Summary

| Layer | Status | Next step |
|-------|--------|-----------|
| **TngGateway** | ✅ Implemented | Add credentials + base URL |
| **API topup/callback** | ✅ Ready | Configure callback_url |
| **AppEV** | ⚠️ Gap | Add QR display for `qr_code` |
| **Credentials** | ❌ Pending | Get from TNGD |
| **POS** | 📋 Future | Same QR flow; debit/credit needs new TNG product |

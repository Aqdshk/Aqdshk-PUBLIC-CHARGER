# TNG Digital TPA Integration — Authoritative Reference (Spec v1.32)

Compiled from the official TNGD package `TPA Integration API SPEC 1.32`:
- `TPA_Standardization_Tech_v0.2.docx` (main technical spec, 26 Nov 2019)
- `Standardization Document - TPA v1.6.docx` (extendInfo addendum)
- `TPA integration/TnG Merchant Integration API/**/*.htm` (per-endpoint specs)
- `integration SDK - php.zip` (reference PHP SDK, v PHP-1.0.0.20180302)
- Java SDK `integration-openapi-sdk-1.0.7.20180705.jar` (META-INF only — `.class` not decompiled)
- `MERCHANT_SETTLEMENT_217120000000252999999_20201229.csv` (production-format sample)
- `B scan C.postman_collection.json` (request URL pattern)

> Throughout this doc, **"A+"** and **"Alipay+"** are TNGD's white-label of Ant Group's Alipay+ platform — the API is identical to Alipay+ acquiring v2.0. The package mixes "DANA", "Alipay+", "A+", and "TNGD" — they refer to the same backend.

---

## A. Envelope spec (authoritative)

### A.1 Request envelope (merchant → TNGD)

```json
{
  "request": {
    "head": { ... },
    "body": { ... }
  },
  "signature": "<base64 RSA-SHA256 of the substring {\"head\":{...},\"body\":{...}}>"
}
```

Source: `TPA_Standardization_Tech_v0.2.docx` §2.1, `Request Header/index.htm`, `SdkClient.php::assembleRequestMsg`.

### A.2 Request.head (mandatory on every call)

Source: `00. Interface Specification/Request And Response Head/Request Header/index.htm` and every endpoint's §5.1.

| # | name          | type     | len | Req | Description / Sample |
|---|---------------|----------|-----|-----|----------------------|
| 1 | `version`     | string   | 8   | M   | API version. Per endpoint spec the value is **`"2.0"`** (endpoint `.htm` all sample `2.0`; the v0.2 main docx sample uses `"1.0"` — drift, use `2.0`). |
| 2 | `function`    | string   | 128 | M   | API name, e.g. `alipayplus.retail.pay`. |
| 3 | `clientId`    | string   | 32  | M   | Assigned by TNGD at onboarding (sample `2014000014442`). |
| 4 | `reqTime`     | datetime | —   | M   | ISO-8601 / RFC 3339 §5.6 with offset, e.g. `2001-07-04T12:08:56+05:30`. PHP SDK uses `date('c')` → `2018-02-23T10:19:45+08:00`. |
| 5 | `reqMsgId`    | string   | 64  | M   | Unique per-request UUID. Identifies the *system* request, NOT the business transaction. |
| 6 | `clientSecret`| string   | 64  | M   | Assigned by TNGD. **Sent in cleartext inside the signed body** — pair with HTTPS and rotate. |
| 7 | `reserve`     | string   | 256 | O   | Free-form K/V JSON string. PHP SDK always sends `""`. |
| — | `sdkVersion`  | string   | —   | O   | Non-spec extension added by PHP SDK (`"PHP-1.0.0.20180302"`), used for client telemetry. |

`M/O/ME/C` legend (from htm tables): `M` mandatory, `O` optional, `ME` mandatory-enum / mandatory-empty-allowed, `C` conditional (see Condition column).

### A.3 Request.body
Per-endpoint — see Section C.

### A.4 Response envelope (TNGD → merchant)

```json
{
  "response": {
    "head": { ... },
    "body": { ... }
  },
  "signature": "<base64 RSA-SHA256 of the substring {\"head\":{...},\"body\":{...}}>"
}
```

### A.5 Response.head

Source: `Response Header/index.htm`. Header echoes the request except:
- `respTime` (datetime, M) instead of `reqTime`.
- No `clientSecret` is returned.
- `reqMsgId` is **echoed verbatim** from the request — use this to correlate.

| # | name      | type     | len | Req | Description |
|---|-----------|----------|-----|-----|-------------|
| 1 | `version` | string   | 8   | M   | Same as request. (Spec table sample is `1.2`; live samples are `2.0`.) |
| 2 | `function`| string   | 128 | M   | Same as request. |
| 3 | `clientId`| string   | 32  | M   | Same as request. |
| 4 | `respTime`| datetime | —   | M   | RFC 3339. |
| 5 | `reqMsgId`| string   | 64  | M   | Echoes request `reqMsgId`. |
| 6 | `reserve` | string   | 256 | O   | Reserved. |

### A.6 SPI Request envelope (TNGD → merchant async callback)

Source: `SPI Request Header/index.htm`, `alipayplus.acquiring.notify.orderFinish.htm`.

```json
{
  "request": {
    "head": {
      "version": "2.0",
      "function": "alipayplus.acquiring.notify.orderFinish",
      "clientId": "PAYTW3IN51",
      "reqTime": "...",
      "reqMsgId": "..."
    },
    "body": { ... }
  },
  "signature": "<base64 RSA-SHA256 from TNGD's private key>"
}
```

SPI head fields:
| # | name      | type     | len | Req | Notes |
|---|-----------|----------|-----|-----|-------|
| 1 | `version` | string   | 8   | M   | |
| 2 | `function`| string   | 128 | M   | |
| 3 | `clientId`| string   | 32  | M   | TNGD core's clientId (sample `PAYTW3IN51`) — NOT the merchant's. |
| 4 | `reqTime` | datetime | —   | M   | |
| 5 | `reqMsgId`| string   | 64  | M   | |

> **No `clientSecret` is sent on SPI requests** — merchant authenticates the message by RSA-verifying the signature with TNGD's server public key.

### A.7 SPI Response envelope (merchant → TNGD ACK)

Source: `SPI Response Header/index.htm`, `SPI Response Body/index.htm`.

```json
{
  "response": {
    "head": {
      "version": "2.0",
      "function": "alipayplus.acquiring.notify.orderFinish",
      "clientId": "PAYTW3IN51",   // echo
      "respTime": "...",
      "reqMsgId": "..."           // echo
    },
    "body": {
      "resultInfo": {
        "resultStatus": "S",
        "resultCodeId": "00000000",
        "resultCode": "SUCCESS",
        "resultMsg": "success"
      }
    }
  },
  "signature": "<base64 RSA-SHA256 with merchant's private key>"
}
```

---

## B. Signature algorithm (authoritative)

### B.1 Algorithm
- **`SHA256withRSA` (PKCS#1 v1.5 padding), RSA-2048**, base64-encoded.
- Spec docx §3.2: *"The signature is generated with SHA256 with RSA 2048 algorithm, using the value of the 'request' or 'response' object, including 'head', 'body' and the {} outside of the 'head' and 'body'."*

### B.2 Exact bytes that are signed
The substring **between** the `{` that opens `head` and the `}` that closes `body`, including both braces:

```
{"head":{...},"body":{...}}
```

Verified from PHP SDK `SdkClient.php::constructSignatureMsg`:
```php
$signatureContent = "{".$headerMsg.",".$bodyMsg."}";
$signature = SignatureUtil::sign($signatureContent, $this->clientRsaPrivateKey);
```

And from `splitResponseMsg` (verifier side) — it locates `{"head":` and `,"signature":` and signs/verifies that slice byte-for-byte:
```php
$signatureContent = substr($responseMsg, $headerPos, $signaturePos - $headerPos);
```

**Implication — critical:**
- The serialization is **not re-serialized before signing**. You sign the *exact byte sequence* you transmit. Key order, whitespace, escaping of `\/` vs `/`, `\uXXXX` escapes — all must be byte-identical on both sides.
- Verifier on TNGD side will do the same: extract the literal bytes between `{"head":` and `,"signature":` (then trim trailing `}` so the slice ends at `}}`). So **don't pretty-print, don't add whitespace, don't reorder** after signing.
- The docx (§3.2): *"It is recommended to sign and verify with the plaintext, no whitespace and comments."*

### B.3 Key format
| Item                    | Per spec docx                                              | Per PHP SDK source                                                                                                |
|-------------------------|------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| Algorithm               | RSA-2048                                                   | OPENSSL_ALGO_SHA256                                                                                               |
| Merchant private key    | **PKCS#8 PEM** (`-----BEGIN PRIVATE KEY-----`)             | Wrapped as **`-----BEGIN RSA PRIVATE KEY-----` (PKCS#1)** — see `SignatureUtil::sign`                              |
| Merchant public key (given to TNGD) | PKCS#8 (`-----BEGIN PUBLIC KEY-----`)              | n/a                                                                                                               |
| TNGD server public key (given to merchant) | PKCS#8 PEM                                        | Wrapped as `-----BEGIN PUBLIC KEY-----` (X.509 SPKI) — see `SignatureUtil::verify`                                |

> **DRIFT vs spec (flagged):** the PHP SDK calls the input "private key" but wraps it with `-----BEGIN RSA PRIVATE KEY-----` (the PKCS#1 marker). OpenSSL is tolerant — both PKCS#1 and PKCS#8 unencrypted PEM bodies work behind that header in most builds — but if you generate a strict PKCS#8 key (`-----BEGIN PRIVATE KEY-----`), strip the headers before passing the base64 body into the SDK, *or* fix the SDK to use the right header. The docx unambiguously requires **PKCS#8** for both private and public; recommend keeping keys in PKCS#8 and patching the wrapper.

### B.4 How keys are generated (per docx §3.1.1)
```
ssh-keygen -b 2048 -t rsa                       # generates id_rsa (PKCS#1) + id_rsa.pub (OpenSSH)
# convert private key to PKCS#8 using https://decoder.link/rsa_converter
ssh-keygen -e -m PKCS8 -f id_rsa.pub            # convert public key to PKCS#8
```
A modern equivalent that avoids the third-party converter:
```
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out merchant_private_pkcs8.pem
openssl rsa -in merchant_private_pkcs8.pem -pubout -out merchant_public_pkcs8.pem
```
Submit `merchant_public_pkcs8.pem` to TNGD; keep the private key offline-signed only.

### B.5 Verification of TNGD responses (mandatory)
PHP SDK `verifySignature` always verifies unless `signSwitch=false` is explicitly set. Treat verification failure as a fatal error and DO NOT trust the body. Spec error code `00000007 INVALID_SIGNATURE` is what TNGD returns when *they* can't verify yours.

---

## C. API endpoints

### C.0 URL pattern (common)

From `SdkClient.php::constructUrl` and Postman collection:
```
POST {baseUrl}/{function-with-dots-as-slashes}.htm
Content-Type: application/json;charset=utf-8
```
e.g. `alipayplus.retail.pay` → `POST {baseUrl}/alipayplus/retail/pay.htm`.

Environments (docx §"Integration Checklist"):
| Env       | Base URL                              |
|-----------|---------------------------------------|
| Sandbox   | `https://api-sd.tngdigital.com.my`    |
| Production| (to be issued by TNGD on go-live; ask) |

Default product code for retail pay: **`51051000101000100040`** (per docx). Sample `51011000100000000001` in the .htm files is generic — use the docx value for TNGD.

---

### C.1 `alipayplus.retail.pay`

Source: `04. RetailPay/RetailPay API/alipayplus.retail.pay.htm`. Idempotence key: `merchantId` + `order.merchantTransId`. Key info compared on retry: `productCode`, `order.orderAmount`, `authCode` — mismatch ⇒ `REPEAT_REQ_INCONSISTENT`.

#### Request.body

| # | name          | type                       | len  | Req | Notes |
|---|---------------|----------------------------|------|-----|-------|
| 1 | `merchantId`  | string                     | 32   | M   | TNGD merchant id. |
| 2 | `productCode` | string                     | 32   | M   | Use `51051000101000100040`. |
| 3 | `mcc`         | string                     | 64   | O   | IRS MCC list. |
| 4 | `authCodeType`| enum AuthCodeTypeEnum      | 32   | M   | `BAR_CODE` / `WAVE_CODE`. |
| 5 | `authCode`    | string                     | 64   | M   | The 18-digit code scanned from the TNG e-Wallet user. |
| 6 | `order`       | Order                      | —    | M   | See §D.Acquiring. |
| 7 | `notifyUrl`   | string                     | 256  | O   | HTTP/HTTPS URL TNGD will call back asynchronously. |
| 8 | `envInfo`     | EnvInfo                    | —    | M   | `orderTerminalType` mandatory. |
| 9 | `shopInfo`    | ShopInfo                   | —    | O   | |
| 10| `extendInfo`  | string (JSON)              | 4096 | O   | **For retail/offline TPA: 12 fields mandatory per addendum — see §H.5.** |

#### Response.body (200 OK)

| # | name              | type     | Req-Condition |
|---|-------------------|----------|---------------|
| 1 | `resultInfo`      | ResultInfo | M |
| 2 | `merchantTransId` | string(64) | C — present when `resultCodeId` ∈ {`00000000`, `PAYMENT_IN_PROCESS`, `USER_PAYING`}. |
| 3 | `acquirementId`   | string(64) | C — same condition. |
| 4 | `orderAmount`     | Money      | C — same condition. |
| 5 | `createTime`      | datetime   | C — same condition. |
| 6 | `paidTime`        | datetime   | C — only when `resultCodeId == 00000000`. |

#### Endpoint-specific result codes
| ResultCodeId | ResultCode                       | Status | Notes |
|--------------|-----------------------------------|--------|-------|
| 00000000     | SUCCESS                          | S | |
| 12005112     | REPEAT_REQ_INCONSISTENT          | F | Same merchantTransId, different key info. |
| 12005103     | CURRENCY_NOT_CORRECT             | F | |
| 12005009     | AUTH_CODE_ILLEGAL                | F | Code malformed / wrong wallet. |
| 12005010     | AUTH_CODE_ALREADY_USED           | F | Codes are one-time. |
| 12005104     | AMOUNT_EXCEEDS_LIMIT             | F | |
| 12005005     | NOAUTH                           | F | Merchant contract issue. |
| 12005200     | MERCHANT_STATUS_ABNORMAL         | F | |
| 12005110     | USER_STATUS_ABNORMAL             | F | |
| 12005011     | PAYMENT_REQUEST_HAS_RISK         | F | Risk engine rejected. |
| **12005012** | **USER_PAYING**                  | **U** | Risk challenge (OTP/password). **Poll order.query.** |
| 12005100     | ORDER_IS_CLOSED                  | F | |
| 12005008     | ORDER_IS_CANCELED                | F | |
| **12005215** | **PAYMENT_IN_PROCESS**           | **U** | Treat as pending; query/poll. |
| 00000019     | PROCESS_FAIL                     | F | |
| 12005007     | ACCOUNT_STATUS_ABNORMAL          | F | |
| 12005115     | BALANCE_NOT_ENOUGH               | F | |
| 12005014     | WITHOUT_AVAILABLE_PAY_METHOD     | F | |
| 12005023     | USER_BOUND_ASSET_NOT_EXIST       | F | |
| 12005024     | CHANNEL_STATUS_NOT_ENABLE        | F | |
| 12005025     | CHANNEL_OVER_LIMIT               | F | |
| 12005135     | MERCHANT_AND_SHOP_NOT_MATCH      | F | |
| 12005136     | SHOP_NOT_EXIST                   | F | |
| 12005137     | SHOP_STATUS_ABNORMAL             | F | |
| 12005028     | AMOUNT_EXCEED_DAILY_LIMIT        | F | |
| 12005029     | AMOUNT_EXCEED_SINGLE_LIMIT       | F | |
| 12005030     | AMOUNT_EXCEED_MONTH_LIMIT        | F | |
+ all basic codes from §E.

#### Handling rules (from .htm §3 "Function Logic")
1. If response is `SYSTEM_ERROR` (00000900) or `PAYMENT_IN_PROCESS` → query via `order.query`.
2. If `USER_PAYING` → poll `order.query` at intervals until success or your client-side timeout.
3. If `resultStatus == F` → create a NEW transaction (new `merchantTransId`).
4. If `resultStatus == U` and querying many times still shows `statusDetail.acquirementStatus == INIT` → call `order.cancel`.

> The PHP SDK class declares the function as `alipayplus.acquiring.retail.pay` (note the extra `.acquiring`). The .htm spec, Postman collection, and main docx all say `alipayplus.retail.pay`. **Use `alipayplus.retail.pay`** — the SDK string is a bug.

---

### C.2 `alipayplus.acquiring.order.query`

Source: `01. Acquiring/Acquiring API/alipayplus.acquiring.order.query.htm`. Idempotence: not stateful (read-only).

#### Request.body
| # | name             | type   | len | Req | Notes |
|---|------------------|--------|-----|-----|-------|
| 1 | `merchantId`     | string | 32  | M   | |
| 2 | `acquirementId`  | string | 64  | C   | One of these two must be set; if both, `acquirementId` wins. |
| 3 | `merchantTransId`| string | 64  | C   | |

#### Response.body
| # | name              | type             | Req-Condition |
|---|-------------------|------------------|---------------|
| 1 | `resultInfo`      | ResultInfo       | M |
| 2 | `acquirementId`   | string(64)       | C — if 00000000 |
| 3 | `merchantTransId` | string(64)       | C — if 00000000 |
| 4 | `buyer`           | InputUserInfo    | O |
| 5 | `seller`          | InputUserInfo    | O |
| 6 | `orderTitle`      | string(256)      | C — if 00000000 |
| 7 | `extendInfo`      | string(4096)     | O |
| 8 | `amountDetail`    | AmountDetail     | C — if 00000000 |
| 9 | `timeDetail`      | TimeDetail       | C — if 00000000 |
| 10| `statusDetail`    | StatusDetail     | C — if 00000000 |
| 11| `goods`           | list<Goods>      | O |
| 12| `shippingInfo`    | list<ShippingInfo>| O |
| 13| `orderMemo`       | string(256)      | O |
| 14| `paymentViews`    | list<PaymentView>| C — when paid |

#### Endpoint result codes (additional to basic)
| Id | Code | Status |
|----|------|--------|
| 00000000 | SUCCESS | S |
| 00000004 | PARAM_ILLEGAL | F |
| 00000900 | SYSTEM_ERROR | U |
| **00000020** | **TARGET_NOT_FOUND** | **F** | order not exist |

> Use `statusDetail.acquirementStatus` (StatusDetailEnum) as the authoritative payment outcome: `INIT`, `SUCCESS`, `CLOSED`, `PAYING`, `MERCHANT_ACCEPT`, `CANCELLED`.

---

### C.3 `alipayplus.acquiring.order.cancel`

Source: `alipayplus.acquiring.order.cancel.htm`. Idempotence: `merchantId` + (`merchantTransId` OR `acquirementId`).

> Spec §2 (paraphrased): *"Upon success of payCancel, merchant may safely assume the transaction never happened. A cancelled transaction will NOT appear in the settlement report."* Refund channel can be slow but A+ guarantees the money goes back to the user.

#### Request.body
| # | name             | type   | len | Req | Notes |
|---|------------------|--------|-----|-----|-------|
| 1 | `merchantId`     | string | 32  | M   | |
| 2 | `acquirementId`  | string | 64  | C   | One of these two; `acquirementId` wins if both. |
| 3 | `merchantTransId`| string | 64  | C   | |

#### Response.body
| # | name | type | Req |
|---|------|------|-----|
| 1 | `resultInfo` | ResultInfo | M |
| 2 | `acquirementId` | string(64) | C — on SUCCESS |
| 3 | `merchantTransId` | string(64) | C — on SUCCESS |
| 4 | `cancelTime` | datetime | O |

#### Endpoint result codes
00000000 SUCCESS S · 00000019 PROCESS_FAIL F · 00000004 PARAM_ILLEGAL F · 00000002 PARAM_MISSING F · 00000900 SYSTEM_ERROR U · 12005110 USER_STATUS_ABNORMAL F · 12005200 MERCHANT_STATUS_ABNORMAL F · 12005003 ORDER_STATUS_INVALID F · 12005004 ORDER_IS_FROZEN F · 12005002 ORDER_NOT_EXISTS F · 12005017 CANCEL_NOT_ALLOWED F · 12005018 CANCEL_EXPIRED F · 12005019 REFUND_TRANSACTION_EXIST F · 12005020 DISPUTE_TRANSACTION_EXIST F · 12005021 MERCHANT_ACCOUNT_BALANCE_NOT_ENOUGH F · 12005022 MERCHANT_ACCOUNT_ABNORMAL F · 12005027 BALANCE_EXCEED_LIMIT F.

> Spec §2: if cancel returns `TARGET_NOT_FOUND` after order.query, retry cancel later.

---

### C.4 `alipayplus.acquiring.order.refund`

Source: `alipayplus.acquiring.order.refund.htm`. Idempotence: `merchantId` + `requestId`. To retry on timeout/U-status, **reuse the same `requestId`** — different `acquirementId` for the same `requestId` ⇒ `REPEAT_REQ_INCONSISTENT`.

#### Request.body
| # | name                  | type     | len  | Req | Notes |
|---|-----------------------|----------|------|-----|-------|
| 1 | `requestId`           | string   | 64   | M   | Merchant-generated, idempotency key. |
| 2 | `merchantId`          | string   | 32   | M   | |
| 3 | `acquirementId`       | string   | 64   | M   | |
| 4 | `payoutAccountNo`     | string   | 32   | O   | If null, contract default account is used. Must be in merchant's contract list. |
| 5 | `refundAmount`        | Money    | —    | M   | Must be > 0. Partial allowed; sum across refunds enforced server-side. |
| 6 | `refundAppliedTime`   | datetime | —    | O   | RFC3339. |
| 7 | `actorType`           | enum ActorTypeEnum | 32 | O | `BACK_OFFICE`, etc. |
| 8 | `refundReason`        | string   | 1024 | O   | |
| 9 | `returnChargeToPayer` | boolean  | —    | O   | Default `false`. Only valid if contract allows merchant to control charge return. |
| 10| `destination`         | enum RefundDestinationEnum | 32 | O | `TO_BALANCE` / `TO_SOURCE`. |
| 11| `extendInfo`          | string   | 4096 | O   | |

#### Response.body
| # | name | type | Req |
|---|------|------|-----|
| 1 | `resultInfo` | ResultInfo | M |
| 2 | `refundId` | string(64) | C — on 00000000 OR 12005436 |
| 3 | `requestId` | string(64) | C — same |
| 4 | `acquirementId` | string(64) | C — same |
| 5 | `refundAmount` | Money | C — same |
| 6 | `refundTime` | datetime | C — same |

> Note: the response *sample* in the .htm only shows `resultInfo` — the table is authoritative; refund metadata is returned when result is SUCCESS or REFUND_IN_PROCESS.

#### Endpoint result codes
00000000 SUCCESS S · 00000004 PARAM_ILLEGAL F · 00000900 SYSTEM_ERROR U · 00000019 PROCESS_FAIL F · 12005002 ORDER_NOT_EXISTS F · 12005003 ORDER_STATUS_INVALID F · 12005004 ORDER_IS_FROZEN F · 12005103 CURRENCY_NOT_SAME F · 12005104 AMOUNT_EXCEEDS_LIMIT F · 12005105 AGREEMENT_REFUND_NOT_ALLOWED F · 12005106 AGREEMENT_MULTI_REFUND_NOT_ALLOWED F · 12005107 AGREEMENT_SPECIFIED_ACCOUNT_NOT_EXIST F · 12005108 AGREEMENT_REFUND_TIME_EXCEEDS_LIMIT F · 12005112 REPEAT_REQ_INCONSISTENT F · 12003001 MERCHANT_NOT_EXIST F · 12005109 USER_NOT_EXISTS F · 12005110 USER_STATUS_ABNORMAL F · 12005200 MERCHANT_STATUS_ABNORMAL F · 12005021 MERCHANT_ACCOUNT_BALANCE_NOT_ENOUGH F · 12005007 ACCOUNT_STATUS_ABNORMAL F · 12005027 BALANCE_EXCEED_LIMIT F · **12005436 REFUND_IN_PROCESS U** — retry with same `requestId`.

---

### C.5 `alipayplus.acquiring.refund.query`

Source: `alipayplus.acquiring.refund.query.htm`. No idempotence. Marked **optional** in RetailPay product matrix.

#### Request.body
| # | name | type | len | Req | Notes |
|---|------|------|-----|-----|-------|
| 1 | `merchantId` | string | 32 | M | |
| 2 | `refundId` | string | 64 | C | If set, returns one specific refund; ignores others. |
| 3 | `acquirementId` | string | 64 | C | If `refundId` null and this set: returns all refunds on this transaction. |
| 4 | `merchantTransId` | string | 64 | C | Used only if both `refundId` and `acquirementId` are null. |

#### Response.body
| # | name | type | Req |
|---|------|------|-----|
| 1 | `resultInfo` | ResultInfo | M |
| 2 | `acquirementId` | string(64) | C — on 00000000 |
| 3 | `merchantTransId` | string(64) | C — on 00000000 |
| 4 | `refundInfos` | list<RefundInfo> | C — on 00000000; **capped at 50 most recent**. |

#### Endpoint result codes
00000000 SUCCESS S · 00000004 PARAM_ILLEGAL F · 00000900 SYSTEM_ERROR U · 00000020 TARGET_NOT_FOUND F.

---

### C.6 `alipayplus.acquiring.notify.orderFinish` (SPI — TNGD → merchant)

Source: `01. Acquiring/Acquiring SPI/alipayplus.acquiring.notify.orderFinish.htm`. Idempotency key (merchant side): `merchantTransId`.

#### Request.body (sent BY TNGD)
| # | name | type | len | Req | Notes |
|---|------|------|-----|-----|-------|
| 1 | `acquirementId` | string | 64 | M | |
| 2 | `merchantTransId` | string | 64 | M | |
| 3 | `finishedTime` | datetime | — | M | |
| 4 | `createdTime` | datetime | — | M | |
| 5 | `merchantId` | string | 32 | M | |
| 6 | `orderAmount` | Money | — | M | |
| 7 | `acquirementStatus` | enum StatusDetailEnum | 32 | M | **Only `CLOSED` or `SUCCESS` per spec.** |
| 8 | `extendInfo` | string | 4096 | O | |

#### Response.body merchant must return
```json
{ "resultInfo": {
    "resultStatus": "S",
    "resultCodeId": "00000000",
    "resultCode": "SUCCESS",
    "resultMsg": "success"
}}
```

#### SPI result codes accepted by TNGD
| Id | Code | Status | Effect |
|----|------|--------|--------|
| 00000000 | SUCCESS | S | TNGD considers callback delivered, stops retrying. |
| 00000900 | SYSTEM_ERROR | U | TNGD **will retry**. Anything that isn't `S` (including HTTP non-200 or sig fail) implicitly causes retry. |

> The .htm doesn't specify retry cadence or maximum retries — see §J open questions.

---

## D. Common parameter structures

### D.1 Global Common Structure (`00.Global Common Structure/index.htm`)

#### ResultInfo
| # | name | type | len | Req | Notes |
|---|------|------|-----|-----|-------|
| 1 | `resultStatus` | string | 2 | M | `S`/`F`/`U` (success/failure/unknown). |
| 2 | `resultCodeId` | string | 8 | M | `00000000` when S; otherwise see §E. |
| 3 | `resultCode` | string | 64 | M | Human-readable token (`SUCCESS`, `PAYMENT_IN_PROCESS`, etc.). |
| 4 | `resultMsg` | string | 256 | O | Description of error when F/U. |

#### Money
| # | name | type | len | Req | Notes |
|---|------|------|-----|-----|-------|
| 1 | `currency` | string | 3 | M | ISO-4217 (e.g. `MYR`, `USD`). |
| 2 | `value` | number(16,0) | — | M | **Integer string** of the smallest currency unit. For MYR ⇒ sen. So MYR 1.00 = `"100"`. No decimals. Max 16 digits. |

#### EnvInfo
| # | name | type | len | Req | Notes |
|---|------|------|-----|-----|-------|
| 1 | sessionId | string | 128 | O | |
| 2 | tokenId | string | 128 | O | Reserved. |
| 3 | websiteLanguage | string | 16 | O | `en_US` etc. |
| 4 | clientIp | string | 32 | O | |
| 5 | osType | string | 128 | O | |
| 6 | appVersion | string | 128 | O | Reserved. |
| 7 | sdkVersion | string | 128 | O | Reserved. |
| 8 | terminalType | enum TerminalTypeEnum | 32 | **M** | For retail it should be `SYSTEM`. |
| 9 | **orderTerminalType** | enum OrderTerminalTypeEnum | 32 | **M** | `APP`/`WEB`/`WAP`/`SYSTEM`. Added 2018-05-30. |
| 10| merchantAppVersion | string | 128 | O | |
| 11| merchantTerminalId | string | 128 | O | |
| 12| merchantIP | string | 128 | O | |
| 13| extendInfo | string | 4096 | O | Often used for `deviceId`. |

#### PaymentView (response side)
`cashierRequestId` M, `paidTime` M, `payOptionInfos` list<PayOptionInfo> M, `payRequestExtendInfo` O, `extendInfo` O (carries `topupAndPay`, `paymentStatus`, `paymentErrorCode`, `instErrorCode`).

#### PayOptionInfo
`payMethod` enum M (`BALANCE`/`NET_BANKING`/`CREDIT_CARD`/`DEBIT_CARD`/`VIRTUAL_ACCOUNT`/`OTC`), `payAmount` Money M, `transAmount` Money O, `chargeAmount` Money O, `extendInfo` O, `payOptionBillExtendInfo` O.

#### Enums (Global)
- TerminalTypeEnum: `APP`, `WEB`, `WAP`, `SYSTEM`, `GATE`, `CCT`.
- OrderTerminalTypeEnum: `APP`, `WEB`, `WAP`, `SYSTEM`.
- RiskResultEnum: `ACCEPT`, `REJECT`, `VERIFICATION`.
- VerificationMethodEnum: `OTP_SMS`, `OTP_EMAIL`, `PASSWORD`, `SECURITY_QUESTION`, `CARD_NO`, `CARD_EXPIRE`.
- PayMethodEnum: `BALANCE`, `NET_BANKING`, `CREDIT_CARD`, `DEBIT_CARD`, `VIRTUAL_ACCOUNT`, `OTC`.
- PayIntegrationTypeEnum: `CASHIER`, `API`, `QR`.
- SettleStrategyEnum: `BY_TIME_CYCLE`, `REALTIME`.
- SettleAccountTypeEnum: `BANK_ACCOUNT`, `BALANCE_ACCOUNT`.
- PayoutTypeEnum: `PENDING_SETTLEMENT_ACCOUNT_PAYOUT`, `SPECIFIED_ACCOUNT_PAYOUT`.
- AcquiringModeEnum: `DIRECTPAY`, `PAY_CONFIRM`, `COD`.
- NeedLoginEnum: `LOGIN_MANDATORY`, `LOGIN_NOT_ALLOWED`, `LOGIN_OPTIONAL`.
- SettleCycleEnum: `T+1` … `T+7`, `W+1`/`W+2`/`W+3`, `M+1`/`M+2`.
- ActorTypeEnum: `USER`, `MERCHANT`, `MERCHANT_OPERATOR`, `BACK_OFFICE`, `SYSTEM`.

### D.2 Acquiring Domain (`01.Acquiring Domain Structure/index.htm`)

#### InputUserInfo
`userId` (string 32, O), `externalUserId` (string 32, C — paired with type), `externalUserType` (string 32, C), `nickname` (string 64, O), `userValidationRequest` (UserValidationRequest, O — selected merchants only).

#### Goods
`merchantGoodsId`(64,O), `description`(256,**M**), `category`(64,O), `price`(Money,**M**, >0), `unit`(64,O), `quantity`(16,O), `merchantShippingId`(64,O), `snapshotUrl`(512,O), `extendInfo`(4096,O).

#### ShippingInfo
`merchantShippingId` M, `trackingNo` O, `carrier` O, `chargeAmount` Money O, `countryName` M(64), `stateName` M(64), `cityName` M(64), `areaName` O(64), `address1` M(256), `address2` O(256), `firstName` M(64), `lastName` M(64), `mobileNo` O(32), `phoneNo` O(32), `zipCode` M(32), `email` O(128), `faxNo` O(32).

#### NotificationUrl
`url` M(512), `type` enum `PAY_RETURN` / `NOTIFICATION` M.

#### Order
| # | name | type | Req | Notes |
|---|------|------|-----|-------|
| 1 | `buyer` | InputUserInfo | C | Mandatory when contract `LOGIN_MANDATORY`. |
| 2 | `seller` | InputUserInfo | O | |
| 3 | `orderTitle` | string(256) | **M** | |
| 4 | `orderAmount` | Money | **M** | > 0. |
| 5 | `merchantTransId` | string(64) | **M** | Idempotency key — unique per merchant transaction. |
| 6 | `merchantTransType` | string(64) | O | |
| 7 | `orderMemo` | string(256) | O | |
| 8 | `createdTime` | datetime | O | |
| 9 | `expiryTime` | datetime | **M** | If still INIT at expiry, system closes the order. |
| 10| `goods` | list<Goods> | O | Max 1000. |
| 11| `shippingInfo` | list<ShippingInfo> | O | Max 1000. |

#### AmountDetail (response of order.query)
`orderAmount` M, `payAmount` O, `voidAmount` O, `confirmAmount` O, `refundAmount` O, `chargebackAmount` O, `chargeAmount` O.

#### StatusDetail
`acquirementStatus` enum StatusDetailEnum M (`INIT`/`SUCCESS`/`CLOSED`/`PAYING`/`MERCHANT_ACCEPT`/`CANCELLED`), `frozen` boolean M.

#### TimeDetail
`createdTime` M, `expiryTime` M, `paidTimes` list<datetime> O, `confirmedTimes` list<datetime> O.

#### RefundInfo (returned in refund.query)
`refundId` M(64), `refundAmount` Money M, `refundReason` O(1024), `refundTime` O, `refundToUserTime` O, `actorType` enum O, `payoutAccountNo` O(64), `returnChargeToPayer` boolean M, `refundStatus` enum RefundStatusEnum M (`PROCESSING`/`FAILED`/`SUCCESS`), `refundChannelDetails` list<RefundChannelDetail> O, `extendInfo` O(4096), `memo` O(128).

#### RefundChannelDetail
`fundProcessId` M(64), `refundMethod` enum (`SYSTEM`/`MANUAL`/`ERROR_PLATFORM`) M, `refundChannel` enum (`BALANCE`/`EXTINSTPAY`/`MANUAL_OFFLINE`) O, `refundAmount` Money M, `refundedTime` datetime M, `success` boolean M, `memo` O(128).

#### ShopInfo
`shopId` O(64), `shopName` O(128), `operatorId` O(64).

#### AuthCodeTypeEnum
`BAR_CODE`, `WAVE_CODE`.

#### StatusDetailEnum (the authoritative payment state)
`INIT` (not paid or paid-not-finished), `SUCCESS`, `CLOSED`, `PAYING`, `MERCHANT_ACCEPT`, `CANCELLED`.

#### RefundStatusEnum
`PROCESSING`, `FAILED`, `SUCCESS`.

#### NotificationUrlTypeEnum
`PAY_RETURN`, `NOTIFICATION`.

#### IdentityTypeEnum
`MYKAD`, `PASSPORT`, `POLICE`, `ARMY`, `OTHERS`.

(Other enums in this domain: `ChargeFromEnum`, `RefundDestinationEnum`, `VoidStatusDetailEnum`, `CaptureStatusDetailEnum`, `ConfirmStatusDetailEnum`, `ConfirmSourceEnum`, `CaptureSourceEnum`, `VoidSourceEnum`, `RefundMethodEnum`, `RefundChannelEnum`, `TransitCodeTypeEnum`, `OrderProcessStatusEnum`.)

### D.3 Risk Domain (`02.Risk Domain Structure/index.htm`)
Only `FPTypeEnum` is defined: `APDID`, `UMID`. Not needed for RetailPay.

### D.4 OAuth Domain (`03.OAuth Domain Structure.htm`)
Defines `GrantTypeEnum` (`authorization_code`, `implicit`, `password`, `client_credential`, `refresh_token`, `third_party_verified`), an EnvInfo variant (same shape as global), `AccessTokenInfo` (`accessToken`/`accessTokenExpiryTime`/`tokenType`/`clientId`/`userId`/`refreshToken`/`refreshTokenExpiryTime`/`scopes`/`tokenStatus`), and `TokenTypeEnum` = `BEARER`. **Not needed for the retail-pay product** but the SDK ships an `AlipayplusOauthAccesstokenRevokeRequest` class.

### D.5 User Domain (`05.User Domain Structure.htm`)
`UserInfo`: only `userId` string(16) M. Sample `216610000000`. `IdentityTypeEnum` = `MYKAD`/`PASSPORT`/`POLICE`/`ARMY`/`OTHERS`.

---

## E. Result codes — master list

### E.1 Basic / framework codes (apply to every endpoint)

Source: `Common Result Code/Basic Result Code/index.htm`.

| Id        | Code               | Status | Meaning / Handling |
|-----------|--------------------|--------|--------------------|
| 00000002  | PARAM_MISSING      | F | Fix request and retry with NEW reqMsgId. |
| 00000004  | PARAM_ILLEGAL      | F | Fix request. |
| 00000007  | INVALID_SIGNATURE  | F | Re-check sign content / key wiring. |
| 00000013  | NO_INTERFACE_DEF   | F | Wrong `function` value. |
| 00000014  | API_IS_INVALID     | F | API disabled / not activated for this clientId. |
| 00000015  | MSG_PARSE_ERROR    | F | Body not valid JSON. |
| 00000016  | OAUTH_FAILED       | F | clientId/clientSecret invalid. |
| 00000017  | FUNCTION_NOT_MATCH | F | head.function doesn't match URL. |
| 00000900  | SYSTEM_ERROR       | **U** | Unknown — **query, do NOT assume failure**. |
| 00000020  | TARGET_NOT_FOUND   | F | (query endpoints) entity does not exist. |

### E.2 Status semantics

- **`S` (Success)** — definitively succeeded. Persist `acquirementId` + `paidTime`.
- **`F` (Failure)** — definitively failed. Safe to mark order failed. For retail.pay, create a NEW `merchantTransId` if user wants to retry.
- **`U` (Unknown)** — outcome indeterminate. **MUST poll `order.query`** (or `refund.query`). NEVER mark final state based on U.

### E.3 Quick handling guide for retail.pay

| Code | Action |
|------|--------|
| 00000000 SUCCESS | Mark paid. |
| 12005012 USER_PAYING | Poll order.query every 2–5s until SUCCESS / CLOSED / final F. Show "user paying" UX. |
| 12005215 PAYMENT_IN_PROCESS | Poll order.query. |
| 00000900 SYSTEM_ERROR | Poll order.query; if INIT after N polls, call order.cancel. |
| 12005009 AUTH_CODE_ILLEGAL / 12005010 ALREADY_USED | Ask user for new QR. |
| 12005115 BALANCE_NOT_ENOUGH | Show top-up prompt. |
| 12005104 / 12005028 / 12005029 / 12005030 | Amount-limit family — surface specific message. |
| All other F | Generic failure; new merchantTransId needed to retry. |

---

## F. SPI (callback) spec — operational

### F.1 URL
Whatever merchant sets in `retail.pay` body `notifyUrl` (≤256 chars, HTTP or HTTPS). TNGD will `POST` JSON with `Content-Type: application/json;charset=utf-8`.

### F.2 What TNGD POSTs
See §C.6 — full signed envelope under `request.head/body`, signed with TNGD's private key. **Verify** with the server public key in your config.

### F.3 What merchant must return
HTTP `200 OK`, body = signed envelope (§A.7) with `resultStatus=S`, `resultCodeId=00000000`. Sign with merchant's private key.

### F.4 Idempotency
TNGD uses `merchantTransId` as idempotency key on the merchant side — if your endpoint is called twice for the same `merchantTransId`, return the same SUCCESS payload without double-processing the order.

### F.5 Retries
The htm `Function Logic` says: *"If the receiver returned 'SYSTEM_ERROR' or the sender didn't get the response such as timeout, the sender will retry to deliver."* — exact cadence/cap are NOT documented (open question, §J).

### F.6 `acquirementStatus` in the SPI payload
Per spec table: **only `CLOSED` or `SUCCESS` are sent** in `notify.orderFinish`. (No INIT/PAYING notifications.)

---

## G. Settlement file spec

### G.1 SFTP transport (docx §"Settlement")

| Item | Value |
|------|-------|
| Host (sandbox)    | `test.tngdigital.com.my` |
| Host (production) | `tpa.tngdigital.com.my` |
| Port              | `2222` |
| Auth              | Account issued by TNGD; **public IP must be whitelisted** by TNGD (apply for both sandbox & prod). |
| File path / pattern | `MDSDO_P_{yyyyMMdd}_{merchantId}.xlsx` (per docx — see drift below) |

### G.2 Filename / format drift (flag)
- Docx says daily file is **`MDSDO_P_{yyyyMMdd}_{merchantId}.xlsx`** (Excel).
- Sample file in the package is **`MERCHANT_SETTLEMENT_{merchantId}_{yyyyMMdd}.csv`** (CSV, two-section).
- Treat the sample as the actual production format (confirmed by its real production-looking content). The xlsx mention may be stale. **Confirm with TNGD which name and format applies for your merchant.**

### G.3 Sample file layout (CSV, two sections)

File: `MERCHANT_SETTLEMENT_217120000000252999999_20201229.csv`

```
SETTLEMENT_SUMMARY
INVOICE_NO,"E/201230A01345874"
INVOICE_DATE,29/12/2020
SETTLEMENT_BATCH_NO,"20201230111213810400171002401345874"
MERCHANT_ID,217120000000252999999
MERCHANT_NAME,"EAGLE"
NET_TRANSACTION_AMOUNT,1400
NET_COMMISSION_AMOUNT,140
NET_SETTLEMENT_AMOUNT,1260
TOTAL_COUNT,5

SETTLEMENT_DETAILS
MERCHANT_ID,MERCHANT_NAME,SHOP_ID,SHOP_NAME,MERCHANT_TRANS_ID,ACQUIREMENT_ID,TRANSACTION_TYPE,TRANSACTION_REQUEST_ID,TRANSACTION_ID,PRODUCT_CODE,TRANSACTION_AMOUNT,TRANSACTION_CURRENCY,TRANSACTION_DATETIME,COMMISSION_AMOUNT,COMMISSION_TAX,SETTLE_AMOUNT,PAY_METHOD,MERCHANT_CUST_ID
217120000000252519359,"EAGLE",,"",9bd1af6e…,20201229211212800110171671600815114,PAYMENT,,20201229211212800110171671600815114,51051000101000100001,100,MYR,2020/12/29 14:13:34,10,0,90,BALANCE,
…
```

### G.4 Summary section fields
| Field | Type | Notes |
|-------|------|-------|
| `INVOICE_NO` | string | TNGD invoice id (e.g. `E/201230A01345874`). |
| `INVOICE_DATE` | `dd/MM/yyyy` | Date the invoice was raised (next day after txn date in this sample). |
| `SETTLEMENT_BATCH_NO` | string | Used in reconciliation queries with TNGD. |
| `MERCHANT_ID` | string | The merchant's top-level account. |
| `MERCHANT_NAME` | string | Quoted. |
| `NET_TRANSACTION_AMOUNT` | integer **sen** | Gross of all PAYMENT rows. |
| `NET_COMMISSION_AMOUNT` | integer sen | Sum of commission (incl. tax). |
| `NET_SETTLEMENT_AMOUNT` | integer sen | `NET_TRANSACTION_AMOUNT − NET_COMMISSION_AMOUNT`. (Payable to merchant.) |
| `TOTAL_COUNT` | int | Number of rows in `SETTLEMENT_DETAILS`. |

### G.5 Detail section columns (CSV header)
| # | Column | Type | Sample | Notes |
|---|--------|------|--------|-------|
| 1 | `MERCHANT_ID` | string | `217120000000252519359` | **Sub-merchant** id (different from summary's parent id). |
| 2 | `MERCHANT_NAME` | string | `EAGLE` | |
| 3 | `SHOP_ID` | string | empty | From `shopInfo.shopId` when sent. |
| 4 | `SHOP_NAME` | string | empty | |
| 5 | `MERCHANT_TRANS_ID` | string | hex/uuid | Echoes your `order.merchantTransId`. |
| 6 | `ACQUIREMENT_ID` | string | `2020…815114` | TNGD's transaction id. |
| 7 | `TRANSACTION_TYPE` | string | `PAYMENT` | Other observed types in spec: `REFUND`, `CANCEL`. |
| 8 | `TRANSACTION_REQUEST_ID` | string | empty for PAYMENT | Populated for REFUND (= your refund `requestId`). |
| 9 | `TRANSACTION_ID` | string | same as ACQUIREMENT_ID in sample | |
| 10| `PRODUCT_CODE` | string | `51051000101000100001` | NB: sample uses `…00001`; docx default for retail is `…00040`. Likely SKU variant. |
| 11| `TRANSACTION_AMOUNT` | integer **sen** | `100` = MYR 1.00 | |
| 12| `TRANSACTION_CURRENCY` | string ISO-4217 | `MYR` | |
| 13| `TRANSACTION_DATETIME` | `yyyy/MM/dd HH:mm:ss` | `2020/12/29 14:13:34` | **No timezone specified** — assumed Malaysia time (`+08:00`). Confirm. |
| 14| `COMMISSION_AMOUNT` | integer sen | `10` | MDR. |
| 15| `COMMISSION_TAX` | integer sen | `0` | SST on commission. |
| 16| `SETTLE_AMOUNT` | integer sen | `90` | `TRANSACTION_AMOUNT − COMMISSION_AMOUNT − COMMISSION_TAX` for PAYMENT. |
| 17| `PAY_METHOD` | enum | `BALANCE` | From PayMethodEnum. |
| 18| `MERCHANT_CUST_ID` | string | empty | Reserved / for accounts-payable cross-ref. |

### G.6 Decoded sample row
```
MERCHANT_ID=217120000000252519359
MERCHANT_NAME="EAGLE"
SHOP_ID=
SHOP_NAME=
MERCHANT_TRANS_ID=9bd1af6eb6332962ff7c395da016c24ce54060a065b5eb3a452e19c703a6b6e0
ACQUIREMENT_ID=20201229211212800110171671600815114
TRANSACTION_TYPE=PAYMENT
TRANSACTION_REQUEST_ID=
TRANSACTION_ID=20201229211212800110171671600815114
PRODUCT_CODE=51051000101000100001
TRANSACTION_AMOUNT=100      // MYR 1.00
TRANSACTION_CURRENCY=MYR
TRANSACTION_DATETIME=2020/12/29 14:13:34
COMMISSION_AMOUNT=10        // MDR 10 sen (10%)
COMMISSION_TAX=0
SETTLE_AMOUNT=90            // MYR 0.90 payable
PAY_METHOD=BALANCE
MERCHANT_CUST_ID=
```

> Cancelled transactions **do not appear** in the file (docx + cancel.htm §2). Refunds appear with `TRANSACTION_TYPE=REFUND` and a negative-direction effect on net amounts (semantic confirmed by file structure; sample doesn't contain a refund row — verify).

---

## H. Notes & gotchas

### H.1 Money unit
`Money.value` is **always integer-string of the smallest unit**. For MYR that's sen. `"100"` = RM 1.00. No decimal point. Max 16 digits.

### H.2 Time / timezone
- API: ISO-8601 with offset (e.g. `2020-12-29T14:13:34+08:00`). PHP SDK `date('c')` is compliant.
- Settlement CSV: `yyyy/MM/dd HH:mm:ss` with **no offset** — assume Malaysia time (`+08:00`).
- ValidateUtil regex in PHP SDK requires offset of form `+HH:MM` / `-HH:MM` — no `Z`. So **don't send `2020-12-29T14:13:34Z`** — convert to `+00:00`.

### H.3 The signed slice is byte-literal
Do not pretty-print, do not change key order between sign-time and send-time. The PHP SDK constructs the header string by manual concatenation (`"\"head\":{...}"`) precisely to lock the byte order. Any JSON library that re-serializes is a footgun.

### H.4 `clientSecret` lives inside the signed envelope
It's not an HTTP header — it's `request.head.clientSecret`. Sent in cleartext (inside HTTPS). Both `clientId` + `clientSecret` are required, in addition to a valid signature.

### H.5 `extendInfo` mandatory fields for retail / offline TPA (Standardization v1.6 addendum)
Send these as a JSON-encoded string in `request.body.extendInfo` for **every** retail.pay. All fields are marked `Yes` (mandatory):

| Field | Description | Sample |
|-------|-------------|--------|
| `merchantId` | sub-merchant's registered ID | `123456` |
| `merchantName` | sub-merchant's registered company name | `ABC Sdn Bhd` |
| `TerminalID` | merchant terminal id | `123456789` |
| `shopName` | merchant shop name | `MyShop-01` |
| `MCC` | merchant category code | `1234` |
| `merchantStreet` | street | `Brickfields` |
| `merchantState` | one of: Johor, Sarawak, Selangor, Terengganu, Kuala Lumpur, Labuan, Sabah, Putrajaya, Kedah, Kelantan, Melaka, Negeri Sembilan, Pahang, Perak, Perlis, Penang | `Selangor` |
| `merchantCity` | city | `Cheras` |
| `merchantPostcode` | postcode | `12345` |
| `latitude` | GPS lat | `3.108220` |
| `longitude` | GPS lon | `101.665733` |
| `brand` | merchant/sub-merchant outlet brand | `ABC-Mart` |

Note: addendum's "MUST HAVE" subset reduces to `merchantId, merchantName, TerminalID, shopName, MCC, brand` if location is unknown — but full set is requested in the example. Send the full set.

Also note the addendum's example uses `submerchantId`/`submerchantName`/`Tid` keys, contradicting the table's `merchantId`/`merchantName`/`TerminalID`. **Both labels appear** — confirm exact keys with TNGD (§J).

### H.6 `notifyUrl` vs `notificationUrls`
- The .htm spec field name is **`notifyUrl`** (singular string).
- The Postman sample uses **`notificationUrls`** as a list of `{url,type}` (NotificationUrl objects).
- The PHP SDK retail.pay model has only `notifyUrl`.
- Either probably works server-side; safest is **send both**, or confirm. The docx and .htm are authoritative — `notifyUrl` string is the documented field.

### H.7 IP whitelisting
- SFTP — yes, required for sandbox & prod (docx).
- Outbound API — not explicitly mentioned but expect TNGD to require source IP whitelisting for production calls. Ask.

### H.8 Currency
TNGD is MYR-only for Malaysian merchants but the protocol allows any ISO-4217. Stick to `MYR`.

### H.9 `clientSecret` sent inside payload (security note)
Don't log full request bodies. Mask `clientSecret` and the entire signature string before logging.

### H.10 Status response code `version` mismatch
Spec table samples respond with `version: "1.2"` in the header but live samples and the actual `version` field sent should remain `"2.0"`. Don't assert on the version value.

### H.11 USER_PAYING means QR was scanned but TNGD now wants OTP/password
You will get this synchronously from `retail.pay`. Show the user "Please complete payment on your TNG app." UX while you poll. Do NOT call cancel until you've polled and seen `acquirementStatus=INIT` repeatedly.

### H.12 Cancel removes the transaction from settlement
Cancelled orders don't appear in the daily settlement CSV. Refunds DO appear.

### H.13 Order expiry
`order.expiryTime` is **mandatory** in the request. If you omit it, system uses contract default (per spec, but PHP SDK doesn't enforce). Recommend explicitly setting (e.g. now+5min for retail).

---

## I. PHP SDK observations

### I.1 Layout
```
php/
├── Readme.md                     (one line: "alipayplus-sdk")
├── composer.json
└── src/alipayplus/sdk/
    ├── SdkClient.php             — main client (sign+post+verify+parse)
    ├── constant/SystemConstant.php — SDK_VERSION, default timeouts (3s connect / 15s read)
    ├── exception/SdkException.php
    ├── util/
    │   ├── SignatureUtil.php     — sign() / verify(), SHA256withRSA + base64
    │   ├── StringUtil.php
    │   ├── LogUtil.php           — hard-coded /Users/shaoshuai.shao/Desktop log paths
    │   └── ValidateUtil.php      — length / required / RFC3339 regex
    ├── model/
    │   ├── BaseObject.php / BaseRequest.php
    │   ├── Money.php / EnvInfo.php / PaymentView.php / PayOptionInfo.php
    │   └── acquiring/{Order, Goods, ShippingInfo, ShopInfo, InputUserInfo,
    │                  PaymentPreference, AmountDetail, StatusDetail, TimeDetail,
    │                  NotificationUrl, RefundChannelDetail, RefundInfo}
    └── request/
        ├── AlipayplusAcquiringRetailPayRequest.php
        ├── AlipayplusAcquiringOrderCancelRequest.php
        ├── AlipayplusAcquiringOrderQueryRequest.php
        ├── AlipayplusAcquiringOrderRefundRequest.php
        ├── AlipayplusAcquiringRefundQueryRequest.php
        ├── AlipayplusOauthAccesstokenRevokeRequest.php
        ├── AlipayplusTestQueryMerchantRequest.php
        └── AlipayplusTestQueryUserRequest.php
```

### I.2 Key behaviours
- Header is hand-assembled string (`"\"head\":{\"version\":\"1.0\",...}"`) so JSON key order is fixed. Body is `json_encode($request)` (BaseRequest extends BaseObject → public properties become JSON keys in declared order).
- Header default `version` is **`"1.0"`** — endpoint specs show `"2.0"`. The SDK has a `// TODO 1.0-->2.0` comment. **Override** when you wire the SDK or patch it.
- HTTP: `CURLOPT_SSL_VERIFYPEER=false` (!!). For production, set to true and bundle CA.
- HTTP body is the signed concatenated string `{"request":{<head>,<body>},"signature":"<b64>"}`.
- Response parsing is *also* substring-based: it finds `{"head":` and `,"signature":` and verifies that exact byte range — confirming sign/verify symmetry.
- Logs: hard-coded paths in `SystemConstant.php` (macOS user dir). Patch before use.
- `array_to_object` recursively flattens JSON response into `stdClass`. No type validation on the way back.

### I.3 Things the SDK does that the spec doesn't document
- Adds `sdkVersion` field to head (used as client-version telemetry; TNGD presumably ignores).
- Generates `reqMsgId` as UUID-like md5 of `uniqid()+mt_rand()`.
- Wraps private key in PKCS#1 PEM header even though spec mandates PKCS#8 (see §B.3).
- Default `version` `"1.0"` not `"2.0"`.

### I.4 Things the spec requires that the SDK does not enforce
- Mandatory `order.expiryTime` — SDK validation marks it only `checkDateFormat` (no required check).
- `extendInfo` schema for retail (§H.5) — SDK only length-checks 4096 chars.
- Body field `notifyUrl` vs `notificationUrls`: SDK only knows `notifyUrl`.

---

## J. Open questions for TNGD (copy-paste checklist for Aqid)

- [ ] **Production base URL** — sandbox is `https://api-sd.tngdigital.com.my`. What is the production base URL for `alipayplus.retail.pay` and friends? Is HTTPS mandatory?
- [ ] **Outbound IP whitelisting** — must our charger backend's source IP be whitelisted for the API itself (separate from SFTP)? If yes, where do we apply?
- [ ] **Settlement filename + format** — docx says `MDSDO_P_{yyyyMMdd}_{merchantId}.xlsx`; the sample we have is `MERCHANT_SETTLEMENT_{merchantId}_{yyyyMMdd}.csv`. Which is current for production, and what is the exact SFTP path/dir?
- [ ] **Settlement file delivery time** — is the daily file dropped at a fixed Malaysia-time clock-time? What's the SLA?
- [ ] **Settlement `TRANSACTION_DATETIME` timezone** — confirm it's `+08:00` (Malaysia time), not UTC.
- [ ] **Refund rows in settlement** — please send a sample CSV that contains REFUND and CANCEL rows so we can verify column semantics (sign of `SETTLE_AMOUNT`, value of `TRANSACTION_REQUEST_ID`).
- [ ] **SPI retry policy** — for `alipayplus.acquiring.notify.orderFinish`, what is the retry cadence and maximum retry count? After final failure, do you mark the transaction as undeliverable on your side or just stop?
- [ ] **SPI source IPs** — list of TNGD egress IPs we should whitelist for the callback endpoint.
- [ ] **`notifyUrl` vs `notificationUrls`** — is the supported request field the singular `notifyUrl` (string) per spec, the plural `notificationUrls` (list of NotificationUrl) per the Postman sample, or both?
- [ ] **Key format** — please confirm whether you accept PKCS#1 or PKCS#8 PEM for our public key submission, and what format your `serverRsaPublicKey` will be issued in (PKCS#8 / X.509 SPKI?).
- [ ] **Header `version`** — confirm production expects `"2.0"`. The PHP SDK default of `"1.0"` is wrong, yes?
- [ ] **Product code** — confirm `51051000101000100040` is the correct retail-pay product code for our merchant onboarding. (Settlement sample shows `…00001`; what is that variant?)
- [ ] **extendInfo keys** — addendum table uses `merchantId/merchantName/TerminalID`; the example uses `submerchantId/submerchantName/Tid`. Which key names are correct? Are they case-sensitive?
- [ ] **MCC** — for EV charging, what MCC do you want us to send? (5552 "Electric Vehicle Charging" is the modern ISO/SS code, but TNGD's table reference points to IRS 2004 list — please confirm.)
- [ ] **TLS / cipher requirements** — any restrictions on TLS version or ciphers on our side?
- [ ] **`reqMsgId` collision** — what happens if we accidentally reuse a `reqMsgId` on a successful request? Replay-protected?
- [ ] **Sandbox test wallet** — please provide a sandbox TNG user account or QR code we can scan during integration testing.
- [ ] **Auth code expiry** — what is the validity window of the BAR_CODE auth code from the user's app? (For UX retry logic.)
- [ ] **Order expiry default** — what is the contract default for `order.expiryTime` when we omit it?
- [ ] **Cancel timing** — how long after a successful payment can `order.cancel` still be called before it returns `CANCEL_EXPIRED` (12005018)?
- [ ] **Refund partial-amount limits** — minimum partial refund amount? Maximum number of partial refunds per order?

---

*End of reference. Update when TNGD answers §J or ships a newer spec.*

---

## K. Implementation status (PlagSini codebase)

As of 2026-05-19. All TNG credentials/URLs/keys are env-var placeholders pending TNGD onboarding. See `ChargingPlatform/docs/TNG_INTEGRATION_PLUG_IN_GUIDE.md` for the final plug-in checklist.

| Spec section | Implementation |
|--------------|----------------|
| §A Envelope (request/response) | `payment_gateway.py::_tng_build_signable_substring`, `TngGateway._build_head`, `_post_signed` |
| §A.6/A.7 SPI envelope + ACK    | `TngGateway.verify_callback`, `TngGateway.build_callback_ack`; wired in `api.py::payment_callback` (returns signed JSON for `gateway_name=="tng"`) |
| §B Signature (literal substring, PKCS#8, RSA-SHA256, v2.0) | `_tng_sign_substring`, `_tng_verify_substring`. Head built in declared key order so signed bytes == sent bytes. |
| §C.1 retail.pay                | `TngGateway._create_retail_pay` (dispatched when `PAYMENT_TNG_PRODUCT=retail_pay`; `authCode` passed via `payment_method` arg) |
| §C.1 ordercode.create (variant)| `TngGateway._create_ordercode_order` (default; `PAYMENT_TNG_PRODUCT=ordercode`) |
| §C.2 order.query               | `TngGateway.check_status` (uses `statusDetail.acquirementStatus` as authoritative) |
| §C.3 order.cancel              | `TngGateway.cancel_payment` + admin endpoint `POST /api/payment/tng/cancel/{transaction_ref}` |
| §C.4 order.refund              | `TngGateway.refund_payment` + admin endpoint `POST /api/payment/tng/refund/{transaction_ref}`. Refunds persisted as negative-amount `PaymentTransaction` rows with `purpose='refund'`. |
| §C.5 refund.query              | `TngGateway.query_refund` |
| §C.6 SPI notify.orderFinish    | Inbound: `api.py::payment_callback` → `TngGateway.verify_callback` (handles `acquirementStatus ∈ {SUCCESS, CLOSED}`). Outbound ACK: `build_callback_ack` returns signed envelope. |
| §E result codes (S/F/U)        | `_parse_payment_response` maps S→success, F→failure, U→pending+auto-poll. `_tng_poll_u_status` in `api.py` polls `order.query` every 3s up to 60s. |
| §G Settlement (SFTP + CSV)     | `ChargingPlatform/scripts/tng_settlement_sync.py` (CLI: `python -m ChargingPlatform.scripts.tng_settlement_sync --date YYYY-MM-DD`). Parser: `parse_settlement_csv` handles two-section format. DB model: `TngSettlementRecord`. Migration: `20260520_000001_add_tng_settlement_records.py`. Mismatches alert Telegram via `TELEGRAM_BOT_TOKEN/CHAT_ID`. Tries `.csv` first, falls back to `.xlsx` (G.2 drift). |
| §H.5 extendInfo v1.6 (12 fields) | `TngGateway._build_extendinfo` — sends both spec key names and addendum example alt keys (`submerchantId/submerchantName/Tid`) for compatibility until §J item is answered. |
| §H.13 order.expiryTime mandatory | `_create_retail_pay` sets `expiryTime = now+5min`. ordercode uses `effectiveSeconds=600`. |
| §J Open questions | Tracked in §J above. All concrete defaults in code are conservative (PKCS#8, v2.0, sandbox URL, MCC 5732). |
| Config error handling | `TngConfigurationError` raised by `_get_credentials` returns a clean message to the caller (no deep-stack crash). |
| Admin self-test | `POST /api/payment/tng/test-sign` (admin-only) — proves keys/wiring before going live. |


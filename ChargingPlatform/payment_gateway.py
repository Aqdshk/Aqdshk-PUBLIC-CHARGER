"""
PlagSini EV — Payment Gateway Abstraction Layer

Supports plugging in any Malaysian payment gateway:
  - OCBC Payment Gateway (placeholder — awaiting API docs)
  - Billplz (FPX) — fully implemented
  - Fiuu / Razer Merchant Services (scaffold — create_payment/check_status pending)
  - TNG Digital / eWallet (create_payment + verify_callback done; check_status scaffold)
  - Manual top-up (admin approved) — fully implemented

All gateways inherit from BasePaymentGateway and implement:
  - create_payment() — initiate payment, return URL or QR
  - verify_callback() — validate webhook/callback from gateway
  - check_status() — poll payment status (optional for async flows)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
#  BASE GATEWAY (Abstract)
# ═══════════════════════════════════════════

class BasePaymentGateway(ABC):
    """Abstract base class for all payment gateways."""

    def __init__(self, config: dict):
        self.merchant_id = config.get("merchant_id", "")
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.is_sandbox = config.get("is_sandbox", True)
        self.sandbox_url = config.get("sandbox_url", "")
        self.production_url = config.get("production_url", "")
        self.callback_url = config.get("callback_url", "")
        self.redirect_url = config.get("redirect_url", "")
        self.extra_config = json.loads(config.get("extra_config", "{}") or "{}")

    @property
    def base_url(self) -> str:
        return self.sandbox_url if self.is_sandbox else self.production_url

    @abstractmethod
    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        """
        Create a payment request.
        
        Returns:
            {
                "success": True/False,
                "payment_url": "https://...",  # URL to redirect user
                "gateway_transaction_id": "...",
                "gateway_reference": "...",
                "raw_response": {...}
            }
        """
        pass

    @abstractmethod
    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        """
        Verify and parse a callback/webhook from the gateway.
        
        Returns:
            {
                "valid": True/False,
                "transaction_ref": "TXN-...",
                "gateway_transaction_id": "...",
                "status": "success" | "failed" | "pending",
                "amount": 50.0,
                "payment_method": "fpx",
                "raw_response": {...}
            }
        """
        pass

    @abstractmethod
    async def check_status(self, gateway_transaction_id: str) -> dict:
        """
        Check payment status from gateway.
        
        Returns:
            {
                "status": "success" | "failed" | "pending",
                "amount": 50.0,
                "raw_response": {...}
            }
        """
        pass


# ─── Helper Functions ──────────────────────────────────────────────────────

def _as_str(value: object) -> str:
    """Safely convert value to stripped string; empty string if None."""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_status(value: str) -> str:
    """Map gateway status strings to standard: success | pending | failed | expired."""
    raw = _as_str(value).lower()
    if raw in {"success", "paid", "completed", "settled", "approved", "ok", "true", "1"}:
        return "success"
    if raw in {"pending", "processing", "in_progress", "authorized"}:
        return "pending"
    if raw in {"failed", "fail", "error", "declined", "cancelled", "canceled", "expired", "0", "false"}:
        if raw == "expired":
            return "expired"
        return "failed"
    return "pending"


def is_callback_already_processed(txn: Any) -> bool:
    """
    Idempotency guard for callback retries:
    once settled/credited, repeated callbacks should become no-ops.
    """
    return getattr(txn, "status", None) in ["success", "refunded"] or bool(getattr(txn, "wallet_transaction_id", None))


# ═══════════════════════════════════════════
#  OCBC GATEWAY (Ready to plug in)
# ═══════════════════════════════════════════

class OcbcGateway(BasePaymentGateway):
    """
    OCBC Bank Payment Gateway.
    
    When OCBC provides API documentation, fill in these methods.
    The structure is ready — just need the actual API endpoints and format.
    
    Typical OCBC flow:
      1. Your server → OCBC API: Create payment order
      2. OCBC returns payment URL
      3. User completes payment on OCBC's page
      4. OCBC sends callback to your callback_url
      5. Your server verifies and credits wallet
    """

    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        """Create payment via OCBC API."""
        
        # ── OCBC API Integration Point ──
        # When OCBC provides their API docs, implement here:
        #
        # payload = {
        #     "merchant_id": self.merchant_id,
        #     "order_id": transaction_ref,
        #     "amount": f"{amount:.2f}",
        #     "currency": currency,
        #     "description": description,
        #     "customer_email": customer_email,
        #     "customer_name": customer_name,
        #     "payment_method": payment_method,  # fpx, card, etc.
        #     "callback_url": self.callback_url,
        #     "redirect_url": self.redirect_url,
        # }
        #
        # # Generate signature (OCBC will specify the algorithm)
        # signature = self._generate_signature(payload)
        # payload["signature"] = signature
        #
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{self.base_url}/api/v1/payment/create",
        #         json=payload,
        #         headers={
        #             "Authorization": f"Bearer {self.api_key}",
        #             "Content-Type": "application/json",
        #         }
        #     )
        #     data = response.json()
        #
        # return {
        #     "success": data.get("status") == "created",
        #     "payment_url": data.get("payment_url"),
        #     "gateway_transaction_id": data.get("transaction_id"),
        #     "gateway_reference": data.get("reference"),
        #     "raw_response": data,
        # }

        # Placeholder until OCBC API docs are received
        logger.warning("OCBC Gateway: Using placeholder — awaiting API documentation")
        return {
            "success": False,
            "payment_url": None,
            "gateway_transaction_id": None,
            "gateway_reference": None,
            "message": "OCBC gateway not yet configured. Awaiting API documentation.",
            "raw_response": {},
        }

    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        """Verify OCBC callback/webhook."""
        
        # ── OCBC Callback Verification Point ──
        # When OCBC provides callback format, implement here:
        #
        # # Verify signature
        # received_sig = payload.get("signature", "")
        # expected_sig = self._generate_callback_signature(payload)
        # if not hmac.compare_digest(received_sig, expected_sig):
        #     return {"valid": False, "message": "Invalid signature"}
        #
        # return {
        #     "valid": True,
        #     "transaction_ref": payload.get("order_id"),
        #     "gateway_transaction_id": payload.get("transaction_id"),
        #     "status": "success" if payload.get("status") == "paid" else "failed",
        #     "amount": float(payload.get("amount", 0)),
        #     "payment_method": payload.get("payment_method"),
        #     "raw_response": payload,
        # }

        return {"valid": False, "message": "OCBC callback verification not yet implemented"}

    async def check_status(self, gateway_transaction_id: str) -> dict:
        """Check payment status from OCBC."""
        return {"status": "pending", "message": "OCBC status check not yet implemented"}

    def _generate_signature(self, payload: dict) -> str:
        """Generate HMAC signature for OCBC API requests."""
        # OCBC will specify: which fields to sign, hash algorithm, etc.
        sign_string = "|".join(str(v) for v in sorted(payload.values()) if v)
        return hmac.new(
            self.api_secret.encode(),
            sign_string.encode(),
            hashlib.sha256
        ).hexdigest()


# ═══════════════════════════════════════════
#  BILLPLZ GATEWAY (Malaysian FPX)
# ═══════════════════════════════════════════

class BillplzGateway(BasePaymentGateway):
    """
    Billplz — Simple Malaysian payment gateway.
    Supports FPX (online banking) and card payments.
    Free to sign up, 1.5% per transaction.
    https://www.billplz.com/api
    """

    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        if not self.api_key:
            return {"success": False, "message": "Billplz API key not configured"}

        collection_id = self.extra_config.get("collection_id", "")
        if not collection_id:
            return {"success": False, "message": "Billplz collection_id not configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v3/bills",
                    auth=(self.api_key, ""),
                    json={
                        "collection_id": collection_id,
                        "email": customer_email,
                        "name": customer_name or "Customer",
                        "amount": int(amount * 100),  # Billplz uses cents
                        "description": description,
                        "callback_url": self.callback_url,
                        "redirect_url": self.redirect_url,
                        "reference_1_label": "Transaction Ref",
                        "reference_1": transaction_ref,
                    },
                )
                data = response.json()

            if response.status_code == 200 and data.get("id"):
                return {
                    "success": True,
                    "payment_url": data.get("url"),
                    "gateway_transaction_id": data.get("id"),
                    "gateway_reference": data.get("id"),
                    "raw_response": data,
                }
            else:
                return {
                    "success": False,
                    "message": data.get("error", {}).get("message", ["Unknown error"]),
                    "raw_response": data,
                }
        except Exception as e:
            logger.error(f"Billplz create_payment error: {e}")
            return {"success": False, "message": str(e)}

    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        """Verify Billplz callback using x_signature."""
        x_signature = _as_str(payload.get("x_signature"))
        if not x_signature and headers:
            x_signature = _as_str(headers.get("x-signature"))
        
        # Billplz v4 callback verification
        signing_keys = ["amount", "collection_id", "email", "id", "name", 
                       "paid", "paid_amount", "paid_at", "state", "url"]
        sign_string = "|".join(
            f"{k}{payload.get(k, '')}" for k in signing_keys if k in payload
        )
        
        expected_sig = hmac.new(
            self.extra_config.get("x_signature_key", self.api_secret).encode(),
            sign_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(x_signature, expected_sig):
            return {"valid": False, "message": "Invalid Billplz signature"}

        paid_value = payload.get("paid")
        paid_normalized = _as_str(paid_value).lower()
        is_paid = paid_normalized in {"true", "1", "paid", "yes"} or paid_value is True

        return {
            "valid": True,
            "transaction_ref": payload.get("reference_1", ""),
            "gateway_transaction_id": payload.get("id", ""),
            "status": "success" if is_paid else "failed",
            "amount": float(payload.get("paid_amount", 0)) / 100,
            "payment_method": "fpx",
            "raw_response": payload,
        }

    async def check_status(self, gateway_transaction_id: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/bills/{gateway_transaction_id}",
                    auth=(self.api_key, ""),
                )
                data = response.json()

            status = "success" if data.get("paid") else "pending"
            if data.get("state") == "due" and data.get("due_at"):
                due = datetime.fromisoformat(data["due_at"].replace("Z", "+00:00"))
                if due < datetime.utcnow():
                    status = "expired"

            return {
                "status": status,
                "amount": float(data.get("amount", 0)) / 100,
                "raw_response": data,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════
#  FIUU GATEWAY (Provider-ready scaffold)
# ═══════════════════════════════════════════

class FiuuGateway(BasePaymentGateway):
    """
    Fiuu gateway scaffold.

    This class is intentionally provider-agnostic and ready for wiring
    once official endpoint + signature docs are confirmed.
    """

    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        # Integration point:
        # 1) Build provider payload from standard request
        # 2) Sign request using provider algorithm
        # 3) POST to FIUU endpoint and normalize response keys
        return {
            "success": False,
            "payment_url": None,
            "gateway_transaction_id": None,
            "gateway_reference": None,
            "message": "Fiuu gateway scaffold is ready. Waiting for final API spec mapping.",
            "raw_response": {},
        }

    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        """
        Verify Fiuu callback signature.

        Default supported mode:
        - md5(amount + merchant_id + orderid + verify_key) == skey

        Configurable via extra_config:
        - signature_mode: md5_concat | hmac_sha256
        - signature_field: skey (default)
        - signature_fields: ["amount", "merchant_id", "orderid"] (default)
        - verify_key: override key (fallback: api_secret)
        - transaction_ref_field: orderid (default)
        - gateway_txn_field: tranID (default)
        - status_field: status (default)
        - success_values: ["00","success","paid"] (default union)
        """
        cfg = self.extra_config or {}
        verify_key = _as_str(cfg.get("verify_key") or self.api_secret)
        if not verify_key:
            return {"valid": False, "message": "Fiuu verify key not configured"}

        signature_field = _as_str(cfg.get("signature_field") or "skey")
        provided_sig = _as_str(payload.get(signature_field))
        if not provided_sig and headers:
            provided_sig = _as_str(headers.get(signature_field)) or _as_str(headers.get(signature_field.lower()))
        if not provided_sig:
            return {"valid": False, "message": f"Missing Fiuu signature field '{signature_field}'"}

        signature_fields = cfg.get("signature_fields") or ["amount", "merchant_id", "orderid"]
        sign_raw = "".join(_as_str(payload.get(k)) for k in signature_fields) + verify_key
        mode = _as_str(cfg.get("signature_mode") or "md5_concat").lower()
        if mode == "hmac_sha256":
            expected_sig = hmac.new(verify_key.encode(), sign_raw.encode(), hashlib.sha256).hexdigest()
        else:
            expected_sig = hashlib.md5(sign_raw.encode()).hexdigest()  # nosec B324 (provider-compatible)

        if not secrets.compare_digest(provided_sig.lower(), expected_sig.lower()):
            return {"valid": False, "message": "Invalid Fiuu signature"}

        txn_field = _as_str(cfg.get("transaction_ref_field") or "orderid")
        gw_txn_field = _as_str(cfg.get("gateway_txn_field") or "tranID")
        status_field = _as_str(cfg.get("status_field") or "status")
        paid_amount_field = _as_str(cfg.get("paid_amount_field") or "amount")
        payment_method_field = _as_str(cfg.get("payment_method_field") or "channel")

        success_values = {v.lower() for v in (cfg.get("success_values") or ["00", "success", "paid", "1", "true"])}
        raw_status = _as_str(payload.get(status_field))
        normalized_status = "success" if raw_status.lower() in success_values else _normalize_status(raw_status)

        try:
            amount = float(_as_str(payload.get(paid_amount_field) or "0"))
        except ValueError:
            amount = 0.0

        return {
            "valid": True,
            "transaction_ref": _as_str(payload.get(txn_field)),
            "gateway_transaction_id": _as_str(payload.get(gw_txn_field)),
            "status": normalized_status,
            "amount": amount,
            "payment_method": _as_str(payload.get(payment_method_field) or "fiuu"),
            "raw_response": payload,
        }

    async def check_status(self, gateway_transaction_id: str) -> dict:
        return {
            "status": "pending",
            "message": "Fiuu status check scaffold is ready. Waiting for final API spec mapping.",
        }


# ═══════════════════════════════════════════
#  TNG GATEWAY (OrderCode API v1.0)
# ═══════════════════════════════════════════
# Based on TNG OrderCode Creation API spec (Feb 2024, v1.04).
# Creates QR code for user to scan with TNG app.
#
# Env:
#   PAYMENT_TNG_API_URL     - Base URL (get from TNG, e.g. https://api.tng.com.my/aps/api/v1)
#   PAYMENT_TNG_API_KEY     - clientId
#   PAYMENT_TNG_API_SECRET  - clientSecret (optional)
#   PAYMENT_TNG_MERCHANT_ID - Merchant ID
#   PAYMENT_TNG_MCC         - Merchant category code (default 5732)
#   PAYMENT_TNG_PRIVATE_KEY - Partner private key PKCS8 PEM (for signing)
#   PAYMENT_TNG_PUBLIC_KEY  - TNGD public key PKCS8 PEM (for callback verification)
#
# Sandbox: clientId 2171020126371234, clientSecret 2022081715510500019671JAQuDH
# Product codes: TNGD QR 51051000101000100046, DuitNow QR 51051000101000300048
# Sign/verify: SHA256 with RSA 2048, plaintext no whitespace (separators=(",",":")).
# ═══════════════════════════════════════════

# TNG OrderCode product codes per spec
TNG_PRODUCT_CODE_TNGD = "51051000101000100046"
TNG_PRODUCT_CODE_DUITNOW = "51051000101000300048"

def _tng_sign_message(msg_obj: dict, private_key_pem: str) -> str:
    """
    Sign message using RSA-SHA256 per TNG OrderCode API spec.
    Message must be plaintext, no whitespace/comments (separators=(",",":")).
    """
    try:
        key_bytes = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
        private_key = serialization.load_pem_private_key(key_bytes, password=None, backend=default_backend())
        msg = json.dumps(msg_obj, separators=(",", ":"), ensure_ascii=False)
        signature = private_key.sign(msg.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode()
    except Exception as e:
        logger.error(f"TNG sign error: {e}")
        raise


def _tng_verify_signature(msg_obj: dict, signature_b64: str, public_key_pem: str) -> bool:
    """
    Verify TNG callback signature using TNGD public key.
    Message must match exactly what TNG signed (plaintext, no whitespace).
    """
    try:
        pub_key = serialization.load_pem_public_key(public_key_pem.encode(), backend=default_backend())
        msg = json.dumps(msg_obj, separators=(",", ":"), ensure_ascii=False)
        sig_bytes = base64.b64decode(signature_b64)
        pub_key.verify(sig_bytes, msg.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


class TngGateway(BasePaymentGateway):
    """
    Touch 'n Go OrderCode API — Create QR for payment.
    User scans QR with TNG app to complete payment.
    """

    def _get_api_url(self) -> str:
        """Base URL from config or env PAYMENT_TNG_API_URL."""
        url = (self.production_url if not self.is_sandbox else self.sandbox_url) or ""
        if not url:
            url = os.getenv("PAYMENT_TNG_API_URL", "").strip()
        return url.rstrip("/")

    def _get_private_key(self) -> Optional[str]:
        """Partner private key (PKCS8 PEM) for signing."""
        key = self.extra_config.get("merchant_private_key") or os.getenv("PAYMENT_TNG_PRIVATE_KEY", "").strip()
        return key if key else None

    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        api_url = self._get_api_url()
        if not api_url:
            return {
                "success": False,
                "message": "PAYMENT_TNG_API_URL not configured. Get base URL from TNG.",
                "payment_url": None,
                "gateway_transaction_id": None,
                "gateway_reference": None,
                "raw_response": {},
            }

        # clientId/clientSecret: use env or config; sandbox defaults from TNG doc
        client_id = self.api_key or os.getenv("PAYMENT_TNG_API_KEY", "").strip()
        client_secret = self.api_secret or os.getenv("PAYMENT_TNG_API_SECRET", "").strip()
        if self.is_sandbox and not client_id:
            client_id = os.getenv("PAYMENT_TNG_SANDBOX_CLIENT_ID", "2171020126371234")
        if self.is_sandbox and not client_secret:
            client_secret = os.getenv("PAYMENT_TNG_SANDBOX_CLIENT_SECRET", "2022081715510500019671JAQuDH")
        merchant_id = self.merchant_id or os.getenv("PAYMENT_TNG_MERCHANT_ID", "").strip()
        mcc = self.extra_config.get("mcc") or os.getenv("PAYMENT_TNG_MCC", "5732").strip()
        private_key = self._get_private_key()

        if not all([client_id, merchant_id, private_key]):
            return {
                "success": False,
                "message": "TNG credentials missing: clientId, merchantId, private key required.",
                "payment_url": None,
                "gateway_transaction_id": None,
                "gateway_reference": None,
                "raw_response": {},
            }

        # Value in cents per TNG Money type (RM 10.00 = 1000 sen)
        value_cents = str(int(round(amount * 100)))
        req_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        req_msg_id = str(uuid.uuid4()).replace("-", "")[:32]

        # Product code: TNGD QR (default) or DuitNow QR via extra_config
        product_code = (
            self.extra_config.get("product_code")
            or os.getenv("PAYMENT_TNG_PRODUCT_CODE", TNG_PRODUCT_CODE_TNGD)
        ).strip() or TNG_PRODUCT_CODE_TNGD

        # Build request per TNG OrderCode API spec (head + body)
        body = {
            "merchantId": merchant_id,
            "subMerchantName": self.extra_config.get("sub_merchant_name") or "PlagSini EV",
            "mcc": mcc,
            "orderTitle": (description or "PlagSini EV Top-Up")[:256],
            "orderAmount": {"value": value_cents, "currency": (currency or "MYR")},
            "merchantTransId": transaction_ref,
            "productCode": product_code,
            "envinfo": {"terminalType": "SYSTEM", "orderTerminalType": "WEB"},
            "effectiveSeconds": "600",
            "notifyUrl": self.callback_url or "",
            "extendinfo": json.dumps({"PARTNER_TRANSACTION_ID": transaction_ref}),
        }
        if self.extra_config.get("sub_merchant_id"):
            body["subMerchantId"] = self.extra_config["sub_merchant_id"]
        order_memo = (description or "").strip()[:512]
        if order_memo:
            body["orderMemo"] = order_memo

        request_obj = {
            "request": {
                "head": {
                    "version": "1.0",
                    "function": "alipayplus.acquiring.ordercode.create",
                    "clientId": client_id,
                    "reqTime": req_time,
                    "reqMsgId": req_msg_id,
                },
                "body": body,
            }
        }
        if client_secret:
            request_obj["request"]["head"]["clientSecret"] = client_secret

        try:
            # Sign the request object (head + body) per spec - plaintext, no whitespace
            signature = _tng_sign_message(request_obj["request"], private_key)
            payload = {**request_obj, "signature": signature}

            # Endpoint: set PAYMENT_TNG_API_URL to full URL e.g. https://api.tng.com.my/aps/api/v1/ordercode
            endpoint = api_url if api_url.startswith("http") else f"{api_url}/aps/api/v1/payments/ordercode"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(endpoint, json=payload)
                data = resp.json() if resp.content else {}

            body = data.get("response", data).get("body", data.get("body", {}))
            result_info = body.get("resultInfo", {})
            result_code = result_info.get("resultCode", "")
            result_code_id = result_info.get("resultCodeId", "")
            result_status = result_info.get("resultStatus", "")
            result_msg = result_info.get("resultMsg", "TNG API error")

            # Per spec: S=success, F=failure, U=unknown
            if result_status == "S" and result_code == "SUCCESS":
                order_qr = body.get("orderQrCode", "")
                acquirement_id = body.get("acquirementId", "")
                return {
                    "success": True,
                    "payment_url": None,
                    "qr_code": order_qr,
                    "gateway_transaction_id": acquirement_id,
                    "gateway_reference": acquirement_id,
                    "raw_response": data,
                }
            # Map common error codes per spec (00000004=INVALID_SIGNATURE, etc.)
            if result_code_id == "00000004":
                result_msg = "Invalid signature — check private key and request format"
            elif result_code_id == "00000002":
                result_msg = "Missing mandatory parameter"
            return {
                "success": False,
                "message": result_msg,
                "payment_url": None,
                "gateway_transaction_id": body.get("acquirementId"),
                "gateway_reference": body.get("acquirementId"),
                "raw_response": data,
            }
        except Exception as e:
            logger.error(f"TNG create_payment error: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "payment_url": None,
                "gateway_transaction_id": None,
                "gateway_reference": None,
                "raw_response": {},
            }

    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        """
        Verify TNG payment notification callback.
        Payload format per spec: {"response":{"head":{...},"body":{...}},"signature":"..."}
        TNG signs the "response" object (head + body) with SHA256-RSA. Verify using TNGD public key.
        """
        cfg = self.extra_config or {}
        provided_sig = _as_str(payload.get("signature", ""))
        if not provided_sig and headers:
            provided_sig = _as_str(headers.get("X-TNG-Signature", "") or headers.get("signature", ""))

        if not provided_sig:
            return {"valid": False, "message": "Missing TNG callback signature"}

        tng_public_key = cfg.get("tng_public_key") or os.getenv("PAYMENT_TNG_PUBLIC_KEY", "").strip()
        if not tng_public_key:
            logger.warning("TNG callback: PUBLIC_KEY not configured — cannot verify. Get from TNGD.")
            return {"valid": False, "message": "TNG public key not configured for callback verification"}

        # Per spec: TNG signs "the value of the response object" = {"head":{...},"body":{...}}
        # Message must match exactly (plaintext, no whitespace)
        response_obj = payload.get("response")
        if not isinstance(response_obj, dict) or "body" not in response_obj:
            return {"valid": False, "message": "Invalid TNG callback: missing response.head/body"}

        valid_sig = _tng_verify_signature(response_obj, provided_sig, tng_public_key)
        if not valid_sig:
            return {"valid": False, "message": "Invalid TNG callback signature"}

        body = response_obj.get("body", {})
        result_info = body.get("resultInfo", {})
        result_status = result_info.get("resultStatus", "")
        order_amount = body.get("orderAmount", {})
        value_cents = order_amount.get("value", 0) if isinstance(order_amount, dict) else 0
        try:
            amount_rm = float(value_cents) / 100.0
        except (TypeError, ValueError):
            amount_rm = 0.0

        return {
            "valid": True,
            "transaction_ref": body.get("merchantTransId", ""),
            "gateway_transaction_id": body.get("acquirementId", ""),
            "status": "success" if result_status == "S" else "pending",
            "amount": amount_rm,
            "payment_method": "tng",
            "raw_response": payload,
        }

    async def check_status(self, gateway_transaction_id: str) -> dict:
        """
        Check TNG payment status from gateway.
        TODO: Implement when TNG status query API spec is available.
        """
        return {
            "status": "pending",
            "message": "TNG status check scaffold is ready. Waiting for final API spec mapping.",
        }


# ═══════════════════════════════════════════
#  MANUAL TOP-UP (Admin Approved)
# ═══════════════════════════════════════════

class ManualGateway(BasePaymentGateway):
    """
    Manual top-up — Admin verifies bank transfer and approves.
    No API integration needed.
    """

    async def create_payment(
        self,
        transaction_ref: str,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: str,
        payment_method: Optional[str] = None,
    ) -> dict:
        return {
            "success": True,
            "payment_url": None,
            "gateway_transaction_id": f"MANUAL-{transaction_ref}",
            "gateway_reference": transaction_ref,
            "message": "Manual payment created. Admin will verify and approve.",
            "raw_response": {"type": "manual", "status": "pending_approval"},
        }

    def verify_callback(self, payload: dict, headers: dict = None) -> dict:
        return {
            "valid": True,
            "transaction_ref": payload.get("transaction_ref", ""),
            "gateway_transaction_id": payload.get("gateway_transaction_id", ""),
            "status": payload.get("status", "success"),
            "amount": float(payload.get("amount", 0)),
            "payment_method": "bank_transfer",
            "raw_response": payload,
        }

    async def check_status(self, gateway_transaction_id: str) -> dict:
        return {"status": "pending", "message": "Awaiting admin approval"}


# ═══════════════════════════════════════════
#  GATEWAY FACTORY
# ═══════════════════════════════════════════

GATEWAY_REGISTRY = {
    "ocbc": OcbcGateway,
    "billplz": BillplzGateway,
    "fiuu": FiuuGateway,
    "tng": TngGateway,
    "manual": ManualGateway,
}


_GATEWAY_ALIASES = {
    "razer": "fiuu",
    "razerms": "fiuu",
    "fiuu_vt": "fiuu",
    "touchngo": "tng",
    "touch_n_go": "tng",
    "tng_ewallet": "tng",
}


def get_gateway(config: dict) -> BasePaymentGateway:
    """
    Get the appropriate gateway instance based on config.
    
    Args:
        config: dict from PaymentGatewayConfig table row
    
    Returns:
        Gateway instance
    """
    gateway_name = str(config.get("gateway_name", "manual")).strip().lower()
    gateway_name = _GATEWAY_ALIASES.get(gateway_name, gateway_name)
    gateway_class = GATEWAY_REGISTRY.get(gateway_name, ManualGateway)
    return gateway_class(config)


def generate_transaction_ref() -> str:
    """Generate unique transaction reference: TXN-YYYYMMDD-XXXXX"""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()
    return f"TXN-{date_str}-{random_part}"

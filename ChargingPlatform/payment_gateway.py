"""
PlagSini EV — Payment Gateway Abstraction Layer

Supports plugging in any Malaysian payment gateway:
  - OCBC Payment Gateway
  - Billplz (FPX)
  - Fiuu / Razer Merchant Services
  - Stripe
  - Manual top-up (admin approved)

When OCBC provides their API docs, just implement OcbcGateway class.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

import httpx

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
        x_signature = payload.get("x_signature", "")
        
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

        return {
            "valid": True,
            "transaction_ref": payload.get("reference_1", ""),
            "gateway_transaction_id": payload.get("id", ""),
            "status": "success" if payload.get("paid") == "true" else "failed",
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
#  MANUAL TOP-UP (Admin Approved)
# ═══════════════════════════════════════════

class ManualGateway(BasePaymentGateway):
    """
    Manual top-up — Admin verifies bank transfer and approves.
    No API integration needed.
    """

    async def create_payment(self, transaction_ref, amount, currency, description,
                           customer_email, customer_name, payment_method=None) -> dict:
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
    "manual": ManualGateway,
}


def get_gateway(config: dict) -> BasePaymentGateway:
    """
    Get the appropriate gateway instance based on config.
    
    Args:
        config: dict from PaymentGatewayConfig table row
    
    Returns:
        Gateway instance
    """
    gateway_name = config.get("gateway_name", "manual")
    gateway_class = GATEWAY_REGISTRY.get(gateway_name, ManualGateway)
    return gateway_class(config)


def generate_transaction_ref() -> str:
    """Generate unique transaction reference: TXN-YYYYMMDD-XXXXX"""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()
    return f"TXN-{date_str}-{random_part}"

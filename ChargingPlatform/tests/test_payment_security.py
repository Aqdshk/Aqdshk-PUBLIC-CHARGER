import hashlib
import hmac
import os
import unittest
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from payment_gateway import (
    BillplzGateway,
    FiuuGateway,
    TngGateway,
    is_callback_already_processed,
    _tng_sign_message,
)


class PaymentSecurityTests(unittest.TestCase):
    def test_fiuu_callback_signature_valid(self):
        verify_key = "fiuu-secret"
        payload = {
            "amount": "50.00",
            "merchant_id": "M123",
            "orderid": "TXN-20260302-ABCDE",
            "tranID": "FW12345",
            "status": "00",
            "channel": "fpx",
        }
        raw = f"{payload['amount']}{payload['merchant_id']}{payload['orderid']}{verify_key}"
        payload["skey"] = hashlib.md5(raw.encode()).hexdigest()  # nosec B324

        gateway = FiuuGateway(
            {
                "gateway_name": "fiuu",
                "api_secret": verify_key,
                "extra_config": "{}",
            }
        )
        result = gateway.verify_callback(payload, headers={})
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["transaction_ref"], payload["orderid"])

    def test_fiuu_callback_signature_invalid(self):
        gateway = FiuuGateway({"gateway_name": "fiuu", "api_secret": "abc", "extra_config": "{}"})
        payload = {
            "amount": "10.00",
            "merchant_id": "M1",
            "orderid": "TXN-1",
            "skey": "bad",
        }
        result = gateway.verify_callback(payload, headers={})
        self.assertFalse(result["valid"])

    def test_tng_callback_signature_valid(self):
        """TNG callback uses RSA signature; payload format: {response:{head,body}, signature}."""
        # Generate temp RSA key pair for test
        priv = rsa.generate_private_key(65537, 2048, default_backend())
        pub_pem = priv.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        priv_pem = priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        response_obj = {
            "head": {"clientId": "test", "reqMsgId": "123"},
            "body": {
                "merchantTransId": "TXN-20260302-AAAAA",
                "acquirementId": "TG-123",
                "orderAmount": {"value": "2050", "currency": "MYR"},
                "resultInfo": {"resultStatus": "S", "resultCode": "SUCCESS"},
            },
        }
        payload = {"response": response_obj, "signature": _tng_sign_message(response_obj, priv_pem)}

        old_val = os.environ.get("PAYMENT_TNG_PUBLIC_KEY")
        os.environ["PAYMENT_TNG_PUBLIC_KEY"] = pub_pem
        try:
            gateway = TngGateway({"gateway_name": "tng", "extra_config": "{}"})
            result = gateway.verify_callback(payload, headers={})
            self.assertTrue(result["valid"])
            self.assertEqual(result["transaction_ref"], "TXN-20260302-AAAAA")
            self.assertEqual(result["gateway_transaction_id"], "TG-123")
            self.assertAlmostEqual(result["amount"], 20.50)
            self.assertEqual(result["status"], "success")
        finally:
            if old_val is not None:
                os.environ["PAYMENT_TNG_PUBLIC_KEY"] = old_val
            else:
                os.environ.pop("PAYMENT_TNG_PUBLIC_KEY", None)

    def test_billplz_callback_accepts_header_signature(self):
        payload = {
            "amount": "1000",
            "collection_id": "col_1",
            "email": "user@example.com",
            "id": "bill_1",
            "name": "User",
            "paid": "true",
            "paid_amount": "1000",
            "paid_at": "2026-03-02T10:00:00Z",
            "state": "paid",
            "url": "https://billplz.test/bill_1",
            "reference_1": "TXN-20260302-11111",
        }
        sign_string = "|".join(
            f"{k}{payload.get(k, '')}"
            for k in ["amount", "collection_id", "email", "id", "name", "paid", "paid_amount", "paid_at", "state", "url"]
        )
        key = "billplz-sign-key"
        signature = hmac.new(key.encode(), sign_string.encode(), hashlib.sha256).hexdigest()
        gateway = BillplzGateway(
            {
                "gateway_name": "billplz",
                "api_secret": "",
                "extra_config": '{"x_signature_key":"billplz-sign-key"}',
            }
        )
        result = gateway.verify_callback(payload, headers={"x-signature": signature})
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "success")

    def test_callback_idempotency_guard(self):
        txn_success = SimpleNamespace(status="success", wallet_transaction_id=None)
        self.assertTrue(is_callback_already_processed(txn_success))

        txn_credited = SimpleNamespace(status="processing", wallet_transaction_id=123)
        self.assertTrue(is_callback_already_processed(txn_credited))

        txn_fresh = SimpleNamespace(status="processing", wallet_transaction_id=None)
        self.assertFalse(is_callback_already_processed(txn_fresh))


if __name__ == "__main__":
    unittest.main()

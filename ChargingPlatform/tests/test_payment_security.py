import hashlib
import hmac
import unittest
from types import SimpleNamespace

from payment_gateway import BillplzGateway, FiuuGateway, TngGateway, is_callback_already_processed


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
        key = "tng-secret"
        payload = {
            "transaction_ref": "TXN-20260302-AAAAA",
            "gateway_transaction_id": "TG-123",
            "amount": "20.50",
            "status": "paid",
            "payment_method": "tng",
        }
        sign_raw = f"{payload['transaction_ref']}{payload['amount']}{payload['status']}"
        payload["signature"] = hmac.new(key.encode(), sign_raw.encode(), hashlib.sha256).hexdigest()
        gateway = TngGateway({"gateway_name": "tng", "api_secret": key, "extra_config": "{}"})
        result = gateway.verify_callback(payload, headers={})
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "success")

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

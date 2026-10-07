"""Partner stop must reach the charger.

On 2026-10-06 a guest pressed stop in the Proton app, the platform answered
200 "Charging already stopped", and the car charged for another 73 minutes.
No RemoteStopTransaction had been sent.

RemoteStart leaves a placeholder session (negative transaction_id) stamped
with our clock, marked completed when the charger's StartTransaction arrives.
The real session carries the charger's own timestamp, which was three seconds
earlier, so "latest session on the charger" was the finished placeholder.
"""
import hashlib
import unittest
from datetime import datetime
from unittest import mock

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargingSession, PartnerAPIKey, PaymentTransaction,
    SessionLocal, User, engine,
)

KEY = "test-partner-stop-key"
CP = "STOP-TEST-CP"


class _Accepted:
    status = "Accepted"


class _FakeChargePoint:
    def __init__(self):
        self.stopped = []

    async def remote_stop_transaction(self, transaction_id):
        self.stopped.append(transaction_id)
        return _Accepted()


class PartnerStopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        user = User(email="stop-test@example.com", password_hash="x", is_active=True)
        charger = Charger(charge_point_id=CP, tenant="stop-tenant")
        db.add_all([
            user,
            charger,
            PartnerAPIKey(
                partner_name="stop-partner",
                key_hash=hashlib.sha256(KEY.encode()).hexdigest(),
                active=True,
                controls_tenant="stop-tenant",
            ),
        ])
        db.commit()
        cls.user_id, cls.charger_pk = user.id, charger.id
        db.close()
        cls.client = TestClient(api.app)

    def _payment(self, ref, paid_at_utc):
        db = SessionLocal()
        db.add(PaymentTransaction(
            transaction_ref=ref, user_id=self.user_id, user_email="stop-test@example.com",
            amount=0, gateway_name="manual", status="success",
            charger_id=CP, connector_id=1, paid_at=paid_at_utc,
        ))
        db.commit()
        db.close()

    def _session(self, transaction_id, start_myt, status):
        db = SessionLocal()
        db.add(ChargingSession(
            charger_id=self.charger_pk, connector_id=1, transaction_id=transaction_id,
            start_time=start_myt, status=status, user_id=0,
        ))
        db.commit()
        db.close()

    def _stop(self, ref):
        cp = _FakeChargePoint()
        with mock.patch.object(api, "get_active_charge_point", return_value=cp):
            r = self.client.post(
                "/api/partner/charging/stop",
                json={"transaction_ref": ref, "customer_id": "guest-1"},
                headers={"X-Partner-API-Key": KEY},
            )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json(), cp.stopped

    def test_stops_the_real_session_not_the_placeholder(self):
        # The times of the incident: paid 12:39:01 UTC, which is 20:39:01 MYT.
        self._payment("TXN-STOP-1", datetime(2026, 10, 6, 12, 39, 1))
        self._session(9442, datetime(2026, 10, 6, 20, 39, 1), "active")
        self._session(-9441, datetime(2026, 10, 6, 20, 39, 4), "completed")

        body, stopped = self._stop("TXN-STOP-1")

        self.assertEqual(stopped, [9442])
        self.assertTrue(body["success"])
        self.assertEqual(body["message"], "Charging stopped")

    def test_placeholder_alone_is_not_a_session_to_stop(self):
        # The charger has accepted RemoteStart but not yet sent StartTransaction.
        self._payment("TXN-STOP-2", datetime(2026, 10, 7, 1, 0, 0))
        self._session(-9500, datetime(2026, 10, 7, 9, 0, 3), "pending")

        body, stopped = self._stop("TXN-STOP-2")

        self.assertEqual(stopped, [])
        self.assertFalse(body["success"])

    def test_a_later_charge_on_the_same_charger_is_left_alone(self):
        # This payment's own session has finished; someone else is now charging.
        self._payment("TXN-STOP-3", datetime(2026, 10, 8, 1, 0, 0))
        self._session(9601, datetime(2026, 10, 8, 9, 0, 5), "completed")
        self._session(9602, datetime(2026, 10, 8, 10, 30, 0), "active")

        body, stopped = self._stop("TXN-STOP-3")

        self.assertEqual(stopped, [])
        self.assertEqual(body["message"], "Charging already stopped")


if __name__ == "__main__":
    unittest.main()

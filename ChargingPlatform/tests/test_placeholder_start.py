"""A start that is under way must not be reported as finished.

On 2026-10-10 a guest started two charges on an AION E7 through the Proton
app. Both times the app showed the charge as over within ten seconds while the
car went on charging, the second time for hours.

Two faults, both replayed here from that evening's log:

1. The charger sent SuspendedEV a few seconds before its StartTransaction.
   Every status other than Charging cleared the RemoteStart placeholder, so
   the partner was told "completed, 0 kWh".
2. The second charge began 88 seconds after the first. The lookup behind
   /api/partner/charging/sessions/{ref} reaches two minutes back from the
   payment, found the first charge there, and answered with it.
"""
import asyncio
import hashlib
import unittest
from datetime import datetime
from unittest import mock

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import ocpp_server  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargingSession, PartnerAPIKey, PaymentTransaction,
    SessionLocal, User, engine,
)

KEY = "test-placeholder-key"
CP = "PLACEHOLDER-TEST-CP"


class PlaceholderStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        user = User(email="placeholder-test@example.com", password_hash="x", is_active=True)
        charger = Charger(charge_point_id=CP, tenant="placeholder-tenant")
        db.add_all([
            user,
            charger,
            PartnerAPIKey(
                partner_name="placeholder-partner",
                key_hash=hashlib.sha256(KEY.encode()).hexdigest(),
                active=True,
                controls_tenant="placeholder-tenant",
            ),
        ])
        db.commit()
        cls.user_id, cls.charger_pk = user.id, charger.id
        db.close()
        cls.client = TestClient(api.app)

    def setUp(self):
        db = SessionLocal()
        db.query(ChargingSession).filter(ChargingSession.charger_id == self.charger_pk).delete()
        db.commit()
        db.close()
        # The handlers only need their id and a database session.
        self.cp = ocpp_server.ChargePoint.__new__(ocpp_server.ChargePoint)
        self.cp.id = CP
        self.cp.db = SessionLocal()

    def tearDown(self):
        self.cp.db.close()

    def _placeholder(self, start_myt):
        """What RemoteStart leaves behind while the charger is yet to answer."""
        db = SessionLocal()
        row = ChargingSession(
            charger_id=self.charger_pk, connector_id=1, transaction_id=0,
            start_time=start_myt, status="pending", user_id=0, energy_kwh_limit=5,
        )
        db.add(row)
        db.flush()
        row.transaction_id = -row.id
        db.commit()
        pk = row.id
        db.close()
        return pk

    def _status(self, status):
        asyncio.run(self.cp.on_status_notification(connector_id=1, error_code="NoError", status=status))

    def _row(self, pk):
        db = SessionLocal()
        row = db.query(ChargingSession).filter(ChargingSession.id == pk).first()
        db.expunge(row)
        db.close()
        return row

    # ── 1. the placeholder ────────────────────────────────────────────────

    def test_suspended_ev_before_start_transaction_keeps_the_placeholder(self):
        pk = self._placeholder(datetime(2026, 10, 10, 19, 6, 48))
        self._status("SuspendedEV")
        row = self._row(pk)
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.stop_time)

    def test_suspended_evse_keeps_it_too(self):
        pk = self._placeholder(datetime(2026, 10, 10, 19, 6, 48))
        self._status("SuspendedEVSE")
        self.assertEqual(self._row(pk).status, "pending")

    def test_start_transaction_then_adopts_it_with_its_quota(self):
        pk = self._placeholder(datetime(2026, 10, 10, 19, 6, 48))
        self._status("SuspendedEV")
        asyncio.run(self.cp.on_start_transaction(
            connector_id=1, id_tag="DASHBOARD_USER", meter_start=632227,
            timestamp="2026-10-10T11:06:47.000Z",
        ))
        db = SessionLocal()
        rows = db.query(ChargingSession).filter(ChargingSession.charger_id == self.charger_pk).all()
        self.assertEqual(len(rows), 1, "the charger's session must be the placeholder, not a second row")
        self.assertEqual(rows[0].id, pk)
        self.assertEqual(rows[0].status, "active")
        self.assertEqual(rows[0].transaction_id, pk)
        self.assertEqual(float(rows[0].energy_kwh_limit), 5.0)
        db.close()

    def test_unplugging_without_charging_still_clears_it(self):
        """The start never happened: the cable came out. That is still an end."""
        pk = self._placeholder(datetime(2026, 10, 10, 19, 6, 48))
        self._status("Available")
        row = self._row(pk)
        self.assertEqual(row.status, "completed")
        self.assertIsNotNone(row.stop_time)

    # ── 2. which session a payment is answered with ───────────────────────

    def _payment(self, ref, paid_at_utc):
        db = SessionLocal()
        db.add(PaymentTransaction(
            transaction_ref=ref, user_id=self.user_id, user_email="placeholder-test@example.com",
            amount=0, gateway_name="manual", status="success",
            charger_id=CP, connector_id=1, paid_at=paid_at_utc,
        ))
        db.commit()
        db.close()

    def _session(self, transaction_id, start_myt, stop_myt, status, kwh=0, reason=None):
        db = SessionLocal()
        db.add(ChargingSession(
            charger_id=self.charger_pk, connector_id=1, transaction_id=transaction_id,
            start_time=start_myt, stop_time=stop_myt, status=status, user_id=0,
            energy_consumed=kwh, stop_reason=reason,
        ))
        db.commit()
        db.close()

    def _poll(self, ref):
        res = self.client.get(f"/api/partner/charging/sessions/{ref}", headers={"X-Partner-API-Key": KEY})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["transaction"]["charging_session"]

    def test_second_charge_is_not_answered_with_the_first(self):
        # First charge: 19:06:47 to 19:07:30, ended by a power cut.
        self._session(9509, datetime(2026, 10, 10, 19, 6, 47), datetime(2026, 10, 10, 19, 7, 30),
                      "completed", kwh=0.066, reason="PowerLoss")
        # Second: paid at 19:08:15 MYT (11:08:15 UTC), started 19:08:16, still running.
        self._payment("TXN-PLACEHOLDER-SECOND", datetime(2026, 10, 10, 11, 8, 15))
        self._session(9511, datetime(2026, 10, 10, 19, 8, 16), None, "active", kwh=0.02)

        session = self._poll("TXN-PLACEHOLDER-SECOND")
        self.assertEqual(session["transaction_id"], 9511)
        self.assertEqual(session["status"], "active")
        self.assertIsNone(session["stop_time"])

    def test_a_charge_whose_clock_runs_ahead_is_still_found(self):
        """The look-back window is there for this, and must keep working."""
        self._payment("TXN-PLACEHOLDER-AHEAD", datetime(2026, 10, 10, 12, 0, 0))
        self._session(9520, datetime(2026, 10, 10, 19, 59, 30), datetime(2026, 10, 10, 20, 30, 0),
                      "completed", kwh=3.2)
        self.assertEqual(self._poll("TXN-PLACEHOLDER-AHEAD")["transaction_id"], 9520)

    def test_stop_acts_on_the_second_charge_not_the_first(self):
        self._session(9530, datetime(2026, 10, 10, 21, 6, 47), datetime(2026, 10, 10, 21, 7, 30),
                      "completed", kwh=0.066, reason="PowerLoss")
        self._payment("TXN-PLACEHOLDER-STOP", datetime(2026, 10, 10, 13, 8, 15))
        self._session(9531, datetime(2026, 10, 10, 21, 8, 16), None, "active")

        stopped = []

        class _Accepted:
            status = "Accepted"

        class _FakeChargePoint:
            async def remote_stop_transaction(self, transaction_id):
                stopped.append(transaction_id)
                return _Accepted()

        with mock.patch.object(api, "get_active_charge_point", return_value=_FakeChargePoint()):
            res = self.client.post(
                "/api/partner/charging/stop",
                json={"transaction_ref": "TXN-PLACEHOLDER-STOP", "customer_id": "guest-1"},
                headers={"X-Partner-API-Key": KEY},
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(stopped, [9531])


if __name__ == "__main__":
    unittest.main()

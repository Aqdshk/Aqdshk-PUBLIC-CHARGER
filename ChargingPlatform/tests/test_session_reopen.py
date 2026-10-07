"""A session closed on BootNotification is reopened if the charger carries on.

AION E7 units send BootNotification after a plain network reconnect, with the
transaction still running. The boot handler closes every open session on that
charger as an orphan. On 2026-10-07 that ended a guest's session four minutes
in: the partner app saw a stop_time and showed the charge as finished while
the car was still charging. The charger's next MeterValues for the same
transaction is the evidence that it never stopped.
"""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone

import ocpp_server  # noqa: E402
from database import Base, Charger, ChargingSession, SessionLocal, engine  # noqa: E402

CP = "REOPEN-TEST-CP"
MYT = timezone(timedelta(hours=8))


def _reading(when_utc, wh):
    return [{
        "timestamp": when_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "sampled_value": [{
            "value": str(wh), "measurand": "Energy.Active.Import.Register", "unit": "Wh",
        }],
    }]


class SessionReopenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        charger = Charger(charge_point_id=CP, tenant="reopen-tenant")
        db.add(charger)
        db.commit()
        cls.charger_pk = charger.id
        db.close()

    def setUp(self):
        # The handler only needs its id and a database session.
        self.cp = ocpp_server.ChargePoint.__new__(ocpp_server.ChargePoint)
        self.cp.id = CP
        self.cp.db = SessionLocal()

    def tearDown(self):
        self.cp.db.close()

    def _session(self, transaction_id, status, stop_time):
        db = SessionLocal()
        db.add(ChargingSession(
            charger_id=self.charger_pk, connector_id=1, transaction_id=transaction_id,
            start_time=datetime(2026, 10, 7, 9, 5, 49), stop_time=stop_time,
            status=status, user_id=0, meter_start=3732000,
        ))
        db.commit()
        db.close()

    def _send(self, transaction_id, when_utc, wh):
        asyncio.run(self.cp.on_meter_values(
            connector_id=1, meter_value=_reading(when_utc, wh), transaction_id=transaction_id,
        ))

    def _row(self, transaction_id):
        db = SessionLocal()
        try:
            return db.query(ChargingSession).filter(
                ChargingSession.transaction_id == transaction_id).first()
        finally:
            db.close()

    def test_reading_after_the_closure_reopens_the_session(self):
        # Closed by the boot handler at 09:09:25 MYT; the charger reports
        # again at 09:09:40 MYT, which is 01:09:40 UTC.
        self._session(8444, "interrupted", datetime(2026, 10, 7, 9, 9, 25))

        self._send(8444, datetime(2026, 10, 7, 1, 9, 40), 3733500)

        row = self._row(8444)
        self.assertEqual(row.status, "active")
        self.assertIsNone(row.stop_time)
        self.assertAlmostEqual(float(row.energy_consumed), 1.5, places=3)

    def test_reading_queued_before_the_reboot_leaves_it_closed(self):
        self._session(8445, "interrupted", datetime(2026, 10, 7, 9, 9, 25))

        self._send(8445, datetime(2026, 10, 7, 1, 9, 10), 3733000)

        row = self._row(8445)
        self.assertEqual(row.status, "interrupted")
        self.assertIsNotNone(row.stop_time)

    def test_a_completed_session_is_never_reopened(self):
        # Chargers keep sending MeterValues for a while after StopTransaction.
        self._session(8446, "completed", datetime(2026, 10, 7, 9, 9, 25))

        self._send(8446, datetime(2026, 10, 7, 1, 10, 0), 3734000)

        self.assertEqual(self._row(8446).status, "completed")


if __name__ == "__main__":
    unittest.main()

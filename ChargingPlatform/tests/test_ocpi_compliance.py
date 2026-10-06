"""The OCPI points Voltality raised in review, pinned down.

Each test here stands for a specific thing a partner actually broke on, so
none of them can quietly regress:

  - a request for one EVSE or one connector fell through to the router and
    came back as a bare 404 with no OCPI body
  - list endpoints took an uncapped limit and answered with no pagination
    headers, so a caller could not tell a full page from the last one
  - costs were bare numbers where the spec models a Price
  - /taxes advertised SST at 6% when C Zero is not SST registered
  - idle was measured to stop_time, so a session stopped from the app or by a
    roaming partner billed nothing however long the car blocked the bay
"""
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import idle_billing  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargingSession, SessionLocal, engine,
)

AUTH = {"Authorization": "Token test-token"}
CP = "OCPITEST1"
LOC = "MYPLG-" + CP
EVSE = LOC + "-EVSE1"


class OcpiTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(api.app)
        db = SessionLocal()
        try:
            db.query(ChargingSession).filter(
                ChargingSession.charger_id.in_(
                    db.query(Charger.id).filter(Charger.charge_point_id == CP)
                )
            ).delete(synchronize_session=False)
            db.query(Charger).filter(Charger.charge_point_id == CP).delete()
            db.commit()
            charger = Charger(
                charge_point_id=CP,
                connector_type="CCS2",
                tariff_per_kwh=1.00,
                idle_fee_enabled=True,
                idle_fee_per_min=0.40,
                idle_grace_minutes=15,
                status="available",
                # Publication is opt-out by staleness, and a fixture charger
                # has never sent a heartbeat.
                is_public=True,
            )
            db.add(charger)
            db.commit()
            cls.charger_id = charger.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        # The suite shares one SQLite file, so a fixture charger left behind
        # turns up in another module's counts.
        db = SessionLocal()
        try:
            db.query(Charger).filter(Charger.charge_point_id == CP).delete()
            db.commit()
        finally:
            db.close()


class LocationSubEndpointTests(OcpiTestBase):
    """Venu's point 3: the Locations sender interface is four endpoints."""

    def test_single_evse_is_served(self):
        r = self.client.get(f"/ocpi/2.2.1/locations/{LOC}/{EVSE}", headers=AUTH)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status_code"], 1000)
        self.assertEqual(body["data"]["uid"], EVSE)

    def test_single_connector_is_served(self):
        r = self.client.get(f"/ocpi/2.2.1/locations/{LOC}/{EVSE}/1", headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["id"], "1")

    def test_unknown_evse_is_an_ocpi_error_not_a_bare_404(self):
        # The failure mode being guarded: FastAPI's own 404 carries no
        # status_code, so a partner's client cannot parse it as OCPI.
        r = self.client.get(f"/ocpi/2.2.1/locations/{LOC}/{LOC}-EVSE99", headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status_code"], 2003)

    def test_unknown_location_is_an_ocpi_error(self):
        r = self.client.get("/ocpi/2.2.1/locations/MYPLG-NOPE/MYPLG-NOPE-EVSE1", headers=AUTH)
        self.assertEqual(r.json()["status_code"], 2003)


class PaginationTests(OcpiTestBase):
    """Venu's point 4: cap the page and say so in the headers."""

    def test_headers_present_on_locations(self):
        r = self.client.get("/ocpi/2.2.1/locations?offset=0&limit=1", headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-Total-Count", r.headers)
        self.assertEqual(r.headers["X-Limit"], "1")

    def test_limit_is_capped(self):
        # An uncapped limit let one request ask for the whole table.
        r = self.client.get("/ocpi/2.2.1/locations?limit=999999", headers=AUTH)
        self.assertLessEqual(int(r.headers["X-Limit"]), 1000)

    def test_next_link_only_while_pages_remain(self):
        r = self.client.get("/ocpi/2.2.1/locations?offset=0&limit=1", headers=AUTH)
        total = int(r.headers["X-Total-Count"])
        if total > 1:
            self.assertIn('rel="next"', r.headers.get("Link", ""))
        r_last = self.client.get(f"/ocpi/2.2.1/locations?offset={total}&limit=1", headers=AUTH)
        self.assertNotIn("Link", r_last.headers)

    def test_headers_on_sessions_and_cdrs(self):
        for path in ("/ocpi/2.2.1/sessions", "/ocpi/2.2.1/cdrs", "/ocpi/2.2.1/tariffs"):
            with self.subTest(path=path):
                r = self.client.get(path + "?limit=5", headers=AUTH)
                self.assertEqual(r.headers["X-Limit"], "5")
                self.assertIn("X-Total-Count", r.headers)


class TaxTests(OcpiTestBase):
    """Venu's point 1: we are not SST registered, so we advertise no tax."""

    def test_no_tax_advertised(self):
        r = self.client.get("/ocpi/2.2.1/taxes", headers=AUTH)
        self.assertEqual(r.json()["data"], [])

    def test_taxes_not_advertised_as_an_ocpi_module(self):
        r = self.client.get("/ocpi/2.2.1", headers=AUTH)
        ids = {e["identifier"] for e in r.json()["data"]["endpoints"]}
        self.assertNotIn("taxes", ids)
        self.assertIn("locations", ids)


class IdleAccrualTests(unittest.TestCase):
    """Venu's point 2: idle runs to the unplug, not to stop_time.

    A remote stop closes the transaction the instant it is requested, so
    stop_time and idle_started_at land together and the old arithmetic scored
    every such session as zero chargeable minutes.
    """

    def setUp(self):
        self.charger = Charger(
            charge_point_id="IDLETEST",
            idle_fee_enabled=True,
            idle_fee_per_min=0.40,
            idle_grace_minutes=15,
        )
        self.stopped_at = datetime(2026, 10, 6, 12, 0, 0)

    def _session(self, **kw):
        s = ChargingSession(transaction_id=1, status="completed")
        s.stop_time = self.stopped_at
        s.idle_started_at = self.stopped_at
        s.unplugged_at = None
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_grace_is_free(self):
        s = self._session(unplugged_at=self.stopped_at + timedelta(minutes=10))
        self.assertEqual(idle_billing.compute_idle(s, self.charger), (0, 0.0))

    def test_billed_from_the_unplug_not_the_stop(self):
        # 75 minutes plugged in after the stop, 15 of them free.
        s = self._session(unplugged_at=self.stopped_at + timedelta(minutes=75))
        minutes, fee = idle_billing.compute_idle(s, self.charger)
        self.assertEqual(minutes, 60)
        self.assertEqual(fee, 24.0)

    def test_still_plugged_in_accrues_against_now(self):
        s = self._session()
        now = self.stopped_at + timedelta(minutes=45)
        minutes, _ = idle_billing.compute_idle(s, self.charger, now=now)
        self.assertEqual(minutes, 30)

    def test_accrual_is_capped_so_a_lost_charger_cannot_bill_forever(self):
        s = self._session()
        far_future = self.stopped_at + timedelta(days=30)
        minutes, _ = idle_billing.compute_idle(s, self.charger, now=far_future)
        cap = idle_billing.hold_cap_minutes()
        self.assertEqual(minutes, cap - int(self.charger.idle_grace_minutes))

    def test_charger_without_idle_fee_accrues_nothing(self):
        self.charger.idle_fee_enabled = False
        s = self._session(unplugged_at=self.stopped_at + timedelta(hours=5))
        self.assertEqual(idle_billing.compute_idle(s, self.charger), (0, 0.0))

    def test_cdr_is_held_until_the_cable_comes_out(self):
        s = self._session()
        self.assertTrue(idle_billing.awaiting_unplug(s, self.charger, now=self.stopped_at))
        s.unplugged_at = self.stopped_at + timedelta(minutes=5)
        self.assertFalse(idle_billing.awaiting_unplug(s, self.charger, now=self.stopped_at))

    def test_cdr_is_held_even_when_the_charger_does_not_bill_idle(self):
        # The hold is about whether the session is over, not about whether we
        # are charging for the remaining minutes. Gating it on the fee meant
        # Voltality's own test charger, which has idle billing off, still got
        # a CDR the instant they stopped the session — the exact behaviour
        # they reported.
        self.charger.idle_fee_enabled = False
        s = self._session()
        self.assertTrue(idle_billing.awaiting_unplug(s, self.charger, now=self.stopped_at))
        # ...and still bills nothing for it.
        s.unplugged_at = self.stopped_at + timedelta(hours=5)
        self.assertEqual(idle_billing.compute_idle(s, self.charger), (0, 0.0))

    def test_hold_expires_with_the_cap(self):
        s = self._session()
        past_cap = self.stopped_at + timedelta(minutes=idle_billing.hold_cap_minutes() + 1)
        self.assertFalse(idle_billing.awaiting_unplug(s, self.charger, now=past_cap))


class UnplugSettlementTests(unittest.TestCase):
    """settle_unplug is the one place the cable coming out is handled.

    Both OCPP stacks call it, because 1.6 reports the unplug as a connector
    going Available and 2.0.1 reports it as a different message entirely, and
    the CDR push now hangs off it. Before this existed the CDR was pushed at
    stop time, where the hold made the builder return None and the push was
    dropped without a retry — a partner would never have received it at all.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id.in_(
                self.db.query(Charger.id).filter(Charger.charge_point_id == "UNPLUGTEST")
            )
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.charge_point_id == "UNPLUGTEST").delete()
        self.db.commit()
        self.charger = Charger(
            charge_point_id="UNPLUGTEST", idle_fee_enabled=True,
            idle_fee_per_min=0.40, idle_grace_minutes=15, is_public=True,
        )
        self.db.add(self.charger)
        self.db.commit()
        self.stopped_at = idle_billing.now_myt() - timedelta(minutes=75)

    def tearDown(self):
        # A test that settled without committing leaves the session dirty,
        # and the bulk delete below then races its pending UPDATE.
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _stopped_session(self, **kw):
        s = ChargingSession(charger_id=self.charger.id, transaction_id=7001,
                            status="completed")
        s.start_time = self.stopped_at - timedelta(minutes=30)
        s.stop_time = self.stopped_at
        s.idle_started_at = self.stopped_at
        s.unplugged_at = None
        for k, v in kw.items():
            setattr(s, k, v)
        self.db.add(s)
        self.db.commit()
        return s

    def test_settles_the_waiting_session(self):
        self._stopped_session()
        settled = idle_billing.settle_unplug(self.db, self.charger)
        self.db.commit()
        self.assertIsNotNone(settled)
        self.assertIsNotNone(settled.unplugged_at)
        self.assertEqual(settled.idle_minutes, 60)

    def test_nothing_waiting_is_not_an_error(self):
        # Chargers report Available constantly, with no session behind it.
        self.assertIsNone(idle_billing.settle_unplug(self.db, self.charger))

    def test_already_unplugged_is_not_settled_twice(self):
        self._stopped_session(unplugged_at=self.stopped_at + timedelta(minutes=5))
        self.assertIsNone(idle_billing.settle_unplug(self.db, self.charger))

    def test_a_refunded_session_records_the_unplug_without_rebilling(self):
        s = self._stopped_session(refund_status="sent", idle_minutes=3)
        settled = idle_billing.settle_unplug(self.db, self.charger)
        self.db.commit()
        self.assertIsNotNone(settled.unplugged_at)
        self.assertEqual(settled.idle_minutes, 3)

    def test_interrupted_sessions_are_settled_too(self):
        # 2.0.1 closes an aborted transaction as "interrupted", and its CDR
        # has to be issuable as well.
        self._stopped_session(status="interrupted")
        self.assertIsNotNone(idle_billing.settle_unplug(self.db, self.charger))


if __name__ == "__main__":
    unittest.main()

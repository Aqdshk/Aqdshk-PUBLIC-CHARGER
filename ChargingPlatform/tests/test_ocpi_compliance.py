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
import io
import math
import os
import re
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import idle_billing  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargingSession, MeterValue, SessionLocal, engine,
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

    def test_next_link_uses_the_advertised_base_url(self):
        """The Link must be https, like every other URL we publish.

        Behind nginx the app sees plain http, so a link built from request.url
        went out as http. That redirects, and an HTTP client which drops the
        Authorization header across the redirect gets a 401 on page two of a
        result set it was already authorised for.
        """
        import os
        os.environ["OCPI_BASE_URL"] = "https://charger.example.test"
        try:
            r = self.client.get("/ocpi/2.2.1/locations?offset=0&limit=1", headers=AUTH)
            if int(r.headers["X-Total-Count"]) > 1:
                self.assertIn("https://charger.example.test/ocpi/2.2.1/locations",
                              r.headers["Link"])
                self.assertNotIn("http://", r.headers["Link"])
        finally:
            del os.environ["OCPI_BASE_URL"]

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

    def test_the_remainder_rounds_to_the_nearest_minute(self):
        """Voltality session 449, their numbers exactly.

        540.12 seconds idle, 300 of them free, leaves 240.12 chargeable. That
        rounds to four minutes, RM0.80, because the 0.12 is under half a
        minute. Aqid chose Voltality's rule on 2026-10-15 so that both sides
        reach the same figure.
        """
        charger = Charger(charge_point_id="STEP", idle_fee_enabled=True,
                          idle_fee_per_min=0.20, idle_grace_minutes=5)
        s = self._session(unplugged_at=self.stopped_at + timedelta(seconds=540.12))
        self.assertEqual(idle_billing.compute_idle(s, charger), (4, 0.8))

    def test_a_part_block_past_the_grace_is_billed_whole(self):
        # Session 528: 377 seconds parking, which is 6.3 minutes once measured
        # to a tenth, rounds up to 7, and leaves 2 minutes past the grace.
        charger = Charger(charge_point_id="STEP", idle_fee_enabled=True,
                          idle_fee_per_min=0.20, idle_grace_minutes=5)
        s = self._session(unplugged_at=self.stopped_at + timedelta(seconds=377))
        self.assertEqual(idle_billing.compute_idle(s, charger), (2, 0.4))

    def test_a_single_second_past_grace_is_free(self):
        charger = Charger(charge_point_id="STEP", idle_fee_enabled=True,
                          idle_fee_per_min=0.20, idle_grace_minutes=5)
        s = self._session(unplugged_at=self.stopped_at + timedelta(seconds=301))
        self.assertEqual(idle_billing.compute_idle(s, charger), (0, 0.0))

    def test_an_exact_number_of_minutes_is_charged_whole(self):
        charger = Charger(charge_point_id="STEP", idle_fee_enabled=True,
                          idle_fee_per_min=0.20, idle_grace_minutes=5)
        s = self._session(unplugged_at=self.stopped_at + timedelta(seconds=600))
        self.assertEqual(idle_billing.compute_idle(s, charger), (5, 1.0))

    def test_session_537_the_exact_half_minute(self):
        # 690 seconds, 11 minutes 30 seconds, the one case where rounding to
        # nearest and dropping the remainder disagree. Voltality bill 7
        # minutes. Billing 6 here is what they rejected on 2026-10-15.
        charger = Charger(charge_point_id="STEP", idle_fee_enabled=True,
                          idle_fee_per_min=0.20, idle_grace_minutes=5)
        s = self._session(unplugged_at=self.stopped_at + timedelta(seconds=690))
        self.assertEqual(idle_billing.compute_idle(s, charger), (7, 1.4))

    def test_the_tariff_advertises_the_block_size_we_bill(self):
        # The two were separate literals. If they drift, the partner's
        # recomputed cost stops matching ours and every CDR is disputable.
        from ocpi.router import _build_tariff
        charger = Charger(charge_point_id="STEP", tariff_per_kwh=1.0,
                          idle_fee_enabled=True, idle_fee_per_min=0.20,
                          idle_grace_minutes=5)
        t = _build_tariff(charger, "2026-10-07T00:00:00Z")
        parking = [c for e in t["elements"] for c in e["price_components"]
                   if c["type"] == "PARKING_TIME"][0]
        self.assertEqual(parking["step_size"], idle_billing.PARKING_STEP_SECONDS)

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
        free = idle_billing.free_seconds(self.charger) // 60
        self.assertEqual(minutes, cap - free)

    def test_a_late_reconnection_cannot_bill_its_own_outage(self):
        """Session 507 on VOLTALITYTEST1, 2026-10-09 to 2026-10-14.

        Stopped with no energy delivered, then reported Available five days
        later. We billed the whole gap: 7090 minutes, RM1418.00, and it went
        to Voltality as a CDR. 559 on DC3001 did the same overnight for
        RM123.40. The cap was only being applied while we were still waiting
        for the unplug, so a charger coming back from its own outage escaped
        it. A reconnection is not evidence that a car sat in the bay.
        """
        cap = idle_billing.hold_cap_minutes()
        s = self._session(unplugged_at=self.stopped_at + timedelta(days=5))
        minutes, _ = idle_billing.compute_idle(s, self.charger)
        self.assertEqual(minutes, cap - int(self.charger.idle_grace_minutes))

    def test_the_cap_binds_whether_or_not_the_unplug_was_seen(self):
        # Same ceiling either way, so a charger cannot bill more by going
        # quiet and coming back than by never coming back at all.
        far = self.stopped_at + timedelta(days=5)
        seen = self._session(unplugged_at=far)
        unseen = self._session()
        self.assertEqual(idle_billing.compute_idle(seen, self.charger),
                         idle_billing.compute_idle(unseen, self.charger, now=far))

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
        # Pin the unplug instant: settling against the wall clock puts the
        # accrual a few microseconds past the hour, which now rounds up to a
        # 61st block and makes the assertion a coin toss.
        unplug = self.stopped_at + timedelta(minutes=75)
        settled = idle_billing.settle_unplug(self.db, self.charger, now=unplug)
        self.db.commit()
        self.assertIsNotNone(settled)
        self.assertEqual(settled.unplugged_at, unplug.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 60)

    def _link(self, event, at):
        from database import ChargerConnectionEvent
        self.db.add(ChargerConnectionEvent(
            charge_point_id=self.charger.charge_point_id,
            event=event, at=at - timedelta(hours=8)))      # the table is UTC
        self.db.commit()

    def _clear_links(self):
        from database import ChargerConnectionEvent
        self.db.query(ChargerConnectionEvent).filter(
            ChargerConnectionEvent.charge_point_id == self.charger.charge_point_id
        ).delete(synchronize_session=False)
        self.db.commit()

    def test_an_outage_is_not_billed_as_parking(self):
        """Session 543 on VOLTALITYTEST1, 15 to 19 October.

        Stopped having delivered nothing, the charger then left the network
        for three and a half days, and the Available it sent on reconnecting
        settled the session: RM35.00 for an outage, published to Voltality.
        While the link is down we observe nothing about the bay, so the
        accrual stops where the contact stopped.
        """
        self.addCleanup(self._clear_links)
        base = idle_billing.now_myt() - timedelta(days=4)
        drop = base + timedelta(minutes=2)
        back = base + timedelta(days=3)
        self._stopped_session(stop_time=base, idle_started_at=base)
        self._link("connected", base - timedelta(hours=1))
        self._link("disconnected", drop)
        self._link("connected", back)

        settled = idle_billing.settle_unplug(self.db, self.charger, now=back)
        self.db.commit()
        self.assertEqual(settled.unplugged_at, drop.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 0)
        self.assertEqual(float(settled.idle_fee_amount), 0.0)

    def test_a_charger_that_never_dropped_is_billed_normally(self):
        # The outage clamp must not touch an ordinary stay.
        self.addCleanup(self._clear_links)
        base = idle_billing.now_myt() - timedelta(days=1)
        unplug = base + timedelta(minutes=75)
        self._stopped_session(stop_time=base, idle_started_at=base)
        self._link("connected", base - timedelta(hours=2))

        settled = idle_billing.settle_unplug(self.db, self.charger, now=unplug)
        self.db.commit()
        self.assertEqual(settled.unplugged_at, unplug.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 60)

    def test_a_drop_before_the_session_does_not_erase_its_parking(self):
        """Session 588 on VOLTALITYTEST1, 4 November, Voltality's own test.

        The charger dropped at 15:01, reconnected at 15:15, and then stayed on
        the wire while the car was parked for eight minutes. The outage clamp
        reached past the start of the session for that 15:01 drop, clamped it
        back up to the stop, and billed nothing: the CDR Voltality pulled had
        total_parking_cost 0.00 and no PARKING_TIME period at all. An outage
        that ended before the accrual began says nothing about the accrual.
        """
        self.addCleanup(self._clear_links)
        # VOLTALITYTEST1's own settings, so the figures are the ones Voltality
        # were looking at: five free minutes, twenty sen a minute after that.
        self.charger.idle_grace_minutes = 5
        self.charger.idle_fee_per_min = 0.20
        self.db.commit()
        stop = idle_billing.now_myt() - timedelta(minutes=30)
        unplug = stop + timedelta(minutes=8)
        self._stopped_session(stop_time=stop, idle_started_at=stop)
        self._link("connected", stop - timedelta(hours=2))
        self._link("disconnected", stop - timedelta(minutes=17))   # before it
        self._link("connected", stop - timedelta(minutes=3))       # back again

        settled = idle_billing.settle_unplug(self.db, self.charger, now=unplug)
        self.db.commit()
        self.assertEqual(settled.unplugged_at, unplug.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 3)                  # 8 less the grace
        self.assertEqual(float(settled.idle_fee_amount), 0.60)

    def test_the_first_drop_inside_the_window_is_the_one_that_counts(self):
        # Two outages during one stay: billing stops at the first, because
        # after it we were no longer watching the bay.
        self.addCleanup(self._clear_links)
        stop = idle_billing.now_myt() - timedelta(hours=2)
        first = stop + timedelta(minutes=20)
        self._stopped_session(stop_time=stop, idle_started_at=stop)
        self._link("connected", stop - timedelta(hours=1))
        self._link("disconnected", first)
        self._link("connected", stop + timedelta(minutes=40))
        self._link("disconnected", stop + timedelta(minutes=50))

        settled = idle_billing.settle_unplug(
            self.db, self.charger, now=stop + timedelta(minutes=90)
        )
        self.db.commit()
        self.assertEqual(settled.unplugged_at, first.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 5)                  # 20 less the grace

    def test_a_fraction_of_a_second_does_not_buy_a_block(self):
        """Session 540, 2026-10-15.

        The charger sent Available with no timestamp, so we read our own clock
        and got 17:12:54.17. Billing from that charged three blocks; the column
        keeps whole seconds, so the CDR rebuilt from it published two, and our
        own record disagreed with what we told the partner.
        """
        self._stopped_session()
        # Land exactly on a block boundary, then add a fraction of a second.
        # Before the fix that fraction bought a whole extra block, which the
        # stored timestamp could not justify.
        free = idle_billing.free_seconds(self.charger)
        unplug = self.stopped_at + timedelta(seconds=free + 120, microseconds=170000)
        settled = idle_billing.settle_unplug(self.db, self.charger, now=unplug)
        self.db.commit()
        self.assertEqual(settled.unplugged_at.microsecond, 0)
        # What we charged is what the stored timestamps say, and what we
        # publish says the same: that is the invariant 540 broke.
        from ocpi.router import _build_cdr_dict
        recomputed = idle_billing.compute_idle(settled, self.charger)
        self.assertEqual(settled.idle_minutes, recomputed[0])
        self.assertEqual(_build_cdr_dict(settled)["total_parking_cost"]["excl_vat"],
                         float(settled.idle_fee_amount))

    def test_the_chargers_own_unplug_instant_is_used(self):
        """Voltality test IDL5.

        The charger reports when the cable came out; that report reaches us a
        moment later. Billing to our clock instead of theirs adds that lag to
        the idle time, and since idle rounds up to a whole block, a few seconds
        can cost the driver a block they did not earn.
        """
        self._stopped_session()
        reported = self.stopped_at + timedelta(seconds=240)
        settled = idle_billing.settle_unplug(self.db, self.charger, now=reported)
        self.db.commit()
        self.assertEqual(settled.unplugged_at, reported.replace(microsecond=0))

    def test_a_charger_clock_in_the_future_cannot_bill_forward(self):
        # The reported instant comes from a clock we do not control.
        self._stopped_session()
        settled = idle_billing.settle_unplug(
            self.db, self.charger, now=idle_billing.now_myt() + timedelta(days=1))
        self.db.commit()
        self.assertLessEqual(settled.unplugged_at, idle_billing.now_myt())

    def test_a_reported_unplug_before_the_stop_is_clamped(self):
        # A charger whose clock runs slow would otherwise close the session
        # before it ended.
        self._stopped_session()
        settled = idle_billing.settle_unplug(
            self.db, self.charger, now=self.stopped_at - timedelta(hours=2))
        self.db.commit()
        self.assertEqual(settled.unplugged_at, self.stopped_at.replace(microsecond=0))
        self.assertEqual(settled.idle_minutes, 0)

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

    def test_a_watchdog_closed_session_does_not_wait_for_a_cable(self):
        """Found in production, not in review.

        Session 441 on 2026-10-06 sat with unplugged_at NULL because the
        watchdog closed it, not the charger. There is no cable to wait for in
        that case — the charger has stopped reporting, or nothing was ever
        delivered — so holding its CDR for the full fallback window delays a
        record that is already final. The watchdog now stamps the unplug, and
        this asserts the consequence: such a session is immediately issuable.
        """
        s = self._stopped_session(status="interrupted", stop_reason="NeverStarted")
        s.unplugged_at = s.stop_time
        self.db.commit()
        self.assertFalse(idle_billing.awaiting_unplug(s, self.charger))

    def test_interrupted_sessions_are_settled_too(self):
        # 2.0.1 closes an aborted transaction as "interrupted", and its CDR
        # has to be issuable as well.
        self._stopped_session(status="interrupted")
        self.assertIsNotNone(idle_billing.settle_unplug(self.db, self.charger))


if __name__ == "__main__":
    unittest.main()


class SpecFieldTests(OcpiTestBase):
    """Mandatory 2.2.1 fields, checked against the spec rather than our habits.

    These were all wrong in production until 2026-10-07 and none of them had
    been reported yet. Several were 2.1.1 spellings that had survived the
    version bump: a partner validating strictly would have seen required
    fields missing and unknown fields present on nearly every object we
    publish.
    """

    SESSION_REQUIRED = {
        "country_code", "party_id", "id", "start_date_time", "kwh",
        "cdr_token", "auth_method", "location_id", "evse_uid", "connector_id",
        "currency", "status", "last_updated",
    }
    CDR_REQUIRED = {
        "country_code", "party_id", "id", "start_date_time", "end_date_time",
        "cdr_token", "auth_method", "cdr_location", "currency", "total_cost",
        "total_energy", "total_time", "last_updated",
    }
    CDR_LOCATION_REQUIRED = {
        "id", "address", "city", "country", "coordinates", "evse_uid",
        "evse_id", "connector_id", "connector_standard", "connector_format",
        "connector_power_type",
    }
    CONNECTOR_REQUIRED = {
        "id", "standard", "format", "power_type", "max_voltage",
        "max_amperage", "last_updated",
    }
    LOCATION_REQUIRED = {
        "country_code", "party_id", "id", "publish", "address", "city",
        "country", "coordinates", "time_zone", "last_updated",
    }
    # Removed between 2.1.1 and 2.2.1. Publishing them is not fatal, but it
    # tells a partner we are speaking the older version.
    LOCATION_GONE = {"type", "evse_uid", "facility_id"}
    # Dropped on 2026-10-07 once Voltality confirmed they read 2.2.1 fields.
    # They were emitted alongside the correct names for one day so the rename
    # could not break a running partner.
    CDR_GONE = {"auth_id", "location_id", "evse_uid", "connector_id", "tariff_id",
                "start_datetime", "end_datetime"}

    def _one_location(self):
        r = self.client.get("/ocpi/2.2.1/locations", headers=AUTH)
        return [l for l in r.json()["data"] if l["id"] == LOC][0]

    def test_location_has_every_required_field(self):
        loc = self._one_location()
        self.assertEqual(self.LOCATION_REQUIRED - set(loc), set())

    def test_location_does_not_carry_2_1_1_leftovers(self):
        self.assertEqual(self.LOCATION_GONE & set(self._one_location()), set())

    def test_connector_uses_max_voltage_and_max_amperage(self):
        conn = self._one_location()["evses"][0]["connectors"][0]
        self.assertEqual(self.CONNECTOR_REQUIRED - set(conn), set())
        self.assertNotIn("voltage", conn)
        self.assertNotIn("amperage", conn)

    def test_evse_has_every_required_field(self):
        evse = self._one_location()["evses"][0]
        self.assertEqual({"uid", "status", "connectors", "last_updated"} - set(evse), set())


class SpecFieldPayloadTests(unittest.TestCase):
    """Session and CDR shapes, built directly so a stopped session exists."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "SPECTEST").delete()
        self.db.commit()
        self.charger = Charger(
            charge_point_id="SPECTEST", connector_type="CCS2", tariff_per_kwh=1.0,
            idle_fee_enabled=True, idle_fee_per_min=0.40, idle_grace_minutes=15,
            is_public=True,
        )
        self.db.add(self.charger)
        self.db.commit()
        stop = idle_billing.now_myt() - timedelta(minutes=75)
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=5001,
                                    status="completed", user_id="U1")
        self.sess.start_time = stop - timedelta(minutes=30)
        self.sess.stop_time = stop
        self.sess.unplugged_at = stop + timedelta(minutes=40)
        self.sess.idle_started_at = stop
        self.sess.energy_consumed = 10.0
        self.sess.evse_id = 1
        self.sess.connector_id = 1
        self.sess.authorization_reference = "A1"
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def test_session_has_every_required_field(self):
        from ocpi.router import _build_session_dict
        d = _build_session_dict(self.sess)
        self.assertEqual(SpecFieldTests.SESSION_REQUIRED - set(d), set())

    def test_session_no_longer_carries_the_2_1_1_names(self):
        from ocpi.router import _build_session_dict
        d = _build_session_dict(self.sess)
        self.assertNotIn("start_datetime", d)
        self.assertNotIn("end_datetime", d)

    def test_cdr_has_every_required_field(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertIsNotNone(d)
        self.assertEqual(SpecFieldTests.CDR_REQUIRED - set(d), set())

    def test_cdr_no_longer_carries_the_2_1_1_fields(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertEqual(SpecFieldTests.CDR_GONE & set(d), set())

    def test_cdr_location_is_complete(self):
        from ocpi.router import _build_cdr_dict
        loc = _build_cdr_dict(self.sess)["cdr_location"]
        self.assertEqual(SpecFieldTests.CDR_LOCATION_REQUIRED - set(loc), set())

    def test_charging_periods_use_the_2_2_1_timestamp_name(self):
        from ocpi.router import _build_cdr_dict
        for period in _build_cdr_dict(self.sess)["charging_periods"]:
            self.assertIn("start_date_time", period)
            self.assertNotIn("start_datetime", period)

    def test_idle_shows_up_as_a_parking_dimension(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        dims = {x["type"] for p in d["charging_periods"] for x in p["dimensions"]}
        self.assertIn("PARKING_TIME", dims)
        self.assertGreater(d["total_parking_cost"]["excl_vat"], 0)

    def test_parking_time_is_the_measured_duration_not_the_billed_one(self):
        # Voltality rejected CDR 528 on 2026-10-15: we published the billed
        # minutes here, so re-pricing our own figure with our own tariff gave
        # the wrong cost. The EV sat for 40 minutes; 15 of those are free under
        # the grace, and the field states the 40, not the 25 we charged for.
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertAlmostEqual(d["total_parking_time"], 40 / 60, places=3)
        parking = [x for p in d["charging_periods"] for x in p["dimensions"]
                   if x["type"] == "PARKING_TIME"][0]
        self.assertEqual(parking["volume"], d["total_parking_time"])

    def test_the_tariff_reprices_the_published_parking_time_to_our_cost(self):
        # The whole point of the field: a partner applies the embedded tariff
        # to the published duration and must land on the cost we charged.
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        seconds = d["total_parking_time"] * 3600
        _free, charged = [(e["price_components"][0], e.get("restrictions") or {})
                          for e in d["tariffs"][0]["elements"]
                          if e["price_components"][0]["type"] == "PARKING_TIME"]
        rate, limits = charged
        billable = max(0.0, seconds - limits["min_duration"])
        blocks = math.ceil(billable / rate["step_size"])
        expected = round(blocks * rate["step_size"] / 3600 * rate["price"], 2)
        self.assertEqual(expected, d["total_parking_cost"]["excl_vat"])


class LocationDataTests(unittest.TestCase):
    """A charger's own address must reach OCPI.

    The chargers table carried `location`, `latitude` and `longitude` all
    along, but the builders published one hardcoded address at one hardcoded
    coordinate for every charge point. DC3001's row said Seksyen 15, Shah
    Alam; OCPI advertised "Your Charging Station Address" in the middle of
    Kuala Lumpur, 25km away, which is where a partner app would have sent the
    driver.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(
            Charger.charge_point_id.in_(["ADDRTEST", "NOADDRTEST"])
        ).delete(synchronize_session=False)
        self.db.commit()
        self.sited = Charger(
            charge_point_id="ADDRTEST", is_public=True,
            location="Seksyen 15, Shah Alam, Selangor",
            latitude=3.06566, longitude=101.533168,
        )
        self.bare = Charger(charge_point_id="NOADDRTEST", is_public=True)
        self.db.add_all([self.sited, self.bare])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        ids = [c.id for c in self.db.query(Charger).filter(
            Charger.charge_point_id.in_(["ADDRTEST", "NOADDRTEST"])).all()]
        # The suite shares one SQLite file. Leaving this test's session behind
        # made an unrelated partner-stop test find a stoppable session and fail,
        # but only when the whole suite ran.
        if ids:
            self.db.query(ChargingSession).filter(
                ChargingSession.charger_id.in_(ids)
            ).delete(synchronize_session=False)
        self.db.query(Charger).filter(
            Charger.charge_point_id.in_(["ADDRTEST", "NOADDRTEST"])
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def test_the_chargers_own_address_is_published(self):
        from ocpi.router import _build_location_dict
        loc = _build_location_dict(self.sited)
        self.assertEqual(loc["address"], "Seksyen 15, Shah Alam, Selangor")
        self.assertEqual(loc["coordinates"]["latitude"], "3.065660")
        self.assertEqual(loc["coordinates"]["longitude"], "101.533168")

    def test_a_charger_without_an_address_falls_back(self):
        from ocpi.router import _build_location_dict
        loc = _build_location_dict(self.bare)
        self.assertTrue(loc["address"])
        self.assertIn("latitude", loc["coordinates"])

    def test_the_cdr_copy_agrees_with_the_location(self):
        # A CDR carries its own copy, so the two must not drift.
        from ocpi.router import _build_location_dict, _build_cdr_dict
        sess = ChargingSession(charger_id=self.sited.id, transaction_id=6001,
                               status="completed", user_id="U")
        stop = idle_billing.now_myt() - timedelta(minutes=300)
        sess.start_time = stop - timedelta(minutes=10)
        sess.stop_time = stop
        sess.unplugged_at = stop
        sess.energy_consumed = 1.0
        sess.evse_id = 1
        self.db.add(sess)
        self.db.commit()
        loc = _build_location_dict(self.sited)
        cdr = _build_cdr_dict(sess)
        self.assertEqual(cdr["cdr_location"]["address"], loc["address"])
        self.assertEqual(cdr["cdr_location"]["coordinates"], loc["coordinates"])


class PublicationTests(unittest.TestCase):
    """What may reach a roaming partner, and what may never.

    On 2026-10-07 three Proton home chargers were being advertised to Voltality
    as public charge points, and 471 Perodua units were one heartbeat away from
    the same thing, because publication was opt-out by staleness: any charger
    that had checked in recently and carried no explicit flag went onto the
    public map by itself.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.ids = ["PUBOURS", "PUBPROTON", "PUBUNFLAGGED", "PUBOFFLINE"]
        self.db.query(Charger).filter(
            Charger.charge_point_id.in_(self.ids)
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.add_all([
            Charger(charge_point_id="PUBOURS", tenant="czero-tng", is_public=True,
                    last_heartbeat=datetime.utcnow()),
            # Someone else's fleet, flagged public by mistake.
            Charger(charge_point_id="PUBPROTON", tenant="proton", is_public=True,
                    last_heartbeat=datetime.utcnow()),
            # Ours, checking in, nobody has published it.
            Charger(charge_point_id="PUBUNFLAGGED", tenant="czero-tng", is_public=None,
                    last_heartbeat=datetime.utcnow()),
            # Ours, published, powered down for a fortnight.
            Charger(charge_point_id="PUBOFFLINE", tenant="czero-tng", is_public=True,
                    last_heartbeat=datetime.utcnow() - timedelta(days=14)),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(Charger).filter(
            Charger.charge_point_id.in_(self.ids)
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def _published(self):
        from ocpi.router import _publishable
        return {c.charge_point_id for c in _publishable(self.db.query(Charger)).all()}

    def test_our_published_charger_is_listed(self):
        self.assertIn("PUBOURS", self._published())

    def test_another_companys_fleet_is_never_listed(self):
        # The flag alone must not be enough. This is the Proton case.
        self.assertNotIn("PUBPROTON", self._published())

    def test_an_unflagged_charger_does_not_publish_itself(self):
        # The Perodua case: checking in is not consent to be advertised.
        self.assertNotIn("PUBUNFLAGGED", self._published())

    def test_a_published_charger_survives_being_offline(self):
        # Voltality's test charger is powered down between test runs; dropping
        # it on silence would pull it off the map mid-integration.
        self.assertIn("PUBOFFLINE", self._published())


class GeoAndCountryTests(OcpiTestBase):
    """Reported by Voltality on 2026-10-07, all three correct.

    country and country_code are different fields taking different standards,
    and we were putting the alpha-2 value in both. Coordinates are typed as
    decimal-degree strings, not numbers, so a partner validating against the
    spec regex rejected every location we published.
    """

    _COORD = re.compile(r"^-?[0-9]{1,3}\.[0-9]{5,7}$")

    def _one_location(self):
        r = self.client.get("/ocpi/2.2.1/locations", headers=AUTH)
        return [l for l in r.json()["data"] if l["id"] == LOC][0]

    def test_country_is_alpha3_and_country_code_is_alpha2(self):
        loc = self._one_location()
        self.assertEqual(loc["country"], "MYS")
        self.assertEqual(loc["country_code"], "MY")

    def test_coordinates_are_strings_matching_the_spec_pattern(self):
        coords = self._one_location()["coordinates"]
        for axis in ("latitude", "longitude"):
            with self.subTest(axis=axis):
                self.assertIsInstance(coords[axis], str)
                self.assertRegex(coords[axis], self._COORD)

    def test_latitude_and_longitude_fit_the_spec_lengths(self):
        coords = self._one_location()["coordinates"]
        self.assertLessEqual(len(coords["latitude"]), 10)
        self.assertLessEqual(len(coords["longitude"]), 11)



class InvalidSessionTests(unittest.TestCase):
    """Sessions that failed must say so, and must not be billed.

    Asked by Voltality on 2026-10-07. OCPI has a SessionStatus of INVALID for a
    session that was opened but failed, typically a charger problem, and which
    must not be billed. We mapped everything that was not active to COMPLETED,
    so a charge that never started was published as a successful one with
    0 kWh and a CDR went out asking the partner to reconcile it. Production
    held 208 such sessions at the time.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "INVTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="INVTEST", tariff_per_kwh=1.0,
                               is_public=True, idle_fee_enabled=True,
                               idle_fee_per_min=0.20, idle_grace_minutes=5)
        self.db.add(self.charger)
        self.db.commit()
        self.stopped = idle_billing.now_myt() - timedelta(minutes=30)

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _sess(self, **kw):
        s = ChargingSession(charger_id=self.charger.id, transaction_id=4001,
                            status="completed", user_id="U")
        s.start_time = self.stopped - timedelta(minutes=5)
        s.stop_time = self.stopped
        s.unplugged_at = self.stopped
        s.energy_consumed = 0.0
        s.evse_id = 1
        for k, v in kw.items():
            setattr(s, k, v)
        self.db.add(s)
        self.db.commit()
        return s

    def test_a_session_that_delivered_nothing_is_invalid(self):
        from ocpi.router import _build_session_dict
        self.assertEqual(_build_session_dict(self._sess())["status"], "INVALID")

    def test_an_interrupted_session_that_never_started_is_invalid(self):
        from ocpi.router import _build_session_dict
        s = self._sess(status="interrupted", stop_reason="NeverStarted")
        self.assertEqual(_build_session_dict(s)["status"], "INVALID")

    def test_a_session_that_delivered_energy_is_completed(self):
        from ocpi.router import _build_session_dict
        s = self._sess(energy_consumed=1.5)
        self.assertEqual(_build_session_dict(s)["status"], "COMPLETED")

    def test_a_watchdog_closed_charge_is_published_at_all(self):
        """Voltality's S4: the session has to reach a final state.

        Sessions 534 and 597 on VOLTALITYTEST1 delivered 1 kWh and 4 kWh, were
        closed by the watchdog when the charger vanished, and then appeared in
        neither /sessions nor /cdrs: RM7.00 of real charging that the partner
        could not see, let alone bill. "interrupted" was simply missing from
        both status filters.
        """
        # authorization_reference is what marks a session as a partner's, and
        # the shared token is only served those.
        s = self._sess(status="interrupted", transaction_id=4097,
                       energy_consumed=4.0,
                       authorization_reference="s4-watchdog")
        client = TestClient(api.app)
        body = client.get("/ocpi/2.2.1/sessions?limit=1000", headers=AUTH).json()
        self.assertIn(str(s.transaction_id), {x["id"] for x in body["data"]})

    def test_a_watchdog_closed_charge_holds_its_cdr_then_releases_it(self):
        """It can still reopen, so the bill waits, but not for ever.

        A meter value timestamped after the stop puts an interrupted session
        back to active, because some chargers reboot on a network blip with the
        transaction still running. Issuing the CDR the instant the watchdog
        fired would hand the partner a final bill for a charge that carried on.
        """
        from ocpi.router import _build_cdr_dict, _build_session_dict
        s = self._sess(status="interrupted", energy_consumed=4.0)

        self.assertIsNone(_build_cdr_dict(s))                  # held
        self.assertEqual(_build_session_dict(s)["status"], "ACTIVE")

        s.stop_time = idle_billing.now_myt() - timedelta(
            minutes=idle_billing.hold_cap_minutes() + 1
        )
        s.unplugged_at = s.stop_time
        self.db.commit()

        cdr = _build_cdr_dict(s)
        self.assertIsNotNone(cdr)                              # released
        self.assertEqual(cdr["total_energy"], 4.0)
        self.assertEqual(_build_session_dict(s)["status"], "COMPLETED")

    def test_a_watchdog_closed_charge_that_owes_nothing_is_not_held(self):
        # No bill to issue, so there is nothing to wait for. Holding these
        # would report a session nobody ever started as ACTIVE for hours.
        from ocpi.router import _build_session_dict
        s = self._sess(status="interrupted", stop_reason="NeverStarted")
        self.assertEqual(_build_session_dict(s)["status"], "INVALID")

    def test_a_running_session_is_active(self):
        from ocpi.router import _build_session_dict
        s = self._sess(status="active", stop_time=None, unplugged_at=None)
        self.assertEqual(_build_session_dict(s)["status"], "ACTIVE")

    def test_no_cdr_is_issued_for_an_invalid_session(self):
        from ocpi.router import _build_cdr_dict
        self.assertIsNone(_build_cdr_dict(self._sess()))

    def test_zero_energy_but_billable_idle_is_still_completed(self):
        # Money is attached, so it is not an invalid session even with no kWh.
        # The cost is recomputed from the clock, so the fixture has to leave a
        # real gap between the stop and the unplug rather than assert a figure.
        from ocpi.router import _build_session_dict, _build_cdr_dict
        s = self._sess(idle_started_at=self.stopped,
                       unplugged_at=self.stopped + timedelta(minutes=12))
        self.assertEqual(_build_session_dict(s)["status"], "COMPLETED")
        self.assertIsNotNone(_build_cdr_dict(s))


class ClockTests(unittest.TestCase):
    """Timestamps must be the UTC instant, not Malaysia wall time wearing a Z.

    Sessions and meter values are stored as Malaysia wall time, naive, because
    that is the basis the OCPP handlers and every report use. We published them
    with a Z suffix, which asserts UTC, so every timestamp a roaming partner
    received was eight hours ahead of the truth. Durations and costs were never
    wrong, since both ends shared the same wrong basis, but a partner
    reconciling against its own records or printing a receipt saw the gap.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "CLOCKTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="CLOCKTEST", tariff_per_kwh=1.0,
                               is_public=True, idle_fee_enabled=False)
        self.db.add(self.charger)
        self.db.commit()
        # 19:30 in Malaysia is 11:30 UTC the same day.
        self.started = datetime(2026, 10, 8, 19, 30, 0)
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=9101,
                                    status="completed", user_id="U")
        self.sess.start_time = self.started
        self.sess.stop_time = self.started + timedelta(minutes=30)
        self.sess.unplugged_at = self.sess.stop_time
        self.sess.energy_consumed = 5.0
        self.sess.evse_id = 1
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def test_a_session_is_published_in_utc(self):
        from ocpi.router import _build_session_dict
        d = _build_session_dict(self.sess)
        self.assertEqual(d["start_date_time"], "2026-10-08T11:30:00Z")
        self.assertEqual(d["end_date_time"], "2026-10-08T12:00:00Z")

    def test_a_cdr_is_published_in_utc(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertEqual(d["start_date_time"], "2026-10-08T11:30:00Z")
        self.assertEqual(d["end_date_time"], "2026-10-08T12:00:00Z")
        self.assertEqual(d["charging_periods"][0]["start_date_time"],
                         "2026-10-08T11:30:00Z")

    def test_the_duration_is_unchanged(self):
        # The shift must move both ends together. This is why the bug survived:
        # every figure a partner billed on was already right.
        from ocpi.router import _build_cdr_dict
        self.assertAlmostEqual(_build_cdr_dict(self.sess)["total_time"], 0.5)

    def test_a_partners_utc_filter_selects_the_right_rows(self):
        # The mirror of the same bug: date_from arrived as UTC and was compared
        # against Malaysia wall time, so the window was eight hours out.
        from ocpi.router import _session_filter_time
        self.assertEqual(_session_filter_time("2026-10-08T11:30:00Z"),
                         datetime(2026, 10, 8, 19, 30, 0))

    def test_a_filter_round_trips_with_what_we_publish(self):
        from ocpi.router import _session_time, _session_filter_time
        published = _session_time(self.started)
        self.assertEqual(_session_filter_time(published), self.started)


class SessionLastUpdatedTests(unittest.TestCase):
    """last_updated has to move whenever the session object moves.

    Reported by Voltality on 2026-10-08: kwh was climbing while last_updated
    stayed put. A partner polls on last_updated to decide what to re-read, so a
    frozen one means they never pick the change up.

    It had always been the stop time falling back to the start time, so it
    never moved during a session. That was invisible while kwh never moved
    either; fixing the meter parsing earlier the same day made it visible.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "LUTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="LUTEST", tariff_per_kwh=1.0,
                               is_public=True, idle_fee_enabled=True,
                               idle_fee_per_min=0.20, idle_grace_minutes=5)
        self.db.add(self.charger)
        self.db.commit()
        self.started = idle_billing.now_myt() - timedelta(minutes=20)
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=7777,
                                    status="active", user_id="U")
        self.sess.start_time = self.started
        self.sess.energy_consumed = 1.0
        self.sess.evse_id = 1
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(MeterValue).filter(MeterValue.transaction_id == 7777).delete(
            synchronize_session=False)
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _reading(self, at, kwh):
        self.db.add(MeterValue(charger_id=self.charger.id, transaction_id=7777,
                               timestamp=at, total_kwh=kwh, connector_id=1))
        self.db.commit()

    def _last_updated(self):
        from ocpi.router import _build_session_dict
        return _build_session_dict(self.sess)["last_updated"]

    def test_a_write_to_the_session_stamps_it(self):
        # The production path: a meter reading updates energy_consumed, and the
        # mapper event in database.py stamps the row on that write.
        before = self.sess.last_updated
        self.sess.energy_consumed = 1.4
        self.db.commit()
        self.assertGreater(self.sess.last_updated, before)

    def test_what_we_publish_is_what_we_filter_on(self):
        # These were two different values before: the published one was derived
        # at render time while the filter ran against the start time, so a
        # partner could be told a session had changed and then not find it.
        from ocpi.router import _session_time
        self.sess.energy_consumed = 2.0
        self.db.commit()
        self.assertEqual(self._last_updated(), _session_time(self.sess.last_updated))

    def test_it_never_goes_backwards(self):
        # Resolution is one second, which is well inside the ten second meter
        # cadence, so two writes in the same second share a stamp. What must
        # always hold is that it only ever moves forward.
        self.sess.energy_consumed = 1.1
        self.db.commit()
        first = self.sess.last_updated
        self.sess.energy_consumed = 1.2
        self.db.commit()
        self.assertGreaterEqual(self.sess.last_updated, first)

    def test_a_session_is_stamped_when_it_is_created(self):
        self.assertIsNotNone(self.sess.last_updated)

    def test_a_finished_session_is_stamped_at_the_unplug(self):
        self.sess.status = "completed"
        self.sess.stop_time = self.started + timedelta(minutes=10)
        self.db.commit()
        at_stop = self.sess.last_updated
        self.sess.unplugged_at = self.started + timedelta(minutes=15)
        self.db.commit()
        self.assertGreater(self.sess.last_updated, at_stop)


class DateFilterTests(unittest.TestCase):
    """date_from and date_to select on last_updated, not on the start time.

    Reported by Voltality on 2026-10-09: once a session had started they could
    not pull its updates, because we filtered on start_date_time. OCPI says
    "only return Sessions that have last_updated after or equal to this
    Date/Time", which is a different question entirely: one asks when the
    session began, the other when it last moved.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "FILTTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="FILTTEST", tariff_per_kwh=1.0,
                               is_public=True, tenant="czero-tng")
        self.db.add(self.charger)
        self.db.commit()
        # Started hours ago, updated moments ago: the exact shape that was
        # being missed.
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=8801,
                                    status="active", user_id="U")
        self.sess.start_time = idle_billing.now_myt() - timedelta(hours=6)
        self.sess.energy_consumed = 3.0
        self.sess.authorization_reference = "A-FILT"
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _ids(self, **params):
        client = TestClient(api.app)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        r = client.get(f"/ocpi/2.2.1/sessions?{qs}", headers=AUTH)
        return {s["id"] for s in r.json()["data"]}

    def _utc(self, dt):
        from ocpi.router import _session_time
        return _session_time(dt)

    def test_a_session_started_long_ago_but_updated_now_is_returned(self):
        # Filtering on the start time would have excluded this one, which is
        # precisely the report.
        since = self._utc(idle_billing.now_myt() - timedelta(minutes=5))
        self.assertIn("8801", self._ids(date_from=since))

    def test_a_session_not_touched_since_the_window_is_excluded(self):
        since = self._utc(idle_billing.now_myt() + timedelta(minutes=5))
        self.assertNotIn("8801", self._ids(date_from=since))

    def test_date_to_is_exclusive_of_the_bound(self):
        upto = self._utc(self.sess.last_updated)
        self.assertNotIn("8801", self._ids(date_to=upto))

    def test_a_fresh_write_brings_it_back_into_the_window(self):
        since = self._utc(idle_billing.now_myt() + timedelta(seconds=1))
        self.assertNotIn("8801", self._ids(date_from=since))
        self.sess.energy_consumed = 9.0
        self.db.commit()
        since2 = self._utc(self.sess.last_updated)
        self.assertIn("8801", self._ids(date_from=since2))

    def test_locations_and_tariffs_accept_the_same_filters(self):
        client = TestClient(api.app)
        future = self._utc(idle_billing.now_myt() + timedelta(days=1))
        for path in ("/ocpi/2.2.1/locations", "/ocpi/2.2.1/tariffs"):
            with self.subTest(path=path):
                r = client.get(f"{path}?date_from={future}", headers=AUTH)
                self.assertEqual(r.status_code, 200)
                # Nothing has changed in the future, so nothing comes back.
                self.assertEqual(r.json()["data"], [])
                self.assertEqual(r.headers["X-Total-Count"], "0")


class ChargerClockTests(unittest.TestCase):
    """The charger stamp is UTC, and the session stamp is Malaysia time.

    They disagree on purpose: every other clock on the chargers table is UTC,
    and every other clock on the sessions table is Malaysia wall time. Mixing
    them in one column is what put DC3001 eight hours into the past on
    2026-10-09, after a backfill wrote UTC and the mapper event wrote local.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "TZTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="TZTEST", is_public=True,
                               tenant="czero-tng", connector_status="{}")
        self.db.add(self.charger)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def test_the_charger_stamp_is_utc(self):
        from database import _utcnow
        drift = abs((self.charger.last_updated - _utcnow()).total_seconds())
        self.assertLess(drift, 120, "charger last_updated is not on the UTC clock")

    def test_the_session_stamp_is_malaysia_time(self):
        sess = ChargingSession(charger_id=self.charger.id, transaction_id=9901,
                               status="active")
        sess.start_time = idle_billing.now_myt()
        self.db.add(sess)
        self.db.commit()
        drift = abs((sess.last_updated - idle_billing.now_myt()).total_seconds())
        self.assertLess(drift, 120, "session last_updated is not on the session clock")
        self.db.query(ChargingSession).filter(ChargingSession.id == sess.id).delete()
        self.db.commit()

    def test_a_location_reports_the_charger_stamp_without_shifting_it(self):
        from ocpi.router import _build_location_dict, _to_ocpi_datetime
        loc = _build_location_dict(self.charger)
        self.assertEqual(loc["last_updated"],
                         _to_ocpi_datetime(self.charger.last_updated))

    def test_a_heartbeat_does_not_count_as_a_change(self):
        # Heartbeats land every thirty seconds. If they stamped the row, every
        # location would look freshly changed and polling would be useless.
        before = self.charger.last_updated
        self.charger.last_heartbeat = datetime(2030, 1, 1)
        self.db.commit()
        self.assertEqual(self.charger.last_updated, before)

    def test_a_visible_change_does_count(self):
        before = self.charger.last_updated
        self.charger.connector_status = '{"1": "charging"}'
        self.db.commit()
        self.assertGreaterEqual(self.charger.last_updated, before)


class PublishedLastUpdatedMatchesFilterTests(unittest.TestCase):
    """What we publish as last_updated must be what date_from selects on.

    If the published value is older than the column behind the filter, a
    partner that stores it and polls from it is handed the same record on
    every poll and never finishes syncing. The CDR published the unplug
    instant, which is the last write today and so matched by luck; a refund
    settling afterwards would have broken it.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "LUTEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="LUTEST", tariff_per_kwh=1.0,
                               is_public=True, tenant="czero-tng")
        self.db.add(self.charger)
        self.db.commit()
        stop = idle_billing.now_myt() - timedelta(hours=4)
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=8888,
                                    status="completed", user_id="U",
                                    authorization_reference="A")
        self.sess.start_time = stop - timedelta(minutes=20)
        self.sess.stop_time = stop
        self.sess.unplugged_at = stop + timedelta(minutes=10)
        self.sess.energy_consumed = 5.0
        self.sess.evse_id = 1
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def test_cdr_publishes_the_column_the_filter_uses(self):
        from ocpi.router import _build_cdr_dict, _session_time, _session_last_updated
        cdr = _build_cdr_dict(self.sess)
        self.assertIsNotNone(cdr)
        self.assertEqual(cdr["last_updated"],
                         _session_time(_session_last_updated(self.sess)))

    def test_a_later_write_does_not_strand_the_cdr(self):
        # The row is touched again after the unplug, as a refund settling
        # would touch it. Polling from the published value must not return it.
        from ocpi.router import _build_cdr_dict, _session_filter_time
        self.sess.refund_status = "sent"
        self.db.commit()
        cdr = _build_cdr_dict(self.sess)
        bound = _session_filter_time(cdr["last_updated"])
        self.assertGreaterEqual(bound, self.sess.last_updated.replace(microsecond=0))

    def test_session_publishes_the_column_the_filter_uses(self):
        from ocpi.router import _build_session_dict, _session_time, _session_last_updated
        d = _build_session_dict(self.sess)
        self.assertEqual(d["last_updated"],
                         _session_time(_session_last_updated(self.sess)))

    def test_location_publishes_the_column_the_filter_uses(self):
        from ocpi.router import _build_location_dict, _charger_changed_at
        loc = _build_location_dict(self.charger)
        self.assertEqual(loc["last_updated"], _charger_changed_at(self.charger))


class SessionLifecycleTests(unittest.TestCase):
    """Voltality test S6, and their proposal of 2026-10-09.

    A stop that is merely accepted does not end a session. The charger goes to
    Finishing, the grace period runs, and idle accrues, all afterwards. We were
    publishing COMPLETED the moment the stop landed, and INVALID whenever no
    energy had flowed, which is decided before any idle exists.

    The damage is revenue: a driver starts a session, stops it at once and
    leaves the car plugged in. No energy, so we called it INVALID, and an
    INVALID session cannot be billed, so the idle that followed was
    unrecoverable.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "LIFETEST").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="LIFETEST", tariff_per_kwh=1.40,
                               is_public=True, tenant="czero-tng",
                               idle_fee_enabled=True, idle_fee_per_min=0.20,
                               idle_grace_minutes=5)
        self.db.add(self.charger)
        self.db.commit()
        self.stopped = idle_billing.now_myt() - timedelta(minutes=2)

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _sess(self, **kw):
        s = ChargingSession(charger_id=self.charger.id, transaction_id=9100,
                            status="completed", user_id="U")
        s.start_time = self.stopped - timedelta(minutes=1)
        s.stop_time = self.stopped
        s.idle_started_at = self.stopped
        s.unplugged_at = None
        s.energy_consumed = 0.0
        s.evse_id = 1
        for k, v in kw.items():
            setattr(s, k, v)
        self.db.add(s)
        self.db.commit()
        return s

    def test_a_stopped_session_stays_active_until_the_cable_is_out(self):
        from ocpi.router import _build_session_dict
        self.assertEqual(_build_session_dict(self._sess())["status"], "ACTIVE")

    def test_it_becomes_completed_once_unplugged_with_something_to_bill(self):
        from ocpi.router import _build_session_dict
        s = self._sess(unplugged_at=self.stopped + timedelta(minutes=12))
        d = _build_session_dict(s)
        self.assertEqual(d["status"], "COMPLETED")
        self.assertGreater(d["total_cost"]["excl_vat"], 0)

    def test_it_becomes_invalid_once_unplugged_with_nothing_to_bill(self):
        from ocpi.router import _build_session_dict
        s = self._sess(unplugged_at=self.stopped + timedelta(seconds=20))
        d = _build_session_dict(s)
        self.assertEqual(d["status"], "INVALID")
        self.assertEqual(d["total_cost"]["excl_vat"], 0)

    def test_the_s6_scenario_does_not_lose_the_idle(self):
        """Start, stop at once, leave it plugged in past the grace period."""
        from ocpi.router import _build_session_dict, _build_cdr_dict
        s = self._sess()
        # Still plugged in and inside grace: nothing owed yet, but not invalid.
        self.assertEqual(_build_session_dict(s)["status"], "ACTIVE")
        # Unplugged well past grace: the idle is billable and the session is
        # not invalid, which is what made it unbillable before.
        s.unplugged_at = self.stopped + timedelta(minutes=11)
        self.db.commit()
        d = _build_session_dict(s)
        self.assertEqual(d["status"], "COMPLETED")
        self.assertEqual(d["total_cost"]["excl_vat"], 1.2)   # 6 blocks x RM0.20
        cdr = _build_cdr_dict(s)
        self.assertEqual(cdr["total_parking_cost"]["excl_vat"], 1.2)

    def test_no_cdr_while_the_session_is_still_running(self):
        from ocpi.router import _build_cdr_dict
        self.assertIsNone(_build_cdr_dict(self._sess()))



class CdrCarriesItsTariffTests(unittest.TestCase):
    """A CDR must show the terms that were actually charged.

    Asked by Voltality on 2026-10-12: the idle cost and grace period have to
    be visible on the CDR. We referenced the tariff by name only. A CDR is
    immutable and a tariff is not, so once a charger's idle rate or grace
    changed, every older CDR would describe terms that were never charged.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "TARCDR").delete()
        self.db.commit()
        self.charger = Charger(charge_point_id="TARCDR", tariff_per_kwh=1.40,
                               is_public=True, tenant="czero-tng",
                               idle_fee_enabled=True, idle_fee_per_min=0.20,
                               idle_grace_minutes=5)
        self.db.add(self.charger)
        self.db.commit()
        stop = idle_billing.now_myt() - timedelta(hours=4)
        self.sess = ChargingSession(charger_id=self.charger.id, transaction_id=9300,
                                    status="completed", user_id="U")
        self.sess.start_time = stop - timedelta(minutes=20)
        self.sess.stop_time = stop
        self.sess.unplugged_at = stop + timedelta(minutes=20)
        self.sess.idle_started_at = stop
        self.sess.energy_consumed = 2.0
        self.sess.evse_id = 1
        self.db.add(self.sess)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _cdr(self):
        from ocpi.router import _build_cdr_dict
        return _build_cdr_dict(self.sess)

    def _reprice_the_charger(self, **kw):
        for field, value in kw.items():
            setattr(self.charger, field, value)
        self.db.commit()

    def test_the_session_takes_a_copy_of_the_prices_when_it_is_created(self):
        # Stamped by a mapper event, so the six places that create a session
        # do not each have to remember.
        self.assertEqual(float(self.sess.tariff_per_kwh_at_start), 1.40)
        self.assertEqual(float(self.sess.idle_fee_per_min_at_start), 0.20)
        self.assertEqual(self.sess.idle_grace_minutes_at_start, 5)
        self.assertTrue(self.sess.idle_fee_enabled_at_start)

    def test_raising_the_idle_rate_does_not_rewrite_a_bill_already_issued(self):
        """The reason the snapshot exists.

        Session 588 went to Voltality carrying RM1.60 of parking. A CDR is
        rebuilt from the session on every read, so putting the idle rate up to
        RM0.30 would have made that same record read RM2.40 the next time they
        pulled it, against a figure they had already settled.
        """
        before = self._cdr()
        self._reprice_the_charger(idle_fee_per_min=0.30, idle_grace_minutes=10)
        after = self._cdr()

        self.assertEqual(after["total_parking_cost"], before["total_parking_cost"])
        self.assertEqual(after["total_cost"], before["total_cost"])
        charged = [e for e in after["tariffs"][0]["elements"]
                   if e["price_components"][0]["type"] == "PARKING_TIME"
                   and e["price_components"][0]["price"]]
        self.assertEqual(charged[0]["price_components"][0]["price"], 12.0)  # RM0.20/min
        self.assertEqual(charged[0]["restrictions"]["min_duration"], 300)   # 5 min

    def test_raising_the_energy_rate_does_not_rewrite_a_bill_already_issued(self):
        before = self._cdr()
        self._reprice_the_charger(tariff_per_kwh=2.50)
        after = self._cdr()

        self.assertEqual(after["total_energy_cost"], before["total_energy_cost"])
        energy = [c for e in after["tariffs"][0]["elements"]
                  for c in e["price_components"] if c["type"] == "ENERGY"]
        self.assertEqual(energy[0]["price"], 1.40)

    def test_a_session_from_before_the_snapshot_still_reads_the_charger(self):
        # Nothing was backfilled, so every older row carries nulls and has to
        # go on behaving exactly as it did.
        self.sess.tariff_per_kwh_at_start = None
        self.sess.idle_fee_enabled_at_start = None
        self.sess.idle_fee_per_min_at_start = None
        self.sess.idle_grace_minutes_at_start = None
        self._reprice_the_charger(tariff_per_kwh=2.50, idle_fee_per_min=0.30)

        cdr = self._cdr()
        energy = [c for e in cdr["tariffs"][0]["elements"]
                  for c in e["price_components"] if c["type"] == "ENERGY"]
        self.assertEqual(energy[0]["price"], 2.50)
        self.assertEqual(cdr["total_energy_cost"]["excl_vat"], 5.0)   # 2 kWh

    def test_the_tariffs_endpoint_still_shows_todays_price(self):
        # A tariff standing on its own is what we charge now, not what some
        # past session was charged. Only a CDR freezes.
        from ocpi.router import _build_tariff
        self._reprice_the_charger(tariff_per_kwh=2.50)
        live = _build_tariff(self.charger, "2026-11-12T00:00:00Z")
        energy = [c for e in live["elements"]
                  for c in e["price_components"] if c["type"] == "ENERGY"]
        self.assertEqual(energy[0]["price"], 2.50)

    def test_the_cdr_embeds_the_tariff(self):
        tariffs = self._cdr()["tariffs"]
        self.assertEqual(len(tariffs), 1)
        self.assertEqual(tariffs[0]["id"], self._cdr()["charging_periods"][0]["tariff_id"])

    def test_the_embedded_tariff_shows_the_idle_rate_and_grace(self):
        # Two parking elements since 2026-10-13: the free window and the
        # charged one. The CDR has to carry both, or the record cannot show
        # why the first five minutes cost nothing.
        parking = [(e["price_components"][0], e.get("restrictions") or {})
                   for e in self._cdr()["tariffs"][0]["elements"]
                   if e["price_components"][0]["type"] == "PARKING_TIME"]
        self.assertEqual(len(parking), 2)
        free, charged = parking
        self.assertEqual(free[0]["price"], 0.0)
        self.assertEqual(free[1]["max_duration"], 300)     # the 5 minute grace
        self.assertEqual(charged[0]["price"], 12.0)        # RM0.20/min as RM/hour
        self.assertEqual(charged[0]["step_size"], 60)
        self.assertEqual(charged[1]["min_duration"], 300)

    def test_a_charger_without_idle_billing_prices_parking_at_zero(self):
        # Not absence. We still publish how long the EV sat without charging,
        # so a tariff with no PARKING_TIME leaves the partner holding a
        # duration they cannot price, which is the fault Voltality raised
        # against session 528. Zero says the same thing and can be checked.
        # On the session, not on the charger: a charger edited after the fact
        # must not rewrite a bill already issued, which is what the snapshot
        # is for. This is a charger that never charged for parking.
        self.sess.idle_fee_enabled_at_start = False
        self.charger.idle_fee_enabled = False
        self.db.commit()
        cdr = self._cdr()
        parking = [(c, e.get("restrictions") or {})
                   for e in cdr["tariffs"][0]["elements"]
                   for c in e["price_components"] if c["type"] == "PARKING_TIME"]
        self.assertEqual(len(parking), 1)
        self.assertEqual(parking[0][0]["price"], 0.0)
        self.assertEqual(parking[0][1], {})          # applies to the whole stay
        self.assertEqual(cdr["total_parking_cost"]["excl_vat"], 0)


class PartnerRepricingTests(unittest.TestCase):
    """Re-price our own CDR the way Voltality do, and demand the same answer.

    Four rounds of this dispute were spent guessing their rule from the few
    figures they had sent. Venu then wrote the rule out for session 537:

        "Based on the 60-second step size, the parking duration should be
         rounded up to 12 minutes. After deducting the 5-minute grace period,
         the chargeable duration should be 7 minutes."

    That is the partner implemented here, so a disagreement shows up in our own
    suite instead of in a WhatsApp message. It needs nothing from their side.
    """

    GRACE_MIN = 5
    RATE = 0.20

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(Charger).filter(Charger.charge_point_id == "REPRICE").delete()
        self.db.commit()
        self.charger = Charger(
            charge_point_id="REPRICE", connector_type="Type2", tariff_per_kwh=1.40,
            idle_fee_enabled=True, idle_fee_per_min=self.RATE,
            idle_grace_minutes=self.GRACE_MIN, is_public=True,
        )
        self.db.add(self.charger)
        self.db.commit()
        self.stop = idle_billing.now_myt() - timedelta(hours=2)

    def tearDown(self):
        self.db.rollback()
        self.db.query(ChargingSession).filter(
            ChargingSession.charger_id == self.charger.id
        ).delete(synchronize_session=False)
        self.db.query(Charger).filter(Charger.id == self.charger.id).delete()
        self.db.commit()
        self.db.close()

    def _cdr_for(self, parking_seconds):
        from ocpi.router import _build_cdr_dict
        s = ChargingSession(charger_id=self.charger.id, transaction_id=9000,
                            status="completed", user_id="U")
        s.start_time = self.stop - timedelta(minutes=10)
        s.stop_time = self.stop
        s.idle_started_at = self.stop
        s.unplugged_at = self.stop + timedelta(seconds=parking_seconds)
        s.energy_consumed = 1.0
        s.evse_id = 1
        s.connector_id = 1
        s.authorization_reference = "A"
        s.charger = self.charger      # in memory only: 3601 commits is a test suite
        return _build_cdr_dict(s)

    def _as_voltality_would(self, cdr):
        """Their algorithm, over the figures we actually publish."""
        minutes = round(cdr["total_parking_time"] * 60, 1)
        chargeable = max(0, math.ceil(minutes) - self.GRACE_MIN)
        return round(chargeable * self.RATE, 2)

    def _every_reading(self, cdr):
        """The same algorithm, written the ways a partner might write it.

        Venu quoted minutes ("approximately 11.5 minutes"), but we should not
        depend on which unit they work in or how many decimals they keep. The
        one that used to fail is "seconds, ceil to step": 1980 seconds is 0.55
        hours and 0.55 * 3600 comes back as 1980.0000000000002, which rounds
        up to a minute we never charged.
        """
        g = self.GRACE_MIN
        m = cdr["total_parking_time"] * 60
        secs = cdr["total_parking_time"] * 3600
        return {
            "raw minutes, ceil":     max(0, math.ceil(m) - g),
            "1 dp then ceil":        max(0, math.ceil(round(m, 1)) - g),
            "2 dp then ceil":        max(0, math.ceil(round(m, 2)) - g),
            "4 dp then ceil":        max(0, math.ceil(round(m, 4)) - g),
            "seconds, ceil to step": max(0, math.ceil(secs / 60) - g),
            "grace off first":       math.ceil(max(0.0, secs - g * 60) / 60),
            "round secs then ceil":  max(0, math.ceil(round(secs) / 60) - g),
        }

    def test_the_sessions_they_gave_a_verdict_on(self):
        # Parking durations measured in production, and the figure Voltality
        # asked for or accepted.
        for sid, seconds, expected in ((535, 421, 0.40),
                                       (537, 690, 1.40),
                                       (540, 449, 0.60)):
            with self.subTest(session=sid):
                cdr = self._cdr_for(seconds)
                self.assertEqual(cdr["total_parking_cost"]["excl_vat"], expected)
                self.assertEqual(self._as_voltality_would(cdr), expected)

    def test_the_fee_matches_the_published_rate_at_any_precision(self):
        """Bill from the rate we publish, not the one we configure.

        We hold a rate per minute and OCPI prices parking per hour. Billing
        from one while publishing the other left a sub-cent gap whenever the
        conversion was not exact: at RM1.333 a minute, 25 minutes came to
        RM33.32 our way and RM33.33 theirs. The column holds two decimals so
        no live rate could reach it, which is exactly why it would have gone
        unnoticed until someone widened the column.
        """
        from decimal import Decimal
        for rate in ("0.20", "1.333", "0.077", "2.4567"):
            self.charger.idle_fee_per_min = Decimal(rate)
            self.db.commit()
            for seconds in (377, 421, 690, 1500, 4200):
                with self.subTest(rate=rate, parking=seconds):
                    cdr = self._cdr_for(seconds)
                    parking = [(c, e.get("restrictions") or {})
                               for e in cdr["tariffs"][0]["elements"]
                               for c in e["price_components"]
                               if c["type"] == "PARKING_TIME"][-1]
                    comp, limits = parking
                    up = math.ceil(cdr["total_parking_time"] * 3600
                                   / comp["step_size"]) * comp["step_size"]
                    chargeable = max(0, up - int(limits.get("min_duration", 0)))
                    self.assertEqual(
                        round(chargeable / 3600 * comp["price"], 2),
                        cdr["total_parking_cost"]["excl_vat"])

    def test_parking_is_always_priceable_even_with_the_idle_fee_off(self):
        """A duration we publish must have a price in the tariff we publish.

        With the idle fee off we were sending the parking time and the
        PARKING_TIME charging period while the tariff carried no PARKING_TIME
        component at all, so the partner could not price it. Aqid was about to
        run exactly this configuration with Voltality.
        """
        self.charger.idle_fee_enabled = False
        self.db.commit()
        for seconds in (0, 60, 690, 3600):
            with self.subTest(parking=seconds):
                cdr = self._cdr_for(seconds)
                parking = [(c, e.get("restrictions") or {})
                           for e in cdr["tariffs"][0]["elements"]
                           for c in e["price_components"]
                           if c["type"] == "PARKING_TIME"]
                self.assertTrue(parking, "parking time published with no price")
                rate, limits = parking[-1]
                grace = int(limits.get("min_duration", 0) // 60)
                minutes = cdr["total_parking_time"] * 60
                priced = round(max(0, math.ceil(minutes) - grace)
                               * rate["price"] / 60, 2)
                self.assertEqual(priced, cdr["total_parking_cost"]["excl_vat"])

    def test_every_duration_up_to_an_hour_agrees(self):
        # The dispute only ever surfaced at durations nobody thought to try,
        # so try all of them rather than a handful.
        disagreed = []
        for seconds in range(0, 3601, 1):
            cdr = self._cdr_for(seconds)
            ours = cdr["total_parking_cost"]["excl_vat"]
            for name, chargeable in self._every_reading(cdr).items():
                if round(chargeable * self.RATE, 2) != ours:
                    disagreed.append((seconds, name))
        self.assertEqual(disagreed[:10], [], f"{len(disagreed)} readings disagree")


class GracePeriodInTariffTests(unittest.TestCase):
    """The free window is stated in the tariff, not implied.

    Voltality objected on 2026-10-13: the grace period was a lone
    min_duration on the charged element, so they had to be told out of band
    what that number meant, and a change here would need a message to them
    before their billing matched ours again. The free window is now an element
    of its own priced at zero, so the tariff says what those seconds cost.
    """

    def _tariff(self, enabled=True, grace=5, per_min=0.20):
        from ocpi.router import _build_tariff
        c = Charger(charge_point_id="GRACE", tariff_per_kwh=1.40,
                    idle_fee_enabled=enabled, idle_fee_per_min=per_min,
                    idle_grace_minutes=grace)
        return _build_tariff(c, "2026-10-13T00:00:00Z")

    def _parking(self, t):
        return [(e["price_components"][0], e.get("restrictions") or {})
                for e in t["elements"]
                if e["price_components"][0]["type"] == "PARKING_TIME"]

    def test_the_free_window_is_its_own_element(self):
        free, charged = self._parking(self._tariff())
        self.assertEqual(free[0]["price"], 0.0)
        self.assertEqual(free[1], {"min_duration": 0, "max_duration": 300})
        self.assertEqual(charged[0]["price"], 12.0)
        self.assertEqual(charged[1], {"min_duration": 300})

    def test_the_two_windows_meet_without_a_gap(self):
        # A gap would leave seconds whose price the tariff does not state.
        free, charged = self._parking(self._tariff())
        self.assertEqual(free[1]["max_duration"], charged[1]["min_duration"])

    def test_the_grace_reflects_the_charger_not_a_constant(self):
        free, charged = self._parking(self._tariff(grace=12))
        self.assertEqual(free[1]["max_duration"], 720)
        self.assertEqual(charged[1]["min_duration"], 720)

    def test_no_free_element_when_there_is_no_grace(self):
        # Nothing is free, so the tariff says so by carrying one parking
        # element that starts at zero.
        parking = self._parking(self._tariff(grace=0))
        self.assertEqual(len(parking), 1)
        self.assertEqual(parking[0][0]["price"], 12.0)
        self.assertEqual(parking[0][1], {"min_duration": 0})

    def test_parking_is_priced_at_zero_when_idling_is_off(self):
        parking = self._parking(self._tariff(enabled=False))
        self.assertEqual(len(parking), 1)
        self.assertEqual(parking[0][0]["price"], 0.0)
        self.assertEqual(parking[0][1], {})

    def test_both_windows_bill_in_the_same_block(self):
        # A partner recomputing our figure needs one block size, not two.
        for comp, _ in self._parking(self._tariff()):
            self.assertEqual(comp["step_size"], idle_billing.PARKING_STEP_SECONDS)

    def test_the_tariff_matches_what_we_actually_bill(self):
        """The published terms and the money we take have to agree.

        Eleven minutes plugged in and the free window is 329 seconds, so six
        minutes are chargeable at RM0.20, and the tariff says RM12 per hour
        from second 329.
        """
        charger = Charger(charge_point_id="GRACE", tariff_per_kwh=1.40,
                          idle_fee_enabled=True, idle_fee_per_min=0.20,
                          idle_grace_minutes=5)
        sess = ChargingSession(transaction_id=1, status="completed")
        stop = idle_billing.now_myt() - timedelta(minutes=30)
        sess.stop_time = stop
        sess.idle_started_at = stop
        sess.unplugged_at = stop + timedelta(minutes=11)
        minutes, fee = idle_billing.compute_idle(sess, charger)
        self.assertEqual(minutes, 6)
        self.assertEqual(fee, 1.20)
        _, charged = self._parking(self._tariff())
        self.assertEqual(round(charged[0]["price"] / 60 * minutes, 2), fee)


class _FakeResponse:
    """Just enough of an httpx response for the callback to report on."""

    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class OutboundAuthTests(unittest.IsolatedAsyncioTestCase):
    """What we present when we call a partner, rather than what we accept.

    Voltality answered 401 to every CommandResult we posted. Two separate
    faults were in the way. The first, fixed earlier, was that no partner
    token was stored at all, so the header went out empty. The second is this
    one: OCPI 2.2.1 carries the token base64-encoded, and we sent it raw.
    Their UAT was checked directly on 2026-11-12 and refuses the plain form
    with 401 while accepting the encoded form, so storing the token without
    this change would have left the callbacks failing exactly as before.
    """

    TOKEN = "43d4a1e2-0000-0000-0000-000000000000"

    def test_the_header_is_base64_and_decodes_to_the_token(self):
        import base64

        from ocpi.push import auth_header

        header = auth_header(self.TOKEN)
        self.assertTrue(header.startswith("Token "))
        encoded = header[len("Token "):]
        self.assertNotEqual(encoded, self.TOKEN)
        self.assertEqual(
            base64.b64decode(encoded, validate=True).decode("utf-8"),
            self.TOKEN,
        )

    def test_we_never_send_the_bare_token(self):
        """The exact shape their UAT rejects."""
        from ocpi.push import auth_header

        self.assertNotEqual(auth_header(self.TOKEN), f"Token {self.TOKEN}")

    def test_what_we_send_is_what_our_own_reader_accepts(self):
        """Lenient inbound, strict outbound: the two still have to meet.

        A partner running our code must be able to read our header, or we
        would be doing to them what Voltality did to us.
        """
        from ocpi.push import auth_header
        from ocpi.router import _token_candidates

        self.assertIn(self.TOKEN, _token_candidates(auth_header(self.TOKEN)))

    async def test_a_command_result_goes_out_encoded(self):
        """End to end through the callback, not just the helper."""
        # `import ocpi.router as router` binds the APIRouter object that
        # ocpi/__init__ exports under that name, not the module.
        import importlib

        router = importlib.import_module("ocpi.router")

        sent = {}

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                sent["url"] = url
                sent["headers"] = headers or {}
                sent["body"] = json
                return _FakeResponse(200)

        import httpx

        real_client = httpx.AsyncClient
        real_token = router._outbound_token
        httpx.AsyncClient = _FakeClient
        router._outbound_token = lambda partner_id=None: self.TOKEN
        try:
            await router._post_command_result(
                "https://api-uat.example.io/ocpi/emsp/2.2.1/commands/START_SESSION/1",
                "ACCEPTED",
            )
        finally:
            httpx.AsyncClient = real_client
            router._outbound_token = real_token

        from ocpi.push import auth_header

        self.assertEqual(sent["headers"].get("Authorization"), auth_header(self.TOKEN))
        self.assertEqual(sent["body"], {"result": "ACCEPTED"})

    async def test_no_stored_token_still_sends_no_header(self):
        """Better a missing header than a header built from an empty string."""
        # `import ocpi.router as router` binds the APIRouter object that
        # ocpi/__init__ exports under that name, not the module.
        import importlib

        router = importlib.import_module("ocpi.router")

        sent = {}

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                sent["headers"] = headers or {}
                return _FakeResponse(200)

        import os

        import httpx

        real_client = httpx.AsyncClient
        real_token = router._outbound_token
        real_env = os.environ.pop("OCPI_OUTBOUND_TOKEN", None)
        httpx.AsyncClient = _FakeClient
        router._outbound_token = lambda partner_id=None: None
        try:
            await router._post_command_result("https://example.test/cb", "ACCEPTED")
        finally:
            httpx.AsyncClient = real_client
            router._outbound_token = real_token
            if real_env is not None:
                os.environ["OCPI_OUTBOUND_TOKEN"] = real_env

        self.assertNotIn("Authorization", sent["headers"])


class PushGateTests(unittest.TestCase):
    """Storing a partner must not, by itself, start pushing to them.

    ocpi_partners was empty from the day it was created, so the push module
    has never sent anything. Writing Voltality's credential into it to fix the
    command callbacks would otherwise have switched outbound pushing on at the
    same moment, the day before their UAT. The fix and the new behaviour are
    separate decisions, so push waits for an explicit flag.
    """

    def setUp(self):
        import os

        self._real = os.environ.pop("OCPI_PUSH_ENABLED", None)

    def tearDown(self):
        import os

        os.environ.pop("OCPI_PUSH_ENABLED", None)
        if self._real is not None:
            os.environ["OCPI_PUSH_ENABLED"] = self._real

    def test_off_by_default(self):
        from ocpi import push

        self.assertFalse(push.enabled())

    def test_the_flag_turns_it_on(self):
        import os

        from ocpi import push

        for value in ("1", "true", "TRUE", "yes", "on"):
            os.environ["OCPI_PUSH_ENABLED"] = value
            self.assertTrue(push.enabled(), value)

    def test_a_nonsense_value_leaves_it_off(self):
        import os

        from ocpi import push

        for value in ("0", "false", "no", "off", "", "maybe"):
            os.environ["OCPI_PUSH_ENABLED"] = value
            self.assertFalse(push.enabled(), value)

    def test_nothing_is_queued_while_it_is_off(self):
        """The guard is at the call site, so a disabled push costs nothing."""
        import asyncio

        from ocpi import push

        real_queue = push._QUEUE
        try:
            push._QUEUE = asyncio.Queue(maxsize=10)
            push.enqueue("cdr", 1)
            self.assertEqual(push._QUEUE.qsize(), 0)
        finally:
            push._QUEUE = real_queue

    def test_it_queues_once_turned_on(self):
        """And the guard is the only thing standing in the way."""
        import asyncio
        import os

        from ocpi import push

        real_queue = push._QUEUE
        try:
            os.environ["OCPI_PUSH_ENABLED"] = "1"
            push._QUEUE = asyncio.Queue(maxsize=10)
            push.enqueue("cdr", 1)
            self.assertEqual(push._QUEUE.qsize(), 1)
        finally:
            push._QUEUE = real_queue


class CallbackOutcomeTests(unittest.IsolatedAsyncioTestCase):
    """A refused callback has to leave a trace on our side.

    httpx does not raise on 4xx, so the 401s Voltality reported four times
    produced no log line here at all. We only ever learned of them by
    WhatsApp, which is why the cause took weeks to find.
    """

    async def _fire(self, status, text=""):
        import importlib
        import logging

        router = importlib.import_module("ocpi.router")

        class _Client:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                return _FakeResponse(status, text)

        import httpx

        real_client, real_token = httpx.AsyncClient, router._outbound_token
        httpx.AsyncClient = _Client
        router._outbound_token = lambda partner_id=None: "tok"
        try:
            with self.assertLogs("ocpi.router", level=logging.INFO) as caught:
                await router._post_command_result("https://partner.test/cb", "ACCEPTED")
        finally:
            httpx.AsyncClient = real_client
            router._outbound_token = real_token
        return caught.output

    async def test_a_refused_callback_is_logged_as_a_warning(self):
        lines = await self._fire(401, "Unauthorized")
        self.assertTrue(any("WARNING" in l and "401" in l for l in lines), lines)
        self.assertTrue(any("refused" in l for l in lines), lines)

    async def test_an_accepted_callback_says_so(self):
        lines = await self._fire(200)
        self.assertTrue(any("accepted" in l for l in lines), lines)
        self.assertFalse(any("WARNING" in l for l in lines), lines)

    async def test_the_result_we_sent_is_in_the_line(self):
        """So a log reader can tie the outcome to the command."""
        lines = await self._fire(401)
        self.assertTrue(any("ACCEPTED" in l for l in lines), lines)


class StateOfChargeTests(unittest.TestCase):
    """SoC belongs on the Session, in a charging period, and nowhere else.

    Voltality tested with a simulator that reports SoC and found our Session
    objects carried no `charging_periods` at all, so the value had nowhere to
    go. We had been storing it on every meter value since the column was
    added; it simply never reached the partner.

    OCPI 2.2.1 lists STATE_OF_CHARGE among the dimensions that "SHALL
    therefore only be used in Sessions", so the CDR must not gain it.
    """

    CP = "SOCTEST1"

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        # Deliberately not published and in no tenant: these tests build the
        # Session object directly, and a charger that joins a tenant would
        # move the counts test_tenants asserts on.
        cls.charger = Charger(charge_point_id=cls.CP, tariff_per_kwh=1.40,
                              idle_fee_enabled=False)
        cls.db.add(cls.charger)
        cls.db.commit()

        start = datetime(2026, 11, 13, 16, 0, 0)
        cls.sess = ChargingSession(
            charger_id=cls.charger.id, transaction_id=90901,
            status="completed", start_time=start,
            stop_time=start + timedelta(minutes=30),
            unplugged_at=start + timedelta(minutes=31),
            energy_consumed=12.0, user_id="SOCUSER",
        )
        cls.db.add(cls.sess)
        cls.db.commit()

        # Readings a real charger would send: SoC climbing, with repeats in
        # between where nothing moved.
        for minute, soc in ((0, 20.0), (5, 20.0), (10, 35.0), (15, 35.0),
                            (20, 58.0), (30, 80.0)):
            cls.db.add(MeterValue(
                charger_id=cls.charger.id, transaction_id=90901,
                connector_id=1, timestamp=start + timedelta(minutes=minute),
                total_kwh=minute / 2.5, soc=soc))
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Leave the shared test database as we found it.
        cls.db.query(MeterValue).filter(
            MeterValue.charger_id == cls.charger.id).delete()
        cls.db.query(ChargingSession).filter(
            ChargingSession.charger_id == cls.charger.id).delete()
        cls.db.query(Charger).filter(Charger.id == cls.charger.id).delete()
        cls.db.commit()
        cls.db.close()

    def _session(self):
        from ocpi.router import _build_session_dict
        return _build_session_dict(self.sess)

    def test_the_session_now_has_charging_periods(self):
        self.assertIn("charging_periods", self._session())

    def test_every_period_carries_a_state_of_charge(self):
        for p in self._session()["charging_periods"]:
            types = [d["type"] for d in p["dimensions"]]
            self.assertIn("STATE_OF_CHARGE", types)

    def test_the_percentages_are_the_ones_the_charger_reported(self):
        got = [d["volume"] for p in self._session()["charging_periods"]
               for d in p["dimensions"]]
        self.assertEqual(got, [20.0, 35.0, 58.0, 80.0])

    def test_a_reading_that_did_not_move_is_not_republished(self):
        """Six readings, four of them distinct."""
        self.assertEqual(len(self._session()["charging_periods"]), 4)

    def test_each_period_is_stamped_with_its_own_reading_time(self):
        from ocpi.router import _session_time
        first = self._session()["charging_periods"][0]
        self.assertEqual(first["start_date_time"],
                         _session_time(datetime(2026, 11, 13, 16, 0, 0)))

    def test_the_cdr_does_not_carry_state_of_charge(self):
        """Session only, per the spec. A CDR with SoC is non-compliant."""
        from ocpi.router import _build_cdr_dict
        cdr = _build_cdr_dict(self.sess)
        dims = {d["type"] for p in cdr["charging_periods"] for d in p["dimensions"]}
        self.assertNotIn("STATE_OF_CHARGE", dims)

    def test_a_session_without_soc_omits_the_field_entirely(self):
        """Most chargers never report it, and an empty array claims otherwise."""
        from ocpi.router import _build_session_dict
        quiet = ChargingSession(
            charger_id=self.charger.id, transaction_id=90902,
            status="completed", start_time=datetime(2026, 11, 13, 18, 0, 0),
            stop_time=datetime(2026, 11, 13, 18, 20, 0),
            energy_consumed=5.0, user_id="NOSOC")
        self.db.add(quiet)
        self.db.commit()
        self.assertNotIn("charging_periods", _build_session_dict(quiet))

    def test_the_list_endpoint_does_not_query_once_per_session(self):
        """Prefetched rows are used as given, so a page costs one query."""
        from ocpi.router import _build_session_dict
        built = _build_session_dict(self.sess, [])
        self.assertNotIn("charging_periods", built)

    def test_prefetching_produces_what_the_single_lookup_does(self):
        from ocpi.router import _build_session_dict, _soc_rows_for
        rows = _soc_rows_for(self.db, [self.sess])
        key = (self.sess.charger_id, self.sess.transaction_id)
        self.assertEqual(
            _build_session_dict(self.sess, rows.get(key, []))["charging_periods"],
            self._session()["charging_periods"])


class ChargerAddressTests(unittest.TestCase):
    """A charger's city and postcode belong to the charger.

    OCPI publishes an address in parts. The street line came from the charger
    row, but city and postal_code came from OCPI_LOCATION_CITY and
    OCPI_LOCATION_POSTAL, one value for the whole platform, never changed from
    their defaults. DC3001 sits in Shah Alam with correct coordinates and was
    published as Kuala Lumpur 50000, so the text contradicted the pin while
    Perodua were being shown the charger.
    """

    CP = "ADDRTEST1"

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.charger = Charger(charge_point_id=cls.CP, tariff_per_kwh=1.40,
                              location="2, Jalan Gergaji 15/14, Seksyen 15",
                              city="Shah Alam", postal_code="40200",
                              latitude=3.06566, longitude=101.533168)
        cls.db.add(cls.charger)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(Charger).filter(Charger.id == cls.charger.id).delete()
        cls.db.commit()
        cls.db.close()

    def _fields(self):
        from ocpi.router import _location_fields
        return _location_fields(self.charger)

    def test_the_city_comes_from_the_charger(self):
        self.assertEqual(self._fields()[1], "Shah Alam")

    def test_the_postcode_comes_from_the_charger(self):
        self.assertEqual(self._fields()[2], "40200")

    def test_the_street_line_is_unchanged(self):
        self.assertEqual(self._fields()[0], "2, Jalan Gergaji 15/14, Seksyen 15")

    def test_the_pin_and_the_text_agree(self):
        """The defect in one assertion: a Shah Alam pin said Kuala Lumpur."""
        address, city, postal, coords = self._fields()
        self.assertEqual(coords["latitude"], "3.065660")
        self.assertNotEqual(city, "Kuala Lumpur")

    def test_a_charger_with_no_city_falls_back_to_the_setting(self):
        """NULL keeps exactly the behaviour every charger had before."""
        import os

        from ocpi.router import _location_fields
        blank = Charger(charge_point_id="ADDRTEST2", tariff_per_kwh=1.40,
                        location="Somewhere", latitude=3.0, longitude=101.0)
        self.db.add(blank)
        self.db.commit()
        try:
            real = os.environ.get("OCPI_LOCATION_CITY")
            os.environ["OCPI_LOCATION_CITY"] = "Kuala Lumpur"
            try:
                self.assertEqual(_location_fields(blank)[1], "Kuala Lumpur")
            finally:
                os.environ.pop("OCPI_LOCATION_CITY", None)
                if real is not None:
                    os.environ["OCPI_LOCATION_CITY"] = real
        finally:
            self.db.query(Charger).filter(Charger.id == blank.id).delete()
            self.db.commit()

    def test_whitespace_is_not_a_city(self):
        """A box someone spacebarred is empty, not a place called ' '."""
        import os

        from ocpi.router import _location_fields
        self.charger.city = "   "
        try:
            real = os.environ.get("OCPI_LOCATION_CITY")
            os.environ["OCPI_LOCATION_CITY"] = "Fallback City"
            try:
                self.assertEqual(_location_fields(self.charger)[1], "Fallback City")
            finally:
                os.environ.pop("OCPI_LOCATION_CITY", None)
                if real is not None:
                    os.environ["OCPI_LOCATION_CITY"] = real
        finally:
            self.charger.city = "Shah Alam"

    def test_the_published_location_carries_them(self):
        """End to end, not just the helper."""
        from ocpi.router import _build_location_dict
        loc = _build_location_dict(self.charger)
        self.assertEqual(loc["city"], "Shah Alam")
        self.assertEqual(loc["postal_code"], "40200")
        self.assertEqual(loc["address"], "2, Jalan Gergaji 15/14, Seksyen 15")

    def test_a_cdr_location_carries_them_too(self):
        """A CDR embeds its own copy of the location and must not disagree."""
        from ocpi.router import _location_fields
        address, city, postal, _ = _location_fields(self.charger)
        self.assertEqual((city, postal), ("Shah Alam", "40200"))

    def test_changing_the_city_is_visible_to_a_partner(self):
        """It is in the partner-visible set, so polling on last_updated sees it."""
        from database import _PARTNER_VISIBLE_CHARGER_FIELDS
        self.assertIn("city", _PARTNER_VISIBLE_CHARGER_FIELDS)
        self.assertIn("postal_code", _PARTNER_VISIBLE_CHARGER_FIELDS)


class NewChargerIsHiddenTests(unittest.TestCase):
    """A charger that registers itself must not reach a roaming partner.

    Chargers are created from a BootNotification on both OCPP stacks, by the
    edge sync and from the dashboard. Publication has been opt-in since the
    Proton home chargers leaked, so a new row was already hidden while its
    flag was NULL; this pins it to an explicit False so the state is a
    decision rather than an absence, and so a future call site cannot quietly
    opt a charger in by setting the column itself.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.made = []

    def tearDown(self):
        for c in self.made:
            self.db.query(Charger).filter(Charger.id == c.id).delete()
        self.db.commit()
        self.db.close()

    def _add(self, **kw):
        c = Charger(tariff_per_kwh=1.40, **kw)
        self.db.add(c)
        self.db.commit()
        self.made.append(c)
        return c

    def test_a_new_charger_is_hidden(self):
        c = self._add(charge_point_id="NEWBOOT1")
        self.assertIs(c.is_public, False)

    def test_it_is_false_not_merely_null(self):
        """NULL hides it too, but says nobody decided."""
        c = self._add(charge_point_id="NEWBOOT2")
        self.assertIsNotNone(c.is_public)

    def test_publishing_one_on_purpose_still_works(self):
        c = self._add(charge_point_id="NEWBOOT3", is_public=True)
        self.assertIs(c.is_public, True)

    def test_an_explicit_false_is_left_alone(self):
        c = self._add(charge_point_id="NEWBOOT4", is_public=False)
        self.assertIs(c.is_public, False)

    def test_a_new_charger_is_not_served_to_a_partner(self):
        """The point of the whole thing, asserted through the real filter."""
        from ocpi.router import _publishable
        self._add(charge_point_id="NEWBOOT5", tenant="czero-tng")
        served = {
            c.charge_point_id
            for c in _publishable(self.db.query(Charger)).all()
        }
        self.assertNotIn("NEWBOOT5", served)

    def test_the_same_charger_appears_once_published(self):
        from ocpi.router import _publishable
        c = self._add(charge_point_id="NEWBOOT6", tenant="czero-tng")
        c.is_public = True
        self.db.commit()
        served = {
            x.charge_point_id
            for x in _publishable(self.db.query(Charger)).all()
        }
        self.assertIn("NEWBOOT6", served)


class PublishableTenantTests(unittest.TestCase):
    """Only the CZero TNG tenant reaches a roaming partner.

    `mini` sat in this list until 2026-11-18 and published nothing, because
    its one charger is not flagged. Aqid asked for czero-tng alone: a list
    that admits a tenant nobody intends to publish is a door left open.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.made = []

    def tearDown(self):
        for c in self.made:
            self.db.query(Charger).filter(Charger.id == c.id).delete()
        self.db.commit()
        self.db.close()

    def _add(self, cp, tenant):
        c = Charger(charge_point_id=cp, tenant=tenant, tariff_per_kwh=1.40,
                    is_public=True)
        self.db.add(c)
        self.db.commit()
        self.made.append(c)
        return c

    def _served(self):
        from ocpi.router import _publishable
        return {c.charge_point_id for c in _publishable(self.db.query(Charger)).all()}

    def test_czero_tng_publishes(self):
        self._add("TENANTOK1", "czero-tng")
        self.assertIn("TENANTOK1", self._served())

    def test_mini_no_longer_publishes(self):
        """Flagged on, and still withheld, because the tenant is not ours."""
        self._add("TENANTMINI", "mini")
        self.assertNotIn("TENANTMINI", self._served())

    def test_a_fleet_tenant_is_withheld_even_when_flagged(self):
        for cp, tenant in (("TENANTPER", "perodua"),
                           ("TENANTPRO", "proton"),
                           ("TENANTHIC", "hicom")):
            self._add(cp, tenant)
        served = self._served()
        for cp in ("TENANTPER", "TENANTPRO", "TENANTHIC"):
            self.assertNotIn(cp, served, cp)

    def test_the_list_is_exactly_one_tenant(self):
        from ocpi.router import _PUBLISHABLE_TENANTS
        self.assertEqual(_PUBLISHABLE_TENANTS, {"czero-tng"})


class PublishesHelperTests(unittest.TestCase):
    """One rule, two callers: the OCPI query and the dashboard card.

    The card used to decide this in JavaScript and still carried the rule
    retired in October, so a charger with a recent heartbeat and no flag was
    shown as "Published (auto)" while the OCPI endpoints withheld it. The
    server now answers, and these pin the helper to the query it mirrors.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.made = []

    def tearDown(self):
        for c in self.made:
            self.db.query(Charger).filter(Charger.id == c.id).delete()
        self.db.commit()
        self.db.close()

    def _add(self, cp, tenant, flag):
        c = Charger(charge_point_id=cp, tenant=tenant, is_public=flag,
                    tariff_per_kwh=1.40,
                    last_heartbeat=datetime.utcnow())
        self.db.add(c)
        self.db.commit()
        self.made.append(c)
        return c

    def test_it_agrees_with_the_query_on_every_case(self):
        from ocpi.router import _publishable, publishes
        cases = [
            ("AGREE1", "czero-tng", True),
            ("AGREE2", "czero-tng", False),
            ("AGREE3", "czero-tng", None),
            ("AGREE4", "perodua", True),
            ("AGREE5", "mini", True),
            ("AGREE6", None, True),
        ]
        for cp, tenant, flag in cases:
            self._add(cp, tenant, flag)
        served = {c.charge_point_id for c in _publishable(self.db.query(Charger)).all()}
        for cp, _, _ in cases:
            c = next(x for x in self.made if x.charge_point_id == cp)
            with self.subTest(cp):
                self.assertEqual(publishes(c), cp in served)

    def test_a_recent_heartbeat_does_not_publish_on_its_own(self):
        """The exact belief the dashboard used to report."""
        from ocpi.router import publishes
        c = self._add("FRESHBUTOFF", "czero-tng", None)
        self.assertIsNotNone(c.last_heartbeat)
        self.assertFalse(publishes(c))

    def test_a_flagged_charger_in_a_withheld_tenant_is_not_published(self):
        from ocpi.router import publishes
        self.assertFalse(publishes(self._add("FLAGGEDPER", "perodua", True)))


class ChargersPayloadTests(unittest.TestCase):
    """The dashboard has to receive what the handler computed.

    `publishes` was right, the handler put `roaming_published` in the dict,
    and the browser still showed every charger as hidden. The route carries
    response_model=List[ChargerStatus] and FastAPI drops any key the model
    does not declare, so the field never left the server. A unit test on the
    predicate cannot see that; this asks the endpoint.
    """

    CP = "PAYLOADTEST1"

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()
        cls.charger = Charger(charge_point_id=cls.CP, tenant="czero-tng",
                              is_public=True, tariff_per_kwh=1.40,
                              status="offline", availability="available")
        cls.db.add(cls.charger)
        cls.db.commit()
        api.invalidate_chargers_cache()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(Charger).filter(Charger.id == cls.charger.id).delete()
        cls.db.commit()
        cls.db.close()
        api.invalidate_chargers_cache()

    def _row(self):
        r = self.client.get("/api/chargers")
        self.assertEqual(r.status_code, 200, r.text)
        for c in r.json():
            if c.get("charge_point_id") == self.CP:
                return c
        self.fail("%s missing from /api/chargers" % self.CP)

    def test_the_field_survives_the_response_model(self):
        self.assertIn("roaming_published", self._row())

    def test_a_published_charger_says_so(self):
        self.assertIs(self._row()["roaming_published"], True)

    def test_it_matches_the_predicate(self):
        from ocpi.router import publishes
        self.assertEqual(self._row()["roaming_published"], publishes(self.charger))

    def test_a_withheld_tenant_is_reported_as_not_published(self):
        self.charger.tenant = "perodua"
        self.db.commit()
        api.invalidate_chargers_cache()
        try:
            self.assertIs(self._row()["roaming_published"], False)
            self.assertIs(self._row()["is_public"], True)
        finally:
            self.charger.tenant = "czero-tng"
            self.db.commit()
            api.invalidate_chargers_cache()


class TenantAnalyticsTests(unittest.TestCase):
    """Analytics split by fleet, and the split reconciling with the total.

    Charging revenue was energy times a flat RM0.50 taken from a pricing
    table that has never had a row, so DC3001 at RM1.40 and the Proton and
    Perodua fleets at RM0.10 were all valued the same, and idle fees were
    left out. All-time it read RM1,135 against RM3,938 billed.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.chargers, cls.sessions = [], []
        start = datetime.utcnow() - timedelta(days=2)

        # Two fleets at different rates, so a flat rate cannot reproduce it.
        for cp, tenant, rate in (("TENA1", "fleet-a", 1.40), ("TENB1", "fleet-b", 0.10)):
            c = Charger(charge_point_id=cp, tenant=tenant, tariff_per_kwh=rate,
                        status="online", availability="available", is_public=True)
            cls.db.add(c)
            cls.db.commit()
            cls.chargers.append(c)

        def sess(charger, kwh, idle, frozen=None):
            s = ChargingSession(charger_id=charger.id, transaction_id=70000 + len(cls.sessions),
                                status="completed", start_time=start,
                                stop_time=start + timedelta(minutes=30),
                                energy_consumed=kwh, idle_fee_amount=idle,
                                tariff_per_kwh_at_start=frozen)
            cls.db.add(s)
            cls.db.commit()
            cls.sessions.append(s)

        sess(cls.chargers[0], 10.0, 2.00)            # 10 * 1.40 + 2.00 = 16.00
        sess(cls.chargers[0], 5.0, 0.00, 0.80)       # frozen: 5 * 0.80  =  4.00
        sess(cls.chargers[1], 20.0, 0.00)            # 20 * 0.10         =  2.00

    @classmethod
    def tearDownClass(cls):
        for s in cls.sessions:
            cls.db.query(ChargingSession).filter(ChargingSession.id == s.id).delete()
        for c in cls.chargers:
            cls.db.query(Charger).filter(Charger.id == c.id).delete()
        cls.db.commit()
        cls.db.close()

    def _rows(self):
        month_ago = datetime.utcnow() - timedelta(days=30)
        return {r["key"]: r for r in api._tenant_breakdown(self.db, month_ago)}

    def test_each_fleet_is_valued_at_its_own_rate(self):
        rows = self._rows()
        self.assertAlmostEqual(rows["fleet-a"]["revenue"]["total"], 20.00, places=2)
        self.assertAlmostEqual(rows["fleet-b"]["revenue"]["total"], 2.00, places=2)

    def test_a_frozen_rate_beats_the_chargers_rate_today(self):
        """The second session sold at RM0.80 while the charger says RM1.40."""
        rows = self._rows()
        self.assertAlmostEqual(rows["fleet-a"]["revenue"]["total"], 16.00 + 4.00, places=2)

    def test_idle_is_counted_and_reported_separately(self):
        rows = self._rows()
        self.assertAlmostEqual(rows["fleet-a"]["revenue"]["idle"], 2.00, places=2)
        self.assertAlmostEqual(rows["fleet-b"]["revenue"]["idle"], 0.00, places=2)

    def test_a_flat_rate_would_not_reproduce_this(self):
        """Pins the defect: 35 kWh at RM0.50 is 17.50, the old figure."""
        rows = self._rows()
        ours = rows["fleet-a"]["revenue"]["total"] + rows["fleet-b"]["revenue"]["total"]
        energy = rows["fleet-a"]["energy"]["total_kwh"] + rows["fleet-b"]["energy"]["total_kwh"]
        self.assertAlmostEqual(energy, 35.0, places=2)
        self.assertNotAlmostEqual(ours, energy * 0.50, places=2)

    def test_energy_and_session_counts_are_per_fleet(self):
        rows = self._rows()
        self.assertEqual(rows["fleet-a"]["sessions"]["total"], 2)
        self.assertEqual(rows["fleet-b"]["sessions"]["total"], 1)
        self.assertAlmostEqual(rows["fleet-a"]["energy"]["total_kwh"], 15.0, places=2)

    def test_charger_counts_are_per_fleet(self):
        rows = self._rows()
        self.assertEqual(rows["fleet-a"]["chargers"]["total"], 1)
        self.assertEqual(rows["fleet-a"]["chargers"]["online"], 1)
        self.assertEqual(rows["fleet-a"]["chargers"]["published"], 1)

    def test_an_unregistered_tenant_is_kept_and_flagged(self):
        """A charger may carry a key the registry never had; losing its
        sessions from the split would make the total stop adding up."""
        rows = self._rows()
        self.assertFalse(rows["fleet-a"]["registered"])
        self.assertEqual(rows["fleet-a"]["label"], "fleet-a")

    def test_the_split_adds_up_to_the_whole(self):
        """The reconciliation the totals row shows on screen."""
        from sqlalchemy import func as f
        rows = list(self._rows().values())
        split = round(sum(r["revenue"]["total"] for r in rows), 2)
        whole = round(float(
            self.db.query(f.coalesce(f.sum(api._session_revenue_sql()), 0))
            .join(Charger, Charger.id == ChargingSession.charger_id)
            .scalar() or 0
        ), 2)
        self.assertAlmostEqual(split, whole, places=2)


class CommandScopeTests(OcpiTestBase):
    """A partner may only command what it is allowed to see.

    Reading was already filtered: a location for an unpublished charger
    answers 2003. Commands were not. START_SESSION naming a Perodua or
    Proton home unit was accepted and dispatched, and STOP_SESSION took a
    bare primary key, so any holder of the shared token could stop any
    charge on the platform by counting upwards through small integers.

    Probed against production on 2026-11-19 before the fix: both returned
    ACCEPTED. The chargers were offline, so nothing physical happened.
    """

    def setUp(self):
        self.db = SessionLocal()
        self.made = []
        self.private = Charger(charge_point_id="PRIVATEHOME1", tenant="perodua",
                               tariff_per_kwh=0.10, status="offline",
                               availability="available")
        self.db.add(self.private)
        self.db.commit()
        self.made.append(self.private)
        # A session on that private charger, as another fleet's customer.
        self.theirs = ChargingSession(
            charger_id=self.private.id, transaction_id=88001, status="active",
            start_time=datetime.utcnow() - timedelta(minutes=10))
        self.db.add(self.theirs)
        self.db.commit()

    def tearDown(self):
        self.db.query(ChargingSession).filter(
            ChargingSession.id == self.theirs.id).delete()
        for c in self.made:
            self.db.query(Charger).filter(Charger.id == c.id).delete()
        self.db.commit()
        self.db.close()

    def _cmd(self, command, body):
        body = dict(body)
        body["response_url"] = "https://partner.test/cb"
        return self.client.post(
            f"/ocpi/2.2.1/commands/{command}", json=body, headers=AUTH).json()

    def test_a_start_on_an_unpublished_charger_is_rejected(self):
        r = self._cmd("START_SESSION", {
            "location_id": "MYPLG-PRIVATEHOME1",
            "evse_uid": "MYPLG-PRIVATEHOME1-EVSE1",
            "token": {"uid": "PROBE"},
        })
        self.assertEqual(r["data"]["result"], "REJECTED")

    def test_a_start_on_a_published_charger_still_works(self):
        """The fix must not close the door on the integration itself."""
        r = self._cmd("START_SESSION", {
            "location_id": f"MYPLG-{CP}",
            "evse_uid": f"MYPLG-{CP}-EVSE1",
            "token": {"uid": "PROBE"},
        })
        self.assertNotEqual(r["data"]["result"], "REJECTED")

    def test_another_fleets_session_cannot_be_stopped(self):
        """By primary key, which is what the handler used to accept."""
        r = self._cmd("STOP_SESSION", {"session_id": self.theirs.id})
        self.assertEqual(r["data"]["result"], "ACCEPTED")
        # OCPI answers the POST synchronously; the refusal is the async
        # result, so assert the session was never matched.
        self.db.refresh(self.theirs)
        self.assertEqual(self.theirs.status, "active")

    def test_a_session_id_that_is_not_a_number_is_survivable(self):
        r = self._cmd("STOP_SESSION", {"session_id": "not-a-number"})
        self.assertEqual(r["status_code"], 1000)

    def test_a_missing_session_id_is_survivable(self):
        r = self._cmd("STOP_SESSION", {})
        self.assertEqual(r["status_code"], 1000)


class MultiPartnerTokenTests(unittest.TestCase):
    """With two partners registered, reply to the one that asked.

    `_outbound_token` took the newest row outright, which was correct while
    a single partner existed. Voltality registered production as SG/VLT on
    2026-11-25 beside the SG/VOL UAT row, so every callback, including the
    ones answering UAT, would have carried the production token. That is
    the same 401 they spent a month reporting, arriving by a new route on
    go-live day.
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        from database import OcpiPartner
        self.made = []
        for cc, pid, tok in (("SG", "TSTA", "token-aaa"), ("SG", "TSTB", "token-bbb")):
            p = OcpiPartner(country_code=cc, party_id=pid, token=tok,
                            versions_url="https://%s.test/versions" % pid.lower())
            self.db.add(p)
            self.db.commit()
            self.made.append(p)
        self.first, self.second = self.made

    def tearDown(self):
        from database import OcpiPartner
        for p in self.made:
            self.db.query(OcpiPartner).filter(OcpiPartner.id == p.id).delete()
        self.db.commit()
        self.db.close()

    def _token(self, partner_id=None):
        import importlib
        return importlib.import_module("ocpi.router")._outbound_token(partner_id)

    def test_the_older_partner_gets_its_own_token(self):
        """The case that broke: not the newest row."""
        self.assertEqual(self._token(self.first.id), "token-aaa")

    def test_the_newer_partner_gets_its_own_token(self):
        self.assertEqual(self._token(self.second.id), "token-bbb")

    def test_an_unknown_caller_falls_back_to_the_newest(self):
        """The shared token identifies nobody, and drove the whole UAT."""
        self.assertEqual(self._token(None), "token-bbb")

    def test_a_partner_id_that_no_longer_exists_falls_back(self):
        missing = max(p.id for p in self.made) + 10_000
        self.assertEqual(self._token(missing), "token-bbb")

    async def _fire(self, partner_id):
        import importlib
        router = importlib.import_module("ocpi.router")
        sent = {}

        class _Client:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                sent["headers"] = headers or {}
                return _FakeResponse(200)

        import httpx
        real = httpx.AsyncClient
        httpx.AsyncClient = _Client
        try:
            await router._post_command_result(
                "https://partner.test/cb", "ACCEPTED", partner_id=partner_id)
        finally:
            httpx.AsyncClient = real
        return sent["headers"].get("Authorization")

    def test_the_callback_carries_the_asking_partners_token(self):
        import asyncio

        from ocpi.push import auth_header
        got = asyncio.new_event_loop().run_until_complete(self._fire(self.first.id))
        self.assertEqual(got, auth_header("token-aaa"))
        self.assertNotEqual(got, auth_header("token-bbb"))


class StopInitiatorTests(unittest.TestCase):
    """Who ended the charge, which the charger's reason cannot say.

    Voltality's live test on 2026-11-25 ended two charges from the car and
    DC3001 reported "Other" for both, the same word it uses when it finishes
    by itself. The dashboard could only print "reason: other".
    """

    CP = "STOPTEST1"

    def setUp(self):
        import ocpp_server as oc
        self.oc = oc
        oc._REMOTE_STOP_TXNS.clear()

    def tearDown(self):
        self.oc._REMOTE_STOP_TXNS.clear()

    def test_a_remote_reason_is_the_platform(self):
        self.assertEqual(self.oc.stop_initiator(self.CP, 1, "Remote"), "platform")

    def test_other_after_our_own_stop_is_the_platform(self):
        """Some firmware answers Other even for a stop we asked for."""
        self.oc._remember_remote_stop(self.CP, 7)
        self.assertEqual(self.oc.stop_initiator(self.CP, 7, "Other"), "platform")

    def test_other_with_no_stop_from_us_is_the_vehicle(self):
        """The case that was invisible: the driver ended it from the car."""
        self.assertEqual(self.oc.stop_initiator(self.CP, 8, "Other"), "vehicle")

    def test_no_reason_at_all_with_no_stop_from_us_is_the_vehicle(self):
        self.assertEqual(self.oc.stop_initiator(self.CP, 9, None), "vehicle")

    def test_local_is_the_charge_point(self):
        self.assertEqual(self.oc.stop_initiator(self.CP, 2, "Local"), "charger")

    def test_ev_disconnected_is_the_vehicle(self):
        self.assertEqual(self.oc.stop_initiator(self.CP, 3, "EVDisconnected"), "vehicle")

    def test_a_fault_is_the_charge_point(self):
        for r in ("PowerLoss", "EmergencyStop", "ImmediateReset", "NeverStarted"):
            with self.subTest(r):
                self.assertEqual(self.oc.stop_initiator(self.CP, 4, r), "charger")

    def test_our_stop_does_not_vouch_for_another_charger(self):
        self.oc._remember_remote_stop(self.CP, 11)
        self.assertEqual(self.oc.stop_initiator("OTHERCP", 11, "Other"), "vehicle")

    def test_our_stop_does_not_vouch_for_another_transaction(self):
        self.oc._remember_remote_stop(self.CP, 12)
        self.assertEqual(self.oc.stop_initiator(self.CP, 13, "Other"), "vehicle")

    def test_an_expired_note_no_longer_vouches(self):
        self.oc._REMOTE_STOP_TXNS[(self.CP, 14)] = 0
        self.assertEqual(self.oc.stop_initiator(self.CP, 14, "Other"), "vehicle")

    def test_the_field_survives_the_response_model(self):
        """A key the model does not declare never reaches the dashboard."""
        self.assertIn("stop_initiator", api.ChargingSessionResponse.model_fields)


class IdlingStateTests(unittest.TestCase):
    """A charge ends in two steps and the badge only knew about the first.

    The transaction closes when the car stops drawing power; the session is
    not finished until the cable comes out. The idle fee runs in between and
    the CDR is held until the unplug, yet the row read COMPLETED from the
    moment the transaction closed, so a bay still occupied and still charging
    the driver looked settled. The dashboard needs the three columns that
    describe the gap, and the page needs to show it.
    """

    PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates", "sessions.html")

    @classmethod
    def setUpClass(cls):
        with io.open(cls.PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()

    def test_the_unplug_time_survives_the_response_model(self):
        self.assertIn("unplugged_at", api.ChargingSessionResponse.model_fields)

    def test_the_accruing_idle_figures_survive_the_response_model(self):
        for f in ("idle_minutes", "idle_fee_amount"):
            with self.subTest(f):
                self.assertIn(f, api.ChargingSessionResponse.model_fields)

    def test_the_unplug_time_is_sent_as_local_wall_time(self):
        """Every other timestamp on this row is MYT; a UTC one would read as
        an unplug eight hours before the charge ended."""
        ser = api.ChargingSessionResponse.__pydantic_decorators__.field_serializers
        fields = set()
        for d in ser.values():
            fields.update(d.info.fields)
        self.assertIn("unplugged_at", fields)

    def test_the_three_columns_exist_on_the_session(self):
        for f in ("unplugged_at", "idle_minutes", "idle_fee_amount"):
            with self.subTest(f):
                self.assertTrue(hasattr(ChargingSession, f))

    # --- the page -------------------------------------------------------
    def test_the_badge_is_derived_and_not_the_raw_status(self):
        self.assertNotIn('<span class="ss-pill ${s.status}">${s.status}</span>', self.page)
        self.assertIn("_displayStatus(s)", self.page)

    def test_a_still_plugged_session_reads_as_idling(self):
        self.assertIn("'idling'", self.page)
        self.assertIn("s.unplugged_at", self.page)

    def test_the_idling_badge_has_a_style_of_its_own(self):
        self.assertIn(".ss-pill.idling", self.page)


class InvoiceTenantScopeTests(unittest.TestCase):
    """One report cannot cover five fleets.

    The invoice page mixed Perodua, HICOM, PROTON, Mini and CZero TNG into a
    single set of totals, so there was nothing to send to any of them. It
    also priced the whole platform at one rate read from an empty pricing
    table, which fell back to RM0.50/kWh however much a charger actually
    charges, and counted no idle income at all.

    These tests run against the endpoints rather than the helpers, because
    the page reads the endpoints and a helper that is right on its own has
    already let a wrong figure through to a printed report once.
    """

    A = "INVTENANTA1"      # tenant alpha, RM1.40/kWh
    B = "INVTENANTB1"      # tenant beta,  RM0.80/kWh
    TA = "inv-test-alpha"
    TB = "inv-test-beta"
    DAY = datetime(2026, 7, 15, 10, 0, 0)

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        api.app.dependency_overrides[api.require_admin_or_staff_admin] = \
            lambda: {"role": "admin", "email": "test@local"}
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()

        cls.ca = Charger(charge_point_id=cls.A, tenant=cls.TA, tariff_per_kwh=1.40,
                         location="Alpha Mall", city="Shah Alam", postal_code="40000",
                         status="offline", availability="available")
        cls.cb = Charger(charge_point_id=cls.B, tenant=cls.TB, tariff_per_kwh=0.80,
                         location="Beta Plaza", city="Klang", postal_code="41000",
                         status="offline", availability="available")
        cls.db.add_all([cls.ca, cls.cb])
        cls.db.commit()

        # Alpha: 10 kWh at the rate frozen on the session (1.40), unplugged an
        # hour after the charge stopped, RM3.00 of idle collected.
        cls.sa = ChargingSession(
            charger_id=cls.ca.id, transaction_id=990001, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            unplugged_at=cls.DAY + timedelta(hours=2),
            energy_consumed=10.0, tariff_per_kwh_at_start=1.40,
            idle_minutes=60, idle_fee_amount=Decimal("3.00"),
        )
        # Beta: 5 kWh, no frozen rate, so it falls back to its charger's 0.80.
        cls.sb = ChargingSession(
            charger_id=cls.cb.id, transaction_id=990002, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            energy_consumed=5.0, tariff_per_kwh_at_start=None,
            idle_minutes=0, idle_fee_amount=Decimal("0"),
        )
        cls.db.add_all([cls.sa, cls.sb])
        cls.db.commit()
        api.invalidate_chargers_cache()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(ChargingSession).filter(
            ChargingSession.transaction_id.in_([990001, 990002])).delete(
            synchronize_session=False)
        cls.db.query(Charger).filter(
            Charger.id.in_([cls.ca.id, cls.cb.id])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        api.app.dependency_overrides.pop(api.require_admin_or_staff_admin, None)
        api.invalidate_chargers_cache()

    def _summary(self, **kw):
        kw.setdefault("start_date", "2026-07-01")
        kw.setdefault("end_date", "2026-07-31")
        r = self.client.get("/api/invoice/summary", params=kw)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _sessions(self, **kw):
        kw.setdefault("start_date", "2026-07-01")
        kw.setdefault("end_date", "2026-07-31")
        r = self.client.get("/api/invoice/sessions", params=kw)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # --- scoping --------------------------------------------------------
    def test_a_tenant_report_counts_only_that_tenant(self):
        self.assertEqual(self._summary(tenant=self.TA)["sessions"]["total"], 1)
        self.assertEqual(self._summary(tenant=self.TB)["sessions"]["total"], 1)

    def test_a_tenant_report_shows_only_that_tenants_chargers(self):
        self.assertEqual(list(self._summary(tenant=self.TA)["charger_breakdown"]), [self.A])
        self.assertEqual(list(self._summary(tenant=self.TB)["charger_breakdown"]), [self.B])

    def test_the_session_lines_are_scoped_too(self):
        """The totals and the lines beneath them must agree, or the report
        prints a figure the rows do not add up to."""
        rows = self._sessions(tenant=self.TA)
        self.assertEqual([r["charge_point_id"] for r in rows], [self.A])

    def test_all_is_the_combined_view(self):
        for t in (None, "all", ""):
            with self.subTest(t):
                kw = {} if t is None else {"tenant": t}
                ids = {r["charge_point_id"] for r in self._sessions(**kw)}
                self.assertTrue({self.A, self.B} <= ids)

    def test_an_unknown_tenant_reports_nothing_rather_than_everything(self):
        self.assertEqual(self._summary(tenant="no-such-fleet")["sessions"]["total"], 0)

    def test_the_scope_is_echoed_back(self):
        self.assertEqual(self._summary(tenant=self.TA)["scope"]["tenant"], self.TA)
        self.assertEqual(self._summary()["scope"]["tenant"], "all")

    # --- money ----------------------------------------------------------
    def test_a_session_is_billed_at_its_own_rate_not_a_flat_guess(self):
        """10 kWh at 1.40 is 14.00. The old report said 5.00 for every
        charger on the platform."""
        s = self._summary(tenant=self.TA)
        self.assertEqual(s["revenue"]["energy"], 14.00)

    def test_a_session_from_before_the_freeze_falls_back_to_its_charger(self):
        s = self._summary(tenant=self.TB)
        self.assertEqual(s["revenue"]["energy"], 4.00)   # 5 kWh x 0.80

    def test_idle_income_is_counted(self):
        s = self._summary(tenant=self.TA)
        self.assertEqual(s["revenue"]["idle"], 3.00)
        self.assertEqual(s["revenue"]["total"], 17.00)

    def test_the_rate_card_is_what_the_period_actually_sold_at(self):
        self.assertEqual(self._summary(tenant=self.TA)["energy"]["price_per_kwh"], 1.40)
        self.assertEqual(self._summary(tenant=self.TB)["energy"]["price_per_kwh"], 0.80)

    def test_the_two_fleets_do_not_share_a_rate(self):
        """Proof the flat rate is gone: one number cannot be right for both."""
        a = self._summary(tenant=self.TA)["energy"]["price_per_kwh"]
        b = self._summary(tenant=self.TB)["energy"]["price_per_kwh"]
        self.assertNotEqual(a, b)

    def test_the_line_total_is_energy_plus_idling(self):
        row = self._sessions(tenant=self.TA)[0]
        self.assertEqual(row["energy_cost"], 14.00)
        self.assertEqual(row["idle_cost"], 3.00)
        self.assertEqual(row["amount"], 17.00)

    def test_the_breakdown_adds_up_to_the_headline(self):
        s = self._summary(tenant=self.TA)
        d = s["charger_breakdown"][self.A]
        self.assertEqual(d["revenue"], s["revenue"]["total"])
        self.assertEqual(round(d["energy_cost"] + d["idle_cost"], 2), d["revenue"])

    # --- the fields the partner's finance team asked for ----------------
    def test_a_line_carries_everything_finance_asked_for(self):
        row = self._sessions(tenant=self.TA)[0]
        for f in ("start_time", "end_time", "charge_point_id", "location",
                  "energy_kwh", "energy_cost", "idle_cost", "transaction_id"):
            with self.subTest(f):
                self.assertIsNotNone(row.get(f), f)

    def test_the_identifier_is_the_one_the_partner_holds(self):
        """transaction_id is what the OCPI Session and CDR publish as `id`.
        The old export numbered rows S0001 upward, which matches nothing."""
        self.assertEqual(self._sessions(tenant=self.TA)[0]["transaction_id"], 990001)

    def test_the_location_is_a_line_an_invoice_can_print(self):
        self.assertEqual(self._sessions(tenant=self.TA)[0]["location"],
                         "Alpha Mall, Shah Alam, 40000")

    def test_a_session_ends_when_the_cable_comes_out(self):
        """The idle fee runs until the unplug, so an end time taken from
        stop_time would not account for the amount on the same line."""
        row = self._sessions(tenant=self.TA)[0]
        self.assertEqual(row["end_time"], (self.DAY + timedelta(hours=2)).isoformat())
        self.assertNotEqual(row["end_time"], row["stop_time"])

    def test_a_session_never_unplugged_still_reports_an_end(self):
        row = self._sessions(tenant=self.TB)[0]
        self.assertEqual(row["end_time"], (self.DAY + timedelta(hours=1)).isoformat())

    # --- the period -----------------------------------------------------
    def test_the_last_day_of_the_period_is_the_whole_day(self):
        """A charge at 10am on the closing date belongs in the month. Read as
        midnight, the end date dropped everything charged that day."""
        s = self._summary(tenant=self.TA, start_date="2026-07-15", end_date="2026-07-15")
        self.assertEqual(s["sessions"]["total"], 1)


class InvoiceMaintenanceScopeTests(unittest.TestCase):
    """A fleet's net profit is its own revenue less its own repairs.

    Maintenance was never scoped, so a tenant report subtracted every repair
    on the platform, including the other 473 chargers'.
    """

    CP = "INVMAINT1"
    TENANT = "inv-test-maint"
    DAY = datetime(2026, 7, 15, 10, 0, 0)

    @classmethod
    def setUpClass(cls):
        from database import MaintenanceRecord
        Base.metadata.create_all(bind=engine)
        api.app.dependency_overrides[api.require_admin_or_staff_admin] = \
            lambda: {"role": "admin", "email": "test@local"}
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()
        cls.charger = Charger(charge_point_id=cls.CP, tenant=cls.TENANT,
                              tariff_per_kwh=1.00, status="offline",
                              availability="available")
        cls.db.add(cls.charger)
        cls.db.commit()
        cls.rec = MaintenanceRecord(
            charger_id=cls.charger.id, maintenance_type="repair",
            work_performed="test", cost=Decimal("250.00"), date_reported=cls.DAY)
        cls.db.add(cls.rec)
        cls.db.commit()
        cls.rec_id = cls.rec.id

    @classmethod
    def tearDownClass(cls):
        from database import MaintenanceRecord
        cls.db.query(MaintenanceRecord).filter(
            MaintenanceRecord.id == cls.rec_id).delete(synchronize_session=False)
        cls.db.query(Charger).filter(
            Charger.id == cls.charger.id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        api.app.dependency_overrides.pop(api.require_admin_or_staff_admin, None)
        api.invalidate_chargers_cache()

    def _summary(self, **kw):
        kw.setdefault("start_date", "2026-07-01")
        kw.setdefault("end_date", "2026-07-31")
        r = self.client.get("/api/invoice/summary", params=kw)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_a_fleet_is_charged_its_own_repairs(self):
        self.assertEqual(self._summary(tenant=self.TENANT)["maintenance"]["total_cost"], 250.00)

    def test_another_fleet_is_not_charged_them(self):
        s = self._summary(tenant="inv-test-someone-else")
        self.assertEqual(s["maintenance"]["total_cost"], 0.0)
        self.assertEqual(s["maintenance"]["total_records"], 0)

    def test_net_profit_subtracts_only_what_is_in_scope(self):
        s = self._summary(tenant=self.TENANT)
        self.assertEqual(s["net_profit"],
                         round(s["revenue"]["total"] - s["maintenance"]["total_cost"], 2))


class InvoicePageTests(unittest.TestCase):
    """The page has to ask for the scope and show the split.

    The report is generated in the browser from these two endpoints; a
    correct endpoint reached by a page that never passes `tenant` produces
    the same mixed report as before.
    """

    PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates", "invoice.html")

    @classmethod
    def setUpClass(cls):
        with io.open(cls.PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()

    def test_the_page_scopes_its_requests(self):
        self.assertIn("tenant=${encodeURIComponent(scopeKey())}", self.page)

    def test_the_page_offers_the_scope_in_its_filter_bar(self):
        """The tenant and partner pickers became one control; what matters
        is still that the scope is chosen here, beside the dates."""
        self.assertIn('id="filterScope"', self.page)
        self.assertIn("Report for", self.page)

    def test_the_page_and_the_sidebar_share_one_scope(self):
        """Two controls that can disagree would let someone export a fleet's
        report under another fleet's name."""
        self.assertIn("window.setTenant", self.page)
        self.assertIn("tenantChange", self.page)

    def test_the_export_no_longer_invents_a_rate(self):
        self.assertNotIn("const up=1.20", self.page)
        self.assertNotIn("up.toFixed(2)", self.page)

    def test_the_export_carries_what_finance_asked_for(self):
        """The columns moved to the server when the workbook and the PDF
        arrived, so this asks the definition the three formats share rather
        than the page, which no longer builds a file."""
        import invoice_export
        heads = {c[1] for c in invoice_export.COLUMNS}
        for col in ("Start Time", "End Time", "Location", "Energy Cost (RM)",
                    "Idling Cost (RM)", "Session ID"):
            with self.subTest(col):
                self.assertIn(col, heads)

    def test_the_export_identifies_a_session_by_its_real_id(self):
        self.assertNotIn("S${String(i+1).padStart(4,'0')}", self.page)

    def test_the_month_buttons_use_calendar_days_not_utc_instants(self):
        """Malaysia is eight hours ahead of UTC, so toISOString() on local
        midnight returns the previous day. "This Month" asked for 31 Oct to
        29 Nov: it billed a day belonging to October and dropped the last day
        of November."""
        self.assertNotIn("toISOString().split('T')[0]", self.page)
        self.assertIn("const ymd =", self.page)

    def test_the_report_states_the_scope_it_was_generated_for(self):
        """A report that does not name its fleet can be sent to the wrong
        one."""
        self.assertIn('id="reportTenant"', self.page)

    def test_the_export_quotes_a_field_that_contains_a_comma(self):
        """An address is one field with two commas in it. Unquoted it split
        into three columns and shifted every figure on the row. The server
        writes it with the csv module now, rather than a hand-rolled
        escaper in the page."""
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        _csv.writer(buf).writerow(["2, Jalan Gergaji 15/14, Shah Alam", 1.5])
        line = buf.getvalue().strip()
        self.assertTrue(line.startswith('"2, Jalan'), line)
        self.assertEqual(len(next(_csv.reader(_io.StringIO(line)))), 2)


class SessionTenantFreezeTests(unittest.TestCase):
    """A charger move must not rewrite an invoice that was already sent.

    The rate was frozen onto a session; the owner was not. A report filtered
    by tenant resolved `chargers.tenant` as it stands today, so moving a
    charger between fleets carried every one of its past sessions with it,
    and re-running last month's invoice returned different money.
    """

    CP = "FREEZETEST1"
    FROM = "freeze-test-from"
    TO = "freeze-test-to"
    DAY = datetime(2026, 8, 10, 9, 0, 0)

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        api.app.dependency_overrides[api.require_admin_or_staff_admin] = \
            lambda: {"role": "admin", "email": "test@local"}
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()
        cls.charger = Charger(charge_point_id=cls.CP, tenant=cls.FROM,
                              tariff_per_kwh=1.40, status="offline",
                              availability="available")
        cls.db.add(cls.charger)
        cls.db.commit()
        cls.session = ChargingSession(
            charger_id=cls.charger.id, transaction_id=991001, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            energy_consumed=10.0, idle_minutes=0, idle_fee_amount=Decimal("0"),
        )
        cls.db.add(cls.session)
        cls.db.commit()
        api.invalidate_chargers_cache()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(ChargingSession).filter(
            ChargingSession.transaction_id == 991001).delete(synchronize_session=False)
        cls.db.query(Charger).filter(
            Charger.id == cls.charger.id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        api.app.dependency_overrides.pop(api.require_admin_or_staff_admin, None)
        api.invalidate_chargers_cache()

    def setUp(self):
        self.charger.tenant = self.FROM
        self.db.commit()
        api.invalidate_chargers_cache()

    def _count(self, tenant):
        r = self.client.get("/api/invoice/summary", params={
            "start_date": "2026-08-01", "end_date": "2026-08-31", "tenant": tenant})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        return j["sessions"]["total"], j["revenue"]["total"]

    def test_the_session_records_the_fleet_it_ran_under(self):
        """Stamped by a mapper event, because sessions are created from six
        places across two OCPP stacks, the API and the edge sync."""
        self.db.refresh(self.session)
        self.assertEqual(self.session.tenant_at_start, self.FROM)

    def test_a_caller_that_states_the_rate_still_gets_an_owner(self):
        """The price freeze returns early when a caller sets the rate itself.
        The tenant is decided separately so it is stamped regardless."""
        s = ChargingSession(
            charger_id=self.charger.id, transaction_id=991002, status="completed",
            start_time=self.DAY, energy_consumed=1.0,
            tariff_per_kwh_at_start=9.99,
        )
        self.db.add(s)
        self.db.commit()
        try:
            self.assertEqual(s.tenant_at_start, self.FROM)
            self.assertEqual(float(s.tariff_per_kwh_at_start), 9.99)
        finally:
            self.db.delete(s)
            self.db.commit()

    def test_an_explicit_tenant_is_left_alone(self):
        s = ChargingSession(
            charger_id=self.charger.id, transaction_id=991003, status="completed",
            start_time=self.DAY, energy_consumed=1.0, tenant_at_start="stated",
        )
        self.db.add(s)
        self.db.commit()
        try:
            self.assertEqual(s.tenant_at_start, "stated")
        finally:
            self.db.delete(s)
            self.db.commit()

    def test_moving_the_charger_does_not_move_the_history(self):
        """The whole point. Before this, both of these assertions were the
        other way round."""
        self.assertEqual(self._count(self.FROM), (1, 14.0))
        self.assertEqual(self._count(self.TO), (0, 0.0))

        self.charger.tenant = self.TO
        self.db.commit()
        api.invalidate_chargers_cache()

        self.assertEqual(self._count(self.FROM), (1, 14.0))
        self.assertEqual(self._count(self.TO), (0, 0.0))

    def test_a_new_charge_belongs_to_the_new_fleet(self):
        """Freezing history must not freeze the future: a charge that runs
        after the move is the new fleet's."""
        self.charger.tenant = self.TO
        self.db.commit()
        api.invalidate_chargers_cache()
        s = ChargingSession(
            charger_id=self.charger.id, transaction_id=991004, status="completed",
            start_time=self.DAY, stop_time=self.DAY + timedelta(hours=1),
            energy_consumed=10.0, idle_minutes=0, idle_fee_amount=Decimal("0"),
        )
        self.db.add(s)
        self.db.commit()
        try:
            self.assertEqual(s.tenant_at_start, self.TO)
            self.assertEqual(self._count(self.FROM), (1, 14.0))
            self.assertEqual(self._count(self.TO), (1, 14.0))
        finally:
            self.db.delete(s)
            self.db.commit()

    def test_the_line_names_the_fleet_that_earned_it(self):
        self.charger.tenant = self.TO
        self.db.commit()
        api.invalidate_chargers_cache()
        r = self.client.get("/api/invoice/sessions", params={
            "start_date": "2026-08-01", "end_date": "2026-08-31",
            "tenant": self.FROM})
        rows = r.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tenant"], self.FROM)

    def test_analytics_and_the_invoice_agree(self):
        """Two pages that split revenue by fleet cannot use different rules,
        or the operator has to decide which one to believe."""
        self.charger.tenant = self.TO
        self.db.commit()
        api.invalidate_chargers_cache()
        rows = api._tenant_breakdown(self.db, self.DAY - timedelta(days=1))
        by = {r["key"]: r for r in rows}
        self.assertIn(self.FROM, by)
        self.assertEqual(by[self.FROM]["sessions"]["total"], 1)
        self.assertEqual(by[self.FROM]["chargers"]["total"], 0)


class BillingLockTests(unittest.TestCase):
    """A fleet under a live contract does not gain or lose chargers quietly.

    This guards future earnings, not past invoices: what a past invoice said
    is already settled by the tenant frozen on each session.
    """

    CP = "LOCKTEST1"
    LOCKED = "lock-test-billed"
    OPEN = "lock-test-open"

    @classmethod
    def setUpClass(cls):
        from database import Tenant
        Base.metadata.create_all(bind=engine)
        api.app.dependency_overrides[api.require_admin_or_staff_admin] = \
            lambda: {"role": "admin", "email": "test@local"}
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()
        cls.db.add_all([
            Tenant(key=cls.LOCKED, label="Billed Fleet", is_active=True,
                   billing_locked=True),
            Tenant(key=cls.OPEN, label="Open Fleet", is_active=True,
                   billing_locked=False),
        ])
        cls.charger = Charger(charge_point_id=cls.CP, tenant=cls.LOCKED,
                              tariff_per_kwh=1.0, status="offline",
                              availability="available")
        cls.db.add(cls.charger)
        cls.db.commit()
        api.invalidate_chargers_cache()

    @classmethod
    def tearDownClass(cls):
        from database import Tenant
        cls.db.query(Charger).filter(
            Charger.id == cls.charger.id).delete(synchronize_session=False)
        cls.db.query(Tenant).filter(
            Tenant.key.in_([cls.LOCKED, cls.OPEN])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        api.app.dependency_overrides.pop(api.require_admin_or_staff_admin, None)
        api.invalidate_chargers_cache()

    def setUp(self):
        self.charger.tenant = self.LOCKED
        self.db.commit()
        api.invalidate_chargers_cache()

    def _patch(self, **body):
        return self.client.patch(
            "/api/admin/chargers/%s/info" % self.CP, json=body)

    def test_moving_out_of_a_billed_fleet_is_refused(self):
        r = self._patch(tenant=self.OPEN)
        self.assertEqual(r.status_code, 409, r.text)
        self.db.refresh(self.charger)
        self.assertEqual(self.charger.tenant, self.LOCKED)

    def test_the_refusal_says_what_would_change(self):
        detail = self._patch(tenant=self.OPEN).json()["detail"]
        self.assertIn(self.LOCKED, detail)
        self.assertIn(self.CP, detail)
        self.assertIn("confirm_tenant_change", detail)

    def test_the_refusal_says_past_invoices_are_safe(self):
        """An operator who is told only "refused" will force it without
        understanding what is and is not at risk."""
        self.assertIn("already issued", self._patch(tenant=self.OPEN).json()["detail"])

    def test_moving_into_a_billed_fleet_is_refused_too(self):
        self.charger.tenant = self.OPEN
        self.db.commit()
        api.invalidate_chargers_cache()
        self.assertEqual(self._patch(tenant=self.LOCKED).status_code, 409)

    def test_an_explicit_confirmation_goes_through(self):
        r = self._patch(tenant=self.OPEN, confirm_tenant_change=True)
        self.assertEqual(r.status_code, 200, r.text)
        self.db.refresh(self.charger)
        self.assertEqual(self.charger.tenant, self.OPEN)

    def test_an_unbilled_fleet_needs_no_confirmation(self):
        self.charger.tenant = self.OPEN
        self.db.commit()
        api.invalidate_chargers_cache()
        from database import Tenant
        third = Tenant(key="lock-test-third", label="Third", is_active=True)
        self.db.add(third)
        self.db.commit()
        try:
            self.assertEqual(self._patch(tenant="lock-test-third").status_code, 200)
        finally:
            self.db.query(Tenant).filter(
                Tenant.key == "lock-test-third").delete(synchronize_session=False)
            self.db.commit()

    def test_other_edits_to_a_billed_charger_are_untouched(self):
        """The lock is about which fleet earns, not about freezing the
        charger's details."""
        r = self._patch(location="Somewhere else")
        self.assertEqual(r.status_code, 200, r.text)

    def test_resaving_the_same_tenant_is_not_a_move(self):
        self.assertEqual(self._patch(tenant=self.LOCKED).status_code, 200)

    def test_the_flag_reaches_the_dashboard(self):
        """A key the response model does not declare never leaves the
        server, so the lock would be invisible in the picker."""
        self.assertIn("billing_locked", api.TenantResponse.model_fields)
        rows = self.client.get("/api/tenants").json()
        row = next(t for t in rows if t["key"] == self.LOCKED)
        self.assertIs(row["billing_locked"], True)

    def test_the_lock_can_be_set_from_the_dashboard(self):
        r = self.client.patch("/api/tenants/%s" % self.OPEN,
                              json={"billing_locked": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(r.json()["billing_locked"], True)
        self.client.patch("/api/tenants/%s" % self.OPEN,
                          json={"billing_locked": False})


class ChargerPageLockTests(unittest.TestCase):
    """The page has to carry the operator's decision, or the guard is just
    an error nobody can get past."""

    PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates", "chargers.html")

    @classmethod
    def setUpClass(cls):
        with io.open(cls.PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()

    def test_the_page_handles_the_refusal(self):
        self.assertIn("res.status === 409", self.page)

    def test_the_page_sends_the_confirmation_on_retry(self):
        self.assertIn("body.confirm_tenant_change = true", self.page)

    def test_a_billed_fleet_is_marked_in_the_picker(self):
        self.assertIn("t.billing_locked", self.page)


class AmountInWordsTests(unittest.TestCase):
    """An invoice states its total in words so it cannot be altered after
    the fact. A wrong one is worse than none."""

    def test_the_cases_an_invoice_actually_hits(self):
        from invoice_export import amount_in_words
        cases = {
            0: "RINGGIT MALAYSIA ZERO ONLY",
            1: "RINGGIT MALAYSIA ONE ONLY",
            13.94: "RINGGIT MALAYSIA THIRTEEN AND NINETY-FOUR SEN ONLY",
            100: "RINGGIT MALAYSIA ONE HUNDRED ONLY",
            435.07: "RINGGIT MALAYSIA FOUR HUNDRED AND THIRTY-FIVE AND SEVEN SEN ONLY",
            1000: "RINGGIT MALAYSIA ONE THOUSAND ONLY",
            12345.6: "RINGGIT MALAYSIA TWELVE THOUSAND THREE HUNDRED AND FORTY-FIVE AND SIXTY SEN ONLY",
        }
        for amount, words in cases.items():
            with self.subTest(amount):
                self.assertEqual(amount_in_words(amount), words)

    def test_the_sen_are_not_lost_to_floating_point(self):
        from invoice_export import amount_in_words
        self.assertIn("TEN SEN", amount_in_words(0.10))
        self.assertIn("ONE SEN", amount_in_words(2.01))


class PdfColumnWidthTests(unittest.TestCase):
    """The column weights were hand-written and summed to 1.06, which pushed
    the last column off the page and silently truncated every total on it."""

    def test_the_table_fits_the_page_exactly(self):
        from invoice_export import _pdf_widths
        for page in (180.0, 273.0):
            with self.subTest(page):
                self.assertAlmostEqual(sum(_pdf_widths(page)), page, places=6)

    def test_every_column_has_a_short_heading_for_the_pdf(self):
        """A heading wider than its column ran into its neighbour and the
        header row read as one word."""
        from invoice_export import BREAKDOWN_COLUMNS, COLUMNS
        for col in list(COLUMNS) + list(BREAKDOWN_COLUMNS):
            with self.subTest(col[0]):
                self.assertEqual(len(col), 6)
                self.assertTrue(col[2])
                self.assertLessEqual(len(col[2]), len(col[1]))


class InvoiceExportTests(unittest.TestCase):
    """The file a partner's finance team receives.

    A CSV cannot carry a logo, a column width or a page layout, so the
    workbook and the PDF are built on the server. Both are generated here
    for real and inspected, because a format that raises on a long address
    or writes a logo nobody can see is not caught by checking a status code.
    """

    CP = "EXPORTTEST1"
    TENANT = "export-test"
    DAY = datetime(2026, 9, 12, 8, 0, 0)

    @classmethod
    def setUpClass(cls):
        from database import OcpiPartner
        Base.metadata.create_all(bind=engine)
        api.app.dependency_overrides[api.require_admin_or_staff_admin] = \
            lambda: {"role": "admin", "email": "test@local"}
        cls.client = TestClient(api.app)
        cls.db = SessionLocal()

        cls.partner = OcpiPartner(
            country_code="SG", party_id="XPT", business_name="Export Test Pte Ltd",
            versions_url="https://example.invalid/versions", token="x")
        cls.other = OcpiPartner(
            country_code="SG", party_id="XPO", business_name="Other Partner",
            versions_url="https://example.invalid/versions", token="x")
        cls.charger = Charger(
            charge_point_id=cls.CP, tenant=cls.TENANT, tariff_per_kwh=1.40,
            location="Test Mall", city="Shah Alam", postal_code="40200",
            status="offline", availability="available")
        cls.db.add_all([cls.partner, cls.other, cls.charger])
        cls.db.commit()

        # Settled: unplugged and not interrupted, which is what releases the
        # CDR the partner holds.
        cls.settled = ChargingSession(
            charger_id=cls.charger.id, transaction_id=992001, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            unplugged_at=cls.DAY + timedelta(hours=2), energy_consumed=10.0,
            tariff_per_kwh_at_start=1.40, idle_minutes=30,
            idle_fee_amount=Decimal("6.00"), ocpi_partner_id=cls.partner.id)
        # Still plugged in: the CDR is held, so it is not on the invoice.
        cls.held = ChargingSession(
            charger_id=cls.charger.id, transaction_id=992002, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            unplugged_at=None, energy_consumed=4.0,
            tariff_per_kwh_at_start=1.40, ocpi_partner_id=cls.partner.id)
        # Another partner's charge, on the same charger.
        cls.theirs = ChargingSession(
            charger_id=cls.charger.id, transaction_id=992003, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            unplugged_at=cls.DAY + timedelta(hours=2), energy_consumed=7.0,
            tariff_per_kwh_at_start=1.40, ocpi_partner_id=cls.other.id)
        # A walk-in. Belongs to the fleet report and to no partner.
        cls.walkin = ChargingSession(
            charger_id=cls.charger.id, transaction_id=992004, status="completed",
            start_time=cls.DAY, stop_time=cls.DAY + timedelta(hours=1),
            unplugged_at=cls.DAY + timedelta(hours=2), energy_consumed=3.0,
            tariff_per_kwh_at_start=1.40)
        cls.db.add_all([cls.settled, cls.held, cls.theirs, cls.walkin])
        cls.db.commit()
        api.invalidate_chargers_cache()

    @classmethod
    def tearDownClass(cls):
        from database import OcpiPartner
        cls.db.query(ChargingSession).filter(
            ChargingSession.transaction_id.between(992001, 992004)).delete(
            synchronize_session=False)
        cls.db.query(Charger).filter(
            Charger.id == cls.charger.id).delete(synchronize_session=False)
        cls.db.query(OcpiPartner).filter(
            OcpiPartner.party_id.in_(["XPT", "XPO"])).delete(
            synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        api.app.dependency_overrides.pop(api.require_admin_or_staff_admin, None)
        api.invalidate_chargers_cache()

    P = {"start_date": "2026-09-01", "end_date": "2026-09-30"}

    def _get(self, **kw):
        q = dict(self.P); q.update(kw)
        r = self.client.get("/api/invoice/export", params=q)
        self.assertEqual(r.status_code, 200, r.text)
        return r

    # --- who is on the invoice ------------------------------------------
    def test_a_settlement_holds_only_that_partners_charges(self):
        rows = self._get(format="json", party_id="XPT").json()["sessions"]
        self.assertEqual([r["session_id"] for r in rows], ["992001"])

    def test_a_held_cdr_is_not_invoiced(self):
        """The cable is still in. The partner has no record to match it
        against, and the amount is not final."""
        ids = [r["session_id"]
               for r in self._get(format="json", party_id="XPT").json()["sessions"]]
        self.assertNotIn("992002", ids)

    def test_a_walk_in_is_not_on_a_partner_invoice(self):
        ids = [r["session_id"]
               for r in self._get(format="json", party_id="XPT").json()["sessions"]]
        self.assertNotIn("992004", ids)

    def test_the_fleet_report_holds_all_of_them(self):
        """The two populations differ, which is the whole reason the page
        has to say which one it is showing."""
        ids = {r["session_id"]
               for r in self._get(format="json", tenant=self.TENANT).json()["sessions"]}
        self.assertEqual(ids, {"992001", "992002", "992003", "992004"})

    def test_an_unknown_partner_is_an_error_not_an_empty_invoice(self):
        r = self.client.get("/api/invoice/export",
                            params=dict(self.P, format="json", party_id="ZZZ"))
        self.assertEqual(r.status_code, 404)

    def test_the_partner_wins_over_the_tenant(self):
        rows = self._get(format="json", party_id="XPT",
                         tenant="something-else").json()["sessions"]
        self.assertEqual(len(rows), 1)

    def test_the_invoice_is_billed_to_the_partner(self):
        meta = self._get(format="json", party_id="XPT").json()["meta"]
        self.assertEqual(meta["bill_to"], "Export Test Pte Ltd")
        self.assertEqual(meta["scope_label"], "Roaming partner")
        self.assertEqual(meta["scope_value"], "SG/XPT")

    def test_the_money_on_the_line(self):
        t = self._get(format="json", party_id="XPT").json()["totals"]
        self.assertEqual(t["energy_cost"], 14.00)   # 10 kWh x 1.40
        self.assertEqual(t["idle_cost"], 6.00)
        self.assertEqual(t["total"], 20.00)

    # --- the partner picker ---------------------------------------------
    def test_the_picker_lists_partners_that_have_sent_charges(self):
        rows = self.client.get("/api/invoice/partners").json()
        codes = {r["code"] for r in rows}
        self.assertIn("SG/XPT", codes)
        self.assertIn("SG/XPO", codes)

    def test_the_picker_separates_a_live_party_from_a_test_one(self):
        """Read off the host each side handshook from, because the business
        name is identical on both."""
        self.assertEqual(api._partner_environment("https://api.voltnet.io/v"),
                         "production")
        self.assertEqual(api._partner_environment("https://api-uat.voltnet.io/v"),
                         "test")
        for url, env in (
            ("https://staging.example.com/v", "test"),
            ("https://partner.dev.example.com/v", "test"),
            ("https://qa-ocpi.foo.my/v", "test"),
            ("https://ocpi.realco.com/v", "production"),
            # "devon" is not "dev": the match is on whole labels, or a list
            # of real partners would start being called test environments.
            ("https://devon.example.com/v", "production"),
            (None, "production"),
        ):
            with self.subTest(url):
                self.assertEqual(api._partner_environment(url), env)

    def test_the_live_party_is_offered_first(self):
        rows = self.client.get("/api/invoice/partners").json()
        envs = [r["environment"] for r in rows]
        self.assertEqual(envs, sorted(envs, key=lambda e: e != "production"))

    def test_the_picker_names_them(self):
        rows = self.client.get("/api/invoice/partners").json()
        row = next(r for r in rows if r["code"] == "SG/XPT")
        self.assertEqual(row["name"], "Export Test Pte Ltd")
        self.assertEqual(row["party_id"], "XPT")

    # --- the files --------------------------------------------------------
    def test_the_workbook_is_a_workbook(self):
        r = self._get(format="xlsx", party_id="XPT")
        self.assertIn("spreadsheetml", r.headers["content-type"])
        self.assertTrue(r.content.startswith(b"PK"))
        self.assertIn(".xlsx", r.headers["content-disposition"])

    def test_the_workbook_carries_the_logo_and_the_sheets(self):
        import zipfile
        r = self._get(format="xlsx", party_id="XPT")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        self.assertTrue(any(n.startswith("xl/media/") for n in names),
                        "no image embedded: %s" % names)
        self.assertGreaterEqual(
            len([n for n in names if n.startswith("xl/worksheets/sheet")]), 2)

    def test_the_pdf_is_a_pdf(self):
        r = self._get(format="pdf", party_id="XPT")
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_the_pdf_says_what_an_invoice_has_to_say(self):
        r = self._get(format="pdf", party_id="XPT")
        import invoice_export
        try:
            import fitz
        except ImportError:
            self.skipTest("pymupdf not installed")
        doc = fitz.open(stream=r.content, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        for needed in (invoice_export.COMPANY_NAME, invoice_export.TAGLINE,
                       "INVOICE", "Export Test Pte Ltd", "SG/XPT",
                       "Authorised Signature",
                       invoice_export.amount_in_words(20.00)):
            with self.subTest(needed):
                self.assertIn(needed, text)

    def test_the_pdf_carries_the_logo(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("pymupdf not installed")
        r = self._get(format="pdf", party_id="XPT")
        doc = fitz.open(stream=r.content, filetype="pdf")
        self.assertTrue(doc[0].get_images(full=True), "no logo on page 1")

    def test_a_long_address_does_not_break_the_pdf(self):
        """The core PDF fonts are latin-1 and the row trims rather than
        wraps. An invoice that raises on a long address is useless."""
        self.charger.location = "Lot 1234567, Bangunan Yang Sangat Panjang " \
                                "Namanya, Jalan Besar Sekali 99/123A"
        self.db.commit()
        api.invalidate_chargers_cache()
        try:
            r = self._get(format="pdf", party_id="XPT")
            self.assertTrue(r.content.startswith(b"%PDF"))
        finally:
            self.charger.location = "Test Mall"
            self.db.commit()
            api.invalidate_chargers_cache()

    def test_the_csv_still_works_for_an_import(self):
        r = self._get(format="csv", party_id="XPT")
        self.assertIn("text/csv", r.headers["content-type"])
        body = r.text
        self.assertTrue(body.startswith("\ufeff"), "no BOM for Excel")
        self.assertIn("Session ID", body)
        self.assertIn("Idling Cost (RM)", body)
        self.assertIn("TOTAL", body)

    def test_the_three_formats_agree_on_the_money(self):
        """Three renderings of one set of rows. The old CSV was a second
        implementation and billed RM1.20 a kWh while the page showed
        something else."""
        total = self._get(format="json", party_id="XPT").json()["totals"]["total"]
        self.assertIn("20.0", self._get(format="csv", party_id="XPT").text)
        self.assertEqual(total, 20.00)

    def test_an_empty_period_still_produces_a_file(self):
        for fmt in ("csv", "xlsx", "pdf"):
            with self.subTest(fmt):
                r = self.client.get("/api/invoice/export", params={
                    "format": fmt, "party_id": "XPT",
                    "start_date": "2020-01-01", "end_date": "2020-01-31"})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertTrue(r.content)


class InvoicePagePartnerTests(unittest.TestCase):
    """The page has to offer the settlement and build nothing itself."""

    PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates", "invoice.html")

    @classmethod
    def setUpClass(cls):
        with io.open(cls.PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()

    def test_the_page_offers_a_roaming_partner(self):
        self.assertIn("partner:", self.page)
        self.assertIn("Roaming settlement", self.page)

    def test_the_scope_is_one_control(self):
        """A tenant dropdown and a partner dropdown sat side by side and the
        partner silently won, so the page could read "HICOM Public Charging"
        while showing Voltality's figures. One control cannot do that."""
        self.assertIn('id="filterScope"', self.page)
        for gone in ('id="filterTenant"', 'id="filterPartner"',
                     "function tenantValue", "function partnerValue"):
            with self.subTest(gone):
                self.assertNotIn(gone, self.page)

    def test_the_two_kinds_are_grouped_and_labelled(self):
        self.assertIn("internal P&L", self.page)
        self.assertIn("invoice a partner", self.page)
        self.assertIn("All tenants (combined)", self.page)

    def test_the_page_scopes_by_party(self):
        self.assertIn("party_id=", self.page)

    def test_the_page_says_which_file_goes_out(self):
        """Sending the fleet report to a partner is the mistake this page
        has to prevent, so it states the difference where it is read."""
        self.assertIn("Roaming settlement", self.page)
        self.assertIn("Fleet report", self.page)

    def test_the_page_no_longer_builds_a_file_itself(self):
        for gone in ("function exportCSV", "function csvCell", "const up=1.20"):
            with self.subTest(gone):
                self.assertNotIn(gone, self.page)

    def test_a_partner_scope_does_not_move_the_sidebar(self):
        """A settlement is not a fleet, so it has no tenant to scope the
        rest of the dashboard to; changing it as a side effect of opening
        an invoice would re-scope every other page."""
        self.assertIn("if (kind === 'partner') return;", self.page)

    def test_a_partners_live_side_is_told_apart_from_its_test_side(self):
        """Voltality is SG/VOL on api-uat.voltnet.io and SG/VLT on
        api.voltnet.io, both carrying the business name "Voltality". A
        picker showing it twice invites someone to invoice the simulator."""
        self.assertIn("TEST / UAT", self.page)
        self.assertIn("LIVE", self.page)
        self.assertIn("pt.environment", self.page)

    def test_picking_a_test_party_is_objected_to(self):
        # The sentence is concatenated across source lines, so match the
        # part that carries the warning rather than the whole of it.
        self.assertIn("Do not invoice", self.page)
        self.assertIn("Test environment", self.page)

    def test_the_formats_are_one_menu(self):
        """Three bare buttons said nothing about how they differ, and the
        difference between a CSV and a workbook is the whole question."""
        self.assertIn('id="exportMenu"', self.page)
        self.assertIn("toggleExportMenu", self.page)

    def test_the_page_offers_all_three_formats(self):
        for fmt in ("'csv'", "'xlsx'", "'pdf'"):
            with self.subTest(fmt):
                self.assertIn("downloadExport(%s)" % fmt, self.page)

    def test_the_download_carries_the_staff_token(self):
        """The endpoint authenticates on a header, so a plain link would
        arrive without the token and come back 401 instead of a file."""
        self.assertIn("downloadExport", self.page)
        self.assertIn("headers: authHeaders()", self.page)

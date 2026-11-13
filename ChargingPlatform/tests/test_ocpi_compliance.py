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
import math
import re
import unittest
from datetime import datetime, timedelta

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
        router._outbound_token = lambda: self.TOKEN
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
        router._outbound_token = lambda: None
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
        router._outbound_token = lambda: "tok"
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

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
    # The CDR's 2.1.1 fields are deliberately still sent: Voltality's billing
    # reads them today, and this is a live integration, so the correct names
    # were added beside them rather than swapped in. They come out once
    # Voltality confirm they have migrated.
    CDR_DEPRECATED = {"auth_id", "location_id", "evse_uid", "connector_id", "tariff_id"}

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
        # The 2.1.1 spellings ride along until Voltality have migrated, and
        # must carry the same values.
        self.assertEqual(conn["voltage"], conn["max_voltage"])
        self.assertEqual(conn["amperage"], conn["max_amperage"])

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

    def test_session_still_carries_the_old_names_during_migration(self):
        # Renaming a field out from under a running partner breaks it with no
        # warning. Both spellings go out until they say they have migrated.
        from ocpi.router import _build_session_dict
        d = _build_session_dict(self.sess)
        self.assertEqual(d["start_datetime"], d["start_date_time"])
        self.assertEqual(d["end_datetime"], d["end_date_time"])

    def test_cdr_has_every_required_field(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertIsNotNone(d)
        self.assertEqual(SpecFieldTests.CDR_REQUIRED - set(d), set())

    def test_cdr_still_carries_the_old_fields_during_migration(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        self.assertEqual(SpecFieldTests.CDR_DEPRECATED - set(d), set())
        # And the duplicates must agree, or a partner reading the old name
        # bills against a different figure from one reading the new one.
        self.assertEqual(d["start_datetime"], d["start_date_time"])
        self.assertEqual(d["location_id"], d["cdr_location"]["id"])
        self.assertEqual(d["evse_uid"], d["cdr_location"]["evse_uid"])
        self.assertEqual(d["connector_id"], d["cdr_location"]["connector_id"])

    def test_cdr_location_is_complete(self):
        from ocpi.router import _build_cdr_dict
        loc = _build_cdr_dict(self.sess)["cdr_location"]
        self.assertEqual(SpecFieldTests.CDR_LOCATION_REQUIRED - set(loc), set())

    def test_charging_periods_use_the_2_2_1_timestamp_name(self):
        from ocpi.router import _build_cdr_dict
        for period in _build_cdr_dict(self.sess)["charging_periods"]:
            self.assertIn("start_date_time", period)
            self.assertEqual(period["start_datetime"], period["start_date_time"])

    def test_idle_shows_up_as_a_parking_dimension(self):
        from ocpi.router import _build_cdr_dict
        d = _build_cdr_dict(self.sess)
        dims = {x["type"] for p in d["charging_periods"] for x in p["dimensions"]}
        self.assertIn("PARKING_TIME", dims)
        self.assertGreater(d["total_parking_cost"]["excl_vat"], 0)


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
        self.db.query(Charger).filter(
            Charger.charge_point_id.in_(["ADDRTEST", "NOADDRTEST"])
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def test_the_chargers_own_address_is_published(self):
        from ocpi.router import _build_location_dict
        loc = _build_location_dict(self.sited)
        self.assertEqual(loc["address"], "Seksyen 15, Shah Alam, Selangor")
        self.assertAlmostEqual(loc["coordinates"]["latitude"], 3.06566)
        self.assertAlmostEqual(loc["coordinates"]["longitude"], 101.533168)

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

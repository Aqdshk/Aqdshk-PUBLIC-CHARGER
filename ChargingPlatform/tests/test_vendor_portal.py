"""Vendor test portal.

A vendor account exists so a charger manufacturer can be let onto the platform
without being handed the administrator login. Everything that matters about it
is therefore a boundary, and those are what is pinned here:

  - a vendor reaches the charge points listed on the account and no others,
    for reads and for every command
  - switching an account off, or its expiry passing, ends a session that is
    already signed in
  - frames are recorded only for chargers under test, and the tap can never
    stop a frame from being handled
  - the checklist says "pass" only on evidence in the trace
"""
import asyncio
import json
import unittest
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import ocpp_server  # noqa: E402
import ocpp_trace  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargingSession, OcppMessageLog, SessionLocal, User, VendorAccount,
    _now_myt, _utcnow, engine,
)
from security import create_tokens  # noqa: E402

MINE = "VT-MINE-001"
OTHER = "VT-OTHER-001"


class _FakeChargePoint:
    """Stands in for a connected charger; records what it was asked to do."""

    def __init__(self):
        self.calls = []

    async def reset(self, type):
        self.calls.append(("reset", type))
        return SimpleNamespace(status="Accepted")

    async def trigger_message(self, requested_message, connector_id=None):
        self.calls.append(("trigger", requested_message))
        return SimpleNamespace(status="Accepted")

    async def update_firmware(self, location, retrieve_date, retries=None, retry_interval=None):
        self.calls.append(("firmware", location))
        return SimpleNamespace()

    async def get_configuration(self, keys=None):
        self.calls.append(("get_configuration", keys))
        return SimpleNamespace(
            configuration_key=[{"key": "HeartbeatInterval", "readonly": False, "value": "30"}],
            unknown_key=[],
        )


class VendorPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        admin = User(email="vendor-admin@example.com", password_hash="x", is_admin=True, is_active=True)
        db.add(admin)
        db.add_all([
            Charger(charge_point_id=MINE, vendor="Acme", model="AC22", firmware_version="1.0.0",
                    status="online", availability="available"),
            Charger(charge_point_id=OTHER, status="online", availability="available"),
        ])
        db.commit()
        db.refresh(admin)
        cls.admin = {"Authorization": "Bearer " + create_tokens(admin)["access_token"]}
        db.close()
        cls.client = TestClient(api.app)

        r = cls.client.post("/api/admin/vendors", headers=cls.admin, json={
            "company": "Acme Chargers", "email": "Tester@Acme.example", "charge_point_ids": f"{MINE}, VT-NOT-YET-1",
        })
        assert r.status_code == 201, r.text
        cls.vendor_id = r.json()["id"]
        cls.password = r.json()["password"]
        cls.email = "tester@acme.example"
        ocpp_trace.invalidate()

    def _login(self):
        # The login limiter is real and per address; the suite signs in far
        # more often than a person would.
        api._RATE_LIMIT_BUCKETS.clear()
        r = self.client.post("/api/vendor/login", json={"email": self.email, "password": self.password})
        self.assertEqual(r.status_code, 200, r.text)
        return {"X-Vendor-Token": r.json()["token"]}

    # ── Accounts ──

    def test_01_admin_endpoints_need_an_admin(self):
        self.assertIn(self.client.get("/api/admin/vendors").status_code, (401, 403))
        r = self.client.post("/api/admin/vendors", json={"company": "x", "email": "a@b.co"})
        self.assertIn(r.status_code, (401, 403))
        # A vendor token is not an admin token.
        self.assertIn(self.client.get("/api/admin/vendors", headers=self._login()).status_code, (401, 403))

    def test_02_password_is_returned_once_and_never_listed(self):
        r = self.client.get("/api/admin/vendors", headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        row = next(v for v in r.json()["vendors"] if v["id"] == self.vendor_id)
        self.assertNotIn("password", row)
        self.assertNotIn("password_hash", row)
        self.assertEqual(row["charge_point_ids"], [MINE, "VT-NOT-YET-1"])

    def test_03_login_rejects_wrong_password(self):
        r = self.client.post("/api/vendor/login", json={"email": self.email, "password": "wrong-password"})
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/vendor/login", json={"email": "nobody@acme.example", "password": "x"})
        self.assertEqual(r.status_code, 401)

    def test_04_bad_charge_point_id_is_refused(self):
        r = self.client.post("/api/admin/vendors", headers=self.admin, json={
            "company": "Bad", "email": "bad@acme.example", "charge_point_ids": "ok-123, has space/slash",
        })
        self.assertEqual(r.status_code, 400, r.text)

    # ── Scope ──

    def test_10_overview_lists_only_assigned_chargers(self):
        r = self.client.get("/api/vendor/overview", headers=self._login())
        self.assertEqual(r.status_code, 200, r.text)
        ids = [c["charge_point_id"] for c in r.json()["chargers"]]
        self.assertEqual(ids, [MINE, "VT-NOT-YET-1"])
        by_id = {c["charge_point_id"]: c for c in r.json()["chargers"]}
        self.assertTrue(by_id[MINE]["registered"])
        self.assertEqual(by_id[MINE]["firmware_version"], "1.0.0")
        # A pile id can be assigned before the charger has ever connected.
        self.assertFalse(by_id["VT-NOT-YET-1"]["registered"])

    def test_11_every_route_refuses_someone_elses_charger(self):
        h = self._login()
        fake = _FakeChargePoint()
        ocpp_server.active_charge_points[OTHER] = fake
        try:
            for path in ("live", "checklist", "sessions"):
                r = self.client.get(f"/api/vendor/chargers/{OTHER}/{path}", headers=h)
                self.assertEqual(r.status_code, 404, path)
            posts = {
                "start": {"connector_id": 1},
                "stop": {},
                "reset": {"type": "Hard"},
                "trigger": {"requested_message": "Heartbeat"},
                "unlock": {"connector_id": 1},
                "configuration/get": {},
                "configuration/set": {"key": "HeartbeatInterval", "value": "1"},
                "firmware": {"location": "http://example.com/fw.bin"},
            }
            for path, body in posts.items():
                r = self.client.post(f"/api/vendor/chargers/{OTHER}/{path}", headers=h, json=body)
                self.assertEqual(r.status_code, 404, f"{path}: {r.text}")
            self.assertEqual(fake.calls, [], "a command reached a charger outside the account")
        finally:
            ocpp_server.active_charge_points.pop(OTHER, None)

    def test_12_requests_without_a_token_are_refused(self):
        self.assertEqual(self.client.get("/api/vendor/overview").status_code, 401)
        self.assertEqual(self.client.get(f"/api/vendor/chargers/{MINE}/live").status_code, 401)
        r = self.client.post(f"/api/vendor/chargers/{MINE}/reset", json={"type": "Soft"})
        self.assertEqual(r.status_code, 401)

    # ── Commands on the vendor's own charger ──

    def test_20_commands_reach_own_charger(self):
        h = self._login()
        fake = _FakeChargePoint()
        ocpp_server.active_charge_points[MINE] = fake
        try:
            r = self.client.post(f"/api/vendor/chargers/{MINE}/reset", headers=h, json={"type": "Soft"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertTrue(r.json()["success"])

            r = self.client.post(f"/api/vendor/chargers/{MINE}/firmware", headers=h,
                                 json={"location": "http://example.com/fw-2.0.bin"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertTrue(r.json()["success"])

            r = self.client.post(f"/api/vendor/chargers/{MINE}/configuration/get", headers=h, json={})
            self.assertEqual(r.json()["configuration"][0]["key"], "HeartbeatInterval")

            self.assertEqual(
                [c[0] for c in fake.calls], ["reset", "firmware", "get_configuration"],
            )
        finally:
            ocpp_server.active_charge_points.pop(MINE, None)

    def test_21_command_to_a_disconnected_charger_says_so(self):
        r = self.client.post(f"/api/vendor/chargers/{MINE}/reset", headers=self._login(), json={"type": "Soft"})
        self.assertEqual(r.status_code, 409, r.text)

    def test_22_firmware_location_must_be_a_url(self):
        h = self._login()
        ocpp_server.active_charge_points[MINE] = _FakeChargePoint()
        try:
            r = self.client.post(f"/api/vendor/chargers/{MINE}/firmware", headers=h,
                                 json={"location": "file:///etc/passwd"})
            self.assertEqual(r.status_code, 400, r.text)
            r = self.client.post(f"/api/vendor/chargers/{MINE}/trigger", headers=h,
                                 json={"requested_message": "SomethingElse"})
            self.assertEqual(r.status_code, 400, r.text)
        finally:
            ocpp_server.active_charge_points.pop(MINE, None)

    # ── Trace ──

    def test_30_only_watched_chargers_are_recorded(self):
        ocpp_trace.invalidate()
        ocpp_trace.record(MINE, "in", '[2,"t30-a","Heartbeat",{}]')
        ocpp_trace.record(OTHER, "in", '[2,"t30-b","Heartbeat",{}]')
        db = SessionLocal()
        try:
            self.assertEqual(db.query(OcppMessageLog).filter_by(unique_id="t30-a").count(), 1)
            self.assertEqual(db.query(OcppMessageLog).filter_by(unique_id="t30-b").count(), 0)
        finally:
            db.close()

    def test_31_reply_is_labelled_with_the_call_it_answers(self):
        ocpp_trace.record(MINE, "out", '[2,"t31","Reset",{"type":"Soft"}]')
        ocpp_trace.record(MINE, "in", '[3,"t31",{"status":"Accepted"}]')
        db = SessionLocal()
        try:
            reply = db.query(OcppMessageLog).filter_by(unique_id="t31", message_type=3).one()
            self.assertEqual(reply.action, "Reset")
            self.assertEqual(reply.direction, "in")
        finally:
            db.close()

    def test_32_tap_always_runs_the_original_handlers(self):
        seen = []

        class _CP:
            id = MINE

            async def route_message(self, raw):
                seen.append(("route", raw))

            async def _send(self, message):
                seen.append(("send", message))

        cp = _CP()
        ocpp_trace.attach(cp)
        # Not JSON at all: the tap must store it and still hand it on.
        asyncio.run(cp.route_message("not json"))
        asyncio.run(cp._send('[3,"t32",{}]'))
        self.assertEqual(seen, [("route", "not json"), ("send", '[3,"t32",{}]')])

    def test_33_live_returns_frames_after_the_cursor(self):
        h = self._login()
        r = self.client.get(f"/api/vendor/chargers/{MINE}/live", headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        messages = r.json()["messages"]
        self.assertTrue(messages)
        last = messages[-1]["id"]
        ocpp_trace.record(MINE, "in", '[2,"t33","Heartbeat",{}]')
        r = self.client.get(f"/api/vendor/chargers/{MINE}/live?after_id={last}", headers=h)
        self.assertEqual([m["unique_id"] for m in r.json()["messages"]], ["t33"])

    # ── Checklist ──

    def _since(self):
        db = SessionLocal()
        try:
            return ocpp_trace.latest_id(db, MINE)
        finally:
            db.close()

    def _states(self, since):
        r = self.client.get(f"/api/vendor/chargers/{MINE}/checklist?since_id={since}", headers=self._login())
        self.assertEqual(r.status_code, 200, r.text)
        return {i["key"]: i for i in r.json()["items"]}, r.json()

    def test_40_checklist_follows_a_charging_run(self):
        since = self._since()
        states, _ = self._states(since)
        self.assertEqual(states["boot"]["state"], "waiting")
        self.assertEqual(states["remote_start"]["state"], "waiting")

        def frame(direction, obj):
            ocpp_trace.record(MINE, direction, json.dumps(obj))

        frame("in", [2, "c1", "BootNotification",
                     {"chargePointVendor": "Acme", "chargePointModel": "AC22", "firmwareVersion": "1.0.0"}])
        frame("out", [3, "c1", {"status": "Accepted", "interval": 30, "currentTime": "2026-10-14T00:00:00Z"}])
        frame("in", [2, "c2", "Heartbeat", {}])
        frame("in", [2, "c3", "StatusNotification", {"connectorId": 1, "status": "Preparing", "errorCode": "NoError"}])
        frame("out", [2, "c4", "RemoteStartTransaction", {"connectorId": 1, "idTag": "DASHBOARD_USER"}])
        frame("in", [3, "c4", {"status": "Accepted"}])
        frame("in", [2, "c5", "StartTransaction", {"connectorId": 1, "idTag": "DASHBOARD_USER", "meterStart": 100}])
        frame("out", [3, "c5", {"transactionId": 4242, "idTagInfo": {"status": "Accepted"}}])
        frame("in", [2, "c6", "MeterValues", {"connectorId": 1, "meterValue": [{"sampledValue": [
            {"value": "600", "measurand": "Energy.Active.Import.Register"}]}]}])
        frame("out", [2, "c7", "RemoteStopTransaction", {"transactionId": 4242}])
        frame("in", [3, "c7", {"status": "Rejected"}])

        states, summary = self._states(since)
        self.assertEqual(states["boot"]["state"], "pass")
        self.assertIn("Acme / AC22 / 1.0.0", states["boot"]["detail"])
        self.assertEqual(states["heartbeat"]["state"], "pass")
        self.assertEqual(states["remote_start"]["state"], "pass")
        self.assertEqual(states["start_tx"]["state"], "pass")
        self.assertIn("4242", states["start_tx"]["detail"])
        self.assertEqual(states["meter"]["state"], "pass")
        # The charger said no: that is a failure, not "done".
        self.assertEqual(states["remote_stop"]["state"], "fail")
        self.assertEqual(states["stop_tx"]["state"], "waiting")
        self.assertEqual(summary["failed"], 1)
        # Optional items do not count towards the total.
        self.assertEqual(states["authorize"]["optional"], True)
        self.assertEqual(summary["total"], len([i for i in summary["items"] if not i["optional"]]))

    def test_41_billing_needs_a_finished_session_with_energy(self):
        since = self._since()
        states, _ = self._states(since)
        self.assertEqual(states["billing"]["state"], "waiting")
        db = SessionLocal()
        try:
            charger = db.query(Charger).filter_by(charge_point_id=MINE).one()
            charger.tariff_per_kwh = 1
            db.add(ChargingSession(
                charger_id=charger.id, transaction_id=990041, connector_id=1,
                start_time=_now_myt(), stop_time=_now_myt() + timedelta(minutes=5),
                meter_start=1000, meter_stop=3500, energy_consumed=2.5, status="completed",
            ))
            db.commit()
        finally:
            db.close()
        states, _ = self._states(since)
        self.assertEqual(states["billing"]["state"], "pass", states["billing"])
        self.assertIn("2.500 kWh", states["billing"]["detail"])
        self.assertIn("RM 2.50", states["billing"]["detail"])

    def test_42_firmware_update_is_proven_by_a_new_version_on_boot(self):
        def frame(direction, obj):
            ocpp_trace.record(MINE, direction, json.dumps(obj))

        frame("in", [2, "f0", "BootNotification",
                     {"chargePointVendor": "Acme", "chargePointModel": "AC22", "firmwareVersion": "1.0.0"}])
        frame("out", [3, "f0", {"status": "Accepted", "interval": 30, "currentTime": "x"}])
        since = self._since() - 2  # keep that boot inside the run
        frame("out", [2, "f1", "UpdateFirmware", {"location": "http://example.com/fw.bin", "retrieveDate": "x"}])
        frame("in", [3, "f1", {}])
        for i, status in enumerate(("Downloading", "Downloaded", "Installing")):
            frame("in", [2, f"f2{i}", "FirmwareStatusNotification", {"status": status}])

        states, _ = self._states(since)
        self.assertEqual(states["fw_request"]["state"], "pass")
        self.assertEqual(states["fw_installing"]["state"], "pass")
        self.assertEqual(states["fw_installed"]["state"], "waiting")
        self.assertEqual(states["fw_boot"]["state"], "waiting")

        frame("in", [2, "f3", "FirmwareStatusNotification", {"status": "Installed"}])
        frame("in", [2, "f4", "BootNotification",
                     {"chargePointVendor": "Acme", "chargePointModel": "AC22", "firmwareVersion": "1.0.0"}])
        states, _ = self._states(since)
        # Installed was reported but the version did not move.
        self.assertEqual(states["fw_boot"]["state"], "fail", states["fw_boot"])

        frame("in", [2, "f5", "BootNotification",
                     {"chargePointVendor": "Acme", "chargePointModel": "AC22", "firmwareVersion": "2.0.0"}])
        states, _ = self._states(since)
        self.assertEqual(states["fw_boot"]["state"], "pass", states["fw_boot"])
        self.assertIn("1.0.0 -> 2.0.0", states["fw_boot"]["detail"])

    # ── Choosing their own charge point ids ──

    def test_50_vendor_adds_an_unused_id(self):
        h = self._login()
        r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": "VT-SELF-001"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertIn("VT-SELF-001", r.json()["charge_point_ids"])
        ids = [c["charge_point_id"] for c in self.client.get("/api/vendor/overview", headers=h).json()["chargers"]]
        self.assertIn("VT-SELF-001", ids)
        # And it is recorded from the first frame, before any admin touches it.
        ocpp_trace.record("VT-SELF-001", "in", '[2,"t50","BootNotification",{}]')
        db = SessionLocal()
        try:
            self.assertEqual(db.query(OcppMessageLog).filter_by(unique_id="t50").count(), 1)
        finally:
            db.close()

    def test_51_an_existing_charger_cannot_be_claimed(self):
        """The whole point of the scope: typing a live charger's id must not
        hand it over, in any spelling."""
        h = self._login()
        for attempt in (OTHER, OTHER.lower(), "  " + OTHER + " "):
            r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": attempt})
            self.assertEqual(r.status_code, 409, f"{attempt!r}: {r.text}")
        ids = [c["charge_point_id"] for c in self.client.get("/api/vendor/overview", headers=h).json()["chargers"]]
        self.assertNotIn(OTHER, ids)
        self.assertEqual(self.client.get(f"/api/vendor/chargers/{OTHER}/live", headers=h).status_code, 404)

    def test_52_another_vendors_id_cannot_be_claimed(self):
        r = self.client.post("/api/admin/vendors", headers=self.admin, json={
            "company": "Rival", "email": "rival@acme.example", "charge_point_ids": "RIVAL-001",
        })
        self.assertEqual(r.status_code, 201, r.text)
        h = self._login()
        for attempt in ("RIVAL-001", "rival-001"):
            r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": attempt})
            self.assertEqual(r.status_code, 409, r.text)
        # The same words as for a live charger: the answer says nothing about who holds it.
        live = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": OTHER})
        self.assertEqual(r.json()["detail"], live.json()["detail"])

    def test_53_bad_ids_and_the_limit(self):
        h = self._login()
        for bad in ("ab", "has space", "semi;colon", "../etc"):
            r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": bad})
            self.assertIn(r.status_code, (400, 422), f"{bad!r}: {r.text}")
        # Adding one already held is a no-op, not a second copy.
        r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": MINE})
        self.assertEqual(r.json()["charge_point_ids"].count(MINE), 1)
        n = len(r.json()["charge_point_ids"])
        for i in range(n, 5):
            r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": f"VT-FILL-{i}"})
            self.assertEqual(r.status_code, 201, r.text)
        r = self.client.post("/api/vendor/chargers", headers=h, json={"charge_point_id": "VT-ONE-TOO-MANY"})
        self.assertEqual(r.status_code, 409, r.text)

    def test_54_only_an_unused_id_can_be_removed(self):
        h = self._login()
        # Never connected: the vendor may take it back.
        r = self.client.delete("/api/vendor/chargers/VT-NOT-YET-1", headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("VT-NOT-YET-1", r.json()["charge_point_ids"])
        # Has connected: it has history, so removal is an administrator's call.
        self.assertEqual(self.client.delete(f"/api/vendor/chargers/{MINE}", headers=h).status_code, 409)
        # Not theirs at all.
        self.assertEqual(self.client.delete(f"/api/vendor/chargers/{OTHER}", headers=h).status_code, 404)

    def test_55_an_account_can_start_with_no_ids(self):
        r = self.client.post("/api/admin/vendors", headers=self.admin, json={
            "company": "Empty", "email": "empty@acme.example",
        })
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["charge_point_ids"], [])

    # ── Losing access ── (last: these change the account)

    def test_90_disabling_ends_a_signed_in_session(self):
        h = self._login()
        self.assertEqual(self.client.get("/api/vendor/overview", headers=h).status_code, 200)
        r = self.client.patch(f"/api/admin/vendors/{self.vendor_id}", headers=self.admin, json={"is_active": False})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.client.get("/api/vendor/overview", headers=h).status_code, 401)
        r = self.client.post("/api/vendor/login", json={"email": self.email, "password": self.password})
        self.assertEqual(r.status_code, 401)
        # And its chargers stop being recorded.
        ocpp_trace.record(MINE, "in", '[2,"t90","Heartbeat",{}]')
        db = SessionLocal()
        try:
            self.assertEqual(db.query(OcppMessageLog).filter_by(unique_id="t90").count(), 0)
        finally:
            db.close()
        self.client.patch(f"/api/admin/vendors/{self.vendor_id}", headers=self.admin, json={"is_active": True})

    def test_91_expiry_ends_a_signed_in_session(self):
        h = self._login()
        db = SessionLocal()
        try:
            v = db.query(VendorAccount).filter_by(id=self.vendor_id).one()
            v.expires_at = _utcnow() - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.client.get("/api/vendor/overview", headers=h).status_code, 401)
        r = self.client.patch(f"/api/admin/vendors/{self.vendor_id}", headers=self.admin, json={"clear_expiry": True})
        self.assertFalse(r.json()["expired"])

    def test_92_reset_password_replaces_the_old_one(self):
        h = self._login()
        r = self.client.patch(f"/api/admin/vendors/{self.vendor_id}", headers=self.admin,
                              json={"reset_password": True})
        new = r.json()["password"]
        self.assertNotEqual(new, self.password)
        self.assertEqual(self.client.get("/api/vendor/overview", headers=h).status_code, 401)
        r = self.client.post("/api/vendor/login", json={"email": self.email, "password": self.password})
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/vendor/login", json={"email": self.email, "password": new})
        self.assertEqual(r.status_code, 200, r.text)
        type(self).password = new

    def test_93_delete_removes_the_account(self):
        r = self.client.post("/api/admin/vendors", headers=self.admin, json={
            "company": "Temp", "email": "temp@acme.example", "charge_point_ids": "TEMP-001",
        })
        vid, pw = r.json()["id"], r.json()["password"]
        h = {"X-Vendor-Token": self.client.post(
            "/api/vendor/login", json={"email": "temp@acme.example", "password": pw}).json()["token"]}
        self.assertEqual(self.client.delete(f"/api/admin/vendors/{vid}", headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get("/api/vendor/overview", headers=h).status_code, 401)


if __name__ == "__main__":
    unittest.main()

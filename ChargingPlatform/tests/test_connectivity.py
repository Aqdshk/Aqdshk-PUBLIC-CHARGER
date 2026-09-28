"""Charger connectivity: SIM identity, the connection log, and its figures.

Pinned down here because each rule answers a question an operator will act
on: which network a charger is on, how often its link drops, and whether a
charger that reports no SIM is being passed off as WiFi (it must not be).
"""
import unittest
from datetime import timedelta

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import connectivity as conn  # noqa: E402
from database import (  # noqa: E402
    Base, Charger, ChargerConnectionEvent, SessionLocal, Tenant, User, engine,
)
from security import create_tokens  # noqa: E402


class OperatorTests(unittest.TestCase):
    def test_malaysian_operators(self):
        # The IMSI DG322021572 actually sends.
        self.assertEqual(conn.operator_from_imsi("502195711692513"), "CelcomDigi (Celcom)")
        self.assertEqual(conn.operator_from_imsi("502121234567890"), "Maxis")
        self.assertEqual(conn.operator_from_imsi("502161234567890"), "CelcomDigi (Digi)")
        self.assertEqual(conn.operator_from_imsi("502181234567890"), "U Mobile")
        # Three-digit MNC must win over the two-digit prefix it starts with.
        self.assertEqual(conn.operator_from_imsi("502153123456789"), "unifi Mobile")

    def test_unknown_and_foreign(self):
        self.assertIsNone(conn.operator_from_imsi(None))
        self.assertIsNone(conn.operator_from_imsi("abc"))
        self.assertEqual(conn.operator_from_imsi("310260123456789"), "Foreign network (MCC 310)")
        self.assertEqual(conn.operator_from_imsi("502991234567890"), "Malaysian network (MNC 99)")


class ClassifyTests(unittest.TestCase):
    def test_sim_reported(self):
        c = Charger(charge_point_id="X", iccid="8960192505343286483F")
        r = conn.classify(c)
        self.assertEqual(r["type"], "cellular")
        self.assertEqual(r["source"], "SIM reported by charger")

    def test_operator_named_when_imsi_known(self):
        c = Charger(charge_point_id="X", iccid="8960", imsi="502195711692513")
        self.assertEqual(conn.classify(c)["label"], "Cellular (SIM) · CelcomDigi (Celcom)")

    def test_no_sim_is_unknown_not_wifi(self):
        r = conn.classify(Charger(charge_point_id="X"))
        self.assertEqual(r["type"], "unknown")

    def test_operator_override_wins(self):
        c = Charger(charge_point_id="X", iccid="8960", connectivity_override="wifi")
        r = conn.classify(c)
        self.assertEqual(r["type"], "wifi")
        self.assertEqual(r["source"], "set by operator")


class LogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def _add(self, db, cp, event, ago, code=None):
        db.add(ChargerConnectionEvent(
            charge_point_id=cp, event=event, at=conn._utcnow() - ago, close_code=code,
        ))

    def test_summary_over_a_window(self):
        cp = "CONN-SUMMARY"
        db = SessionLocal()
        h = timedelta(hours=1)
        self._add(db, cp, "connected", 30 * h)                 # before the window: up at its start
        self._add(db, cp, "disconnected", 10 * h, 1006)        # signal lost
        self._add(db, cp, "connected", 10 * h - timedelta(minutes=5))
        self._add(db, cp, "disconnected", 2 * h, 1000)
        self._add(db, cp, "connected", 1 * h)
        db.commit()

        r = conn.summarize(db, cp, 24)
        db.close()

        self.assertEqual(r["disconnects"], 2)
        self.assertEqual(r["abnormal_drops"], 1)
        # Down 5 min + 1 h out of 24 h.
        self.assertAlmostEqual(r["uptime_percent"], 95.5, delta=0.2)
        self.assertAlmostEqual(r["longest_offline_seconds"], 3600, delta=5)
        self.assertEqual(r["events"][0]["event"], "connected")  # newest first
        self.assertIn("1006", conn.describe_close(1006, None) + " 1006")

    def test_log_newer_than_window_is_not_counted_as_offline(self):
        # The log only exists from the day this shipped. A charger connected
        # an hour ago with nothing before it has been up 100% of what we know.
        cp = "CONN-NEW"
        db = SessionLocal()
        self._add(db, cp, "connected", timedelta(hours=1))
        db.commit()
        r = conn.summarize(db, cp, 24)
        db.close()
        self.assertEqual(r["uptime_percent"], 100.0)
        self.assertIsNotNone(r["measured_since"])

    def test_no_events_means_no_figures(self):
        db = SessionLocal()
        r = conn.summarize(db, "CONN-NOTHING", 24)
        db.close()
        self.assertIsNone(r["uptime_percent"])
        self.assertEqual(r["disconnects"], 0)

    def test_record_event_durations_and_ip(self):
        cp = "CONN-RECORD"
        db = SessionLocal()
        # Its own tenant: the suite shares one database, and a charger left in
        # the default tenant changes the counts test_tenants asserts.
        db.add(Charger(charge_point_id=cp, tenant="conn-test"))
        db.commit()
        db.close()

        conn.record_event(cp, "connected", remote_ip="203.0.113.7")
        conn.record_event(cp, "disconnected", close_code=1006)
        conn.record_event(cp, "connected", remote_ip="203.0.113.8")

        db = SessionLocal()
        rows = (
            db.query(ChargerConnectionEvent)
            .filter(ChargerConnectionEvent.charge_point_id == cp)
            .order_by(ChargerConnectionEvent.id)
            .all()
        )
        charger = db.query(Charger).filter(Charger.charge_point_id == cp).first()
        db.close()

        self.assertEqual([r.event for r in rows], ["connected", "disconnected", "connected"])
        self.assertIsNone(rows[0].duration_seconds)       # nothing before it
        self.assertIsNotNone(rows[1].duration_seconds)    # how long it was up
        self.assertIsNotNone(rows[2].duration_seconds)    # how long it was down
        self.assertEqual(charger.last_remote_ip, "203.0.113.8")

    def test_record_event_never_raises(self):
        # A charger's WebSocket must not die because the log could not be
        # written; an oversized reason is truncated, not an error.
        conn.record_event("CONN-LONG", "disconnected", close_reason="x" * 1000)


class ConnectivityApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        admin = User(
            email="conn-test@example.com", password_hash="not-a-real-hash",
            is_admin=True, is_active=True,
        )
        db.add(admin)
        if not db.query(Tenant).filter(Tenant.key == "mini").first():
            db.add(Tenant(key="mini", label="PlagSini Mini"))
        db.add(Charger(
            charge_point_id="CONN-API", tenant="mini",
            iccid="8960192111333023299F", imsi="502195711692513",
        ))
        db.commit()
        db.refresh(admin)
        cls.headers = {"Authorization": "Bearer " + create_tokens(admin)["access_token"]}
        db.close()
        cls.client = TestClient(api.app)

    def test_log_endpoint_needs_staff(self):
        r = self.client.get("/api/admin/chargers/CONN-API/connectivity")
        self.assertIn(r.status_code, (401, 403))

    def test_log_endpoint(self):
        r = self.client.get("/api/admin/chargers/CONN-API/connectivity?hours=24", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["connectivity"]["type"], "cellular")
        self.assertEqual(body["connectivity"]["imsi"], "502195711692513")
        self.assertIn("events", body)

    def test_list_carries_type_but_not_sim_numbers(self):
        api._CHARGERS_CACHE.clear()
        r = self.client.get("/api/chargers?tenant=mini", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        row = next(c for c in r.json() if c["charge_point_id"] == "CONN-API")
        self.assertEqual(row["connectivity"]["type"], "cellular")
        self.assertNotIn("iccid", row["connectivity"])
        self.assertNotIn("imsi", row["connectivity"])

    def test_anonymous_list_hides_connectivity(self):
        api._CHARGERS_CACHE.clear()
        r = self.client.get("/api/chargers?tenant=mini")
        row = next(c for c in r.json() if c["charge_point_id"] == "CONN-API")
        self.assertIsNone(row["connectivity"])

    def test_override_is_validated_and_reversible(self):
        url = "/api/admin/chargers/CONN-API/info"
        self.assertEqual(self.client.patch(url, json={"connectivity": "carrier-pigeon"}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.patch(url, json={"connectivity": "wifi"}, headers=self.headers).status_code, 200)
        db = SessionLocal()
        self.assertEqual(db.query(Charger).filter(Charger.charge_point_id == "CONN-API").first().connectivity_override, "wifi")
        db.close()
        self.assertEqual(self.client.patch(url, json={"connectivity": "auto"}, headers=self.headers).status_code, 200)
        db = SessionLocal()
        self.assertIsNone(db.query(Charger).filter(Charger.charge_point_id == "CONN-API").first().connectivity_override)
        db.close()


if __name__ == "__main__":
    unittest.main()

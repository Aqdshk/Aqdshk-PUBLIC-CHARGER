"""Tenant management endpoints.

The dashboard's tenant switcher used to read a hardcoded array in
static/tenant.js, and `chargers.tenant` could only be changed with an UPDATE
against the database. These endpoints replaced both, so the rules that keep the
data consistent are worth pinning down:

  - a key is immutable, because chargers store it directly
  - a tenant holding chargers cannot be deleted, or they vanish from every view
  - a charger cannot be moved to a key that was never registered
"""
import unittest

# Database configuration lives in conftest.py, which pytest imports before any
# test module, so the engine is already pointed at SQLite by the time this runs.

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from database import Base, Charger, SessionLocal, Tenant, User, engine  # noqa: E402
from security import create_tokens  # noqa: E402


class TenantApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        admin = User(
            email="tenant-test@example.com",
            password_hash="not-a-real-hash",
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.add_all([
            Tenant(key="czero-tng", label="CZero TNG Public", badge="TNG", sort_order=10),
            Tenant(key="perodua", label="Perodua Public", badge="P2", sort_order=20),
        ])
        db.commit()
        db.refresh(admin)
        db.add_all([
            Charger(charge_point_id="TEST-CP-A", tenant="perodua"),
            Charger(charge_point_id="TEST-CP-B", tenant="czero-tng"),
        ])
        db.commit()
        cls.headers = {"Authorization": "Bearer " + create_tokens(admin)["access_token"]}
        db.close()
        cls.client = TestClient(api.app)

    def _keys(self):
        r = self.client.get("/api/tenants", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return {t["key"]: t for t in r.json()}

    def test_01_list_and_counts(self):
        rows = self._keys()
        self.assertIn("czero-tng", rows)
        self.assertIn("perodua", rows)
        self.assertEqual(rows["perodua"]["charger_count"], 1)
        self.assertEqual(rows["czero-tng"]["charger_count"], 1)

    def test_02_requires_auth(self):
        self.assertIn(self.client.get("/api/tenants").status_code, (401, 403))

    def test_03_create_and_reject_bad_input(self):
        r = self.client.post(
            "/api/tenants",
            headers=self.headers,
            json={"key": "shell-recharge", "label": "Shell Recharge", "badge": "SHELL"},
        )
        self.assertEqual(r.status_code, 201, r.text)

        dup = self.client.post(
            "/api/tenants", headers=self.headers,
            json={"key": "shell-recharge", "label": "Duplicate"},
        )
        self.assertEqual(dup.status_code, 409)

        bad = self.client.post(
            "/api/tenants", headers=self.headers, json={"key": "Bad Key!", "label": "x"},
        )
        self.assertEqual(bad.status_code, 400)

        nolabel = self.client.post("/api/tenants", headers=self.headers, json={"key": "nolabel"})
        self.assertEqual(nolabel.status_code, 400)

    def test_04_rename_allowed_key_change_is_not(self):
        r = self.client.patch(
            "/api/tenants/shell-recharge", headers=self.headers,
            json={"label": "Shell Malaysia"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["label"], "Shell Malaysia")

        # Chargers store the key, so renaming it would orphan every one of them.
        r = self.client.patch(
            "/api/tenants/shell-recharge", headers=self.headers,
            json={"key": "something-else"},
        )
        self.assertEqual(r.status_code, 400)

    def test_05_move_charger_between_tenants(self):
        r = self.client.patch(
            "/api/admin/chargers/TEST-CP-A/info", headers=self.headers,
            json={"tenant": "shell-recharge"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        rows = self._keys()
        self.assertEqual(rows["shell-recharge"]["charger_count"], 1)
        self.assertEqual(rows["perodua"]["charger_count"], 0)

    def test_06_cannot_delete_a_tenant_that_still_holds_chargers(self):
        r = self.client.delete("/api/tenants/shell-recharge", headers=self.headers)
        self.assertEqual(r.status_code, 409, r.text)

    def test_07_unknown_tenant_refused_on_charger(self):
        self.client.patch(
            "/api/admin/chargers/TEST-CP-A/info", headers=self.headers,
            json={"tenant": "perodua"},
        )
        r = self.client.patch(
            "/api/admin/chargers/TEST-CP-A/info", headers=self.headers,
            json={"tenant": "ghost-tenant"},
        )
        self.assertEqual(r.status_code, 400, r.text)

    def test_08_delete_once_empty(self):
        r = self.client.delete("/api/tenants/shell-recharge", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("shell-recharge", self._keys())

    def test_09_charger_filter_still_scopes(self):
        r = self.client.get("/api/chargers?tenant=perodua", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(all(c.get("tenant") == "perodua" for c in r.json()))


if __name__ == "__main__":
    unittest.main()

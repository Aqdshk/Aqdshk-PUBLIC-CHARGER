"""Phantom-connector handling in StatusNotification.

DC3001 has one gun. Its firmware announces a second connector and reports it
Faulted on every status sweep. That report used to reach charger.availability
and paint the whole station red on the app's map while the real gun sat
available.
"""
import asyncio
import unittest
from types import SimpleNamespace

from database import Charger, Fault
from ocpp_server import (
    ChargePoint,
    best_connector_availability,
    forget_phantom_connector,
    is_phantom_connector,
    parse_connector_status,
)


def _dc3001(**overrides):
    """A charger row shaped like DC3001 in production: one gun, count locked,
    and a leftover 'faulted' entry for the gun that does not exist."""
    row = dict(
        id=2,
        charge_point_id="DC3001",
        status="online",
        availability="faulted",
        connector_status='{"1": "available", "2": "faulted"}',
        number_of_connectors=1,
        connectors_locked=True,
        last_heartbeat=None,
    )
    row.update(overrides)
    return SimpleNamespace(**row)


class ConnectorHelperTests(unittest.TestCase):
    def test_parse_connector_status_survives_junk(self):
        self.assertEqual(parse_connector_status(None), {})
        self.assertEqual(parse_connector_status(""), {})
        self.assertEqual(parse_connector_status("not json"), {})
        self.assertEqual(parse_connector_status('{"1": "available"}'),
                         {"1": "available"})

    def test_best_availability_prefers_the_usable_socket(self):
        # A real 2-gun charger: one faulted gun must not take the station off
        # the map while the other is free.
        self.assertEqual(
            best_connector_availability({"1": "available", "2": "faulted"}),
            "available")
        self.assertEqual(
            best_connector_availability({"1": "charging", "2": "faulted"}),
            "charging")
        self.assertEqual(best_connector_availability({"1": "faulted"}),
                         "faulted")
        self.assertIsNone(best_connector_availability({}))

    def test_phantom_only_when_the_operator_has_pinned_the_count(self):
        charger = _dc3001()
        self.assertTrue(is_phantom_connector(charger, 2))
        self.assertFalse(is_phantom_connector(charger, 1))
        # connector 0 is the station itself, never a phantom gun
        self.assertFalse(is_phantom_connector(charger, 0))

    def test_unlocked_charger_is_still_allowed_to_declare_its_guns(self):
        charger = _dc3001(connectors_locked=False)
        self.assertFalse(is_phantom_connector(charger, 2))

    def test_forget_phantom_clears_the_stale_entry_and_reheals_availability(self):
        charger = _dc3001()
        self.assertTrue(forget_phantom_connector(charger, 2))
        self.assertEqual(parse_connector_status(charger.connector_status),
                         {"1": "available"})
        self.assertEqual(charger.availability, "available")

    def test_forget_phantom_is_a_no_op_once_it_is_gone(self):
        charger = _dc3001(connector_status='{"1": "available"}',
                          availability="available")
        self.assertFalse(forget_phantom_connector(charger, 2))
        self.assertEqual(charger.availability, "available")


class _FakeQuery:
    def __init__(self, result):
        self._result = result
        self.updates = []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def all(self):
        return []

    def update(self, values):
        self.updates.append(values)
        return 0


class _FakeDB:
    """Just enough session for the StatusNotification handler."""

    def __init__(self, charger):
        self.charger = charger
        self.added = []
        self.commits = 0

    def query(self, model):
        return _FakeQuery(self.charger if model is Charger else None)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _status_notification(charger, connector_id, status, error_code):
    """Drive the real handler against a stub charge point."""
    db = _FakeDB(charger)
    cp = SimpleNamespace(id=charger.charge_point_id, db=db)
    asyncio.run(ChargePoint.on_status_notification(
        cp, connector_id=connector_id, error_code=error_code, status=status))
    return db


class StatusNotificationPhantomTests(unittest.TestCase):
    def test_phantom_faulted_report_does_not_reach_availability(self):
        # This is the bug: the check used to run after availability had
        # already been written, so DC3001 showed FAULTED on the map.
        charger = _dc3001(availability="available",
                          connector_status='{"1": "available"}')
        db = _status_notification(charger, 2, "Faulted", "OtherError")

        self.assertEqual(charger.availability, "available")
        self.assertEqual(parse_connector_status(charger.connector_status),
                         {"1": "available"})
        self.assertEqual([o for o in db.added if isinstance(o, Fault)], [])
        # The message still proves the charger is talking to us.
        self.assertEqual(charger.status, "online")
        self.assertIsNotNone(charger.last_heartbeat)

    def test_phantom_report_heals_a_row_that_already_went_faulted(self):
        charger = _dc3001()  # availability='faulted', phantom entry present
        _status_notification(charger, 2, "Faulted", "OtherError")

        self.assertEqual(charger.availability, "available")
        self.assertEqual(parse_connector_status(charger.connector_status),
                         {"1": "available"})

    def test_real_gun_still_updates_normally(self):
        charger = _dc3001(availability="faulted",
                          connector_status='{"1": "faulted"}')
        _status_notification(charger, 1, "Available", "NoError")

        self.assertEqual(charger.availability, "available")
        self.assertEqual(parse_connector_status(charger.connector_status),
                         {"1": "available"})

    def test_second_gun_on_a_genuine_two_gun_charger_is_not_dropped(self):
        charger = _dc3001(charge_point_id="DC2GUN",
                          number_of_connectors=2,
                          connectors_locked=True,
                          availability="available",
                          connector_status='{"1": "available"}')
        _status_notification(charger, 2, "Charging", "NoError")

        self.assertEqual(parse_connector_status(charger.connector_status),
                         {"1": "available", "2": "charging"})
        self.assertEqual(charger.availability, "available")


if __name__ == "__main__":
    unittest.main()

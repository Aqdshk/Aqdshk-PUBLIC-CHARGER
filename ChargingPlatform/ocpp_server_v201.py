"""OCPP 2.0.1 message handlers.

Phase 1: connection lifecycle only — BootNotification, Heartbeat,
StatusNotification. Enough for a 2.0.1 charger to come online and show correct
connector state on the dashboard. Transactions, remote control and the device
model land in later phases.

Kept in its own module on purpose. The 1.6 handler in ocpp_server.py is the
one carrying live traffic and paid sessions; nothing here imports into it or
changes its behaviour. Routing between the two happens in on_connect, chosen
by the WebSocket subprotocol the charger negotiated.

Where 2.0.1 differs from 1.6, and why this file cannot just reuse the old one:

  * BootNotification nests identity under `charging_station` and sends
    `reason` instead of a flat model/vendor pair.
  * StatusNotification is per (evse_id, connector_id) — a two-level hierarchy.
    1.6 has a flat connector_id. We store evse_id alongside so a charger with
    several EVSEs, each with several connectors, stays unambiguous.
  * Status values are ConnectorStatusEnumType: Available, Occupied, Reserved,
    Unavailable, Faulted. 1.6's Preparing / Charging / Finishing / SuspendedEV
    are gone — occupancy is carried by transactions instead. So a 2.0.1
    charger never reports "Charging" here; it reports "Occupied".
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ocpp.routing import on
from ocpp.v201 import ChargePoint as cp201
from ocpp.v201 import call_result
from ocpp.v201.enums import RegistrationStatusEnumType

from database import Charger, SessionLocal

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 2.0.1 reports occupancy through transactions, not through the connector
# status, so this map is deliberately smaller than the 1.6 one. "Occupied"
# covers everything from plugged-in to actively charging; the transaction
# stream is what tells the two apart (phase 2).
_STATUS_MAP = {
    "Available": "available",
    "Occupied": "charging",
    "Reserved": "reserved",
    "Unavailable": "unavailable",
    "Faulted": "faulted",
}

# Best (most usable) socket wins when deriving charger-level availability,
# matching the ranking the 1.6 handler uses.
_RANK = {
    "available": 0, "preparing": 1, "charging": 2, "finishing": 3,
    "reserved": 4, "unavailable": 5, "faulted": 6, "unknown": 7,
}


class ChargePoint201(cp201):
    """OCPP 2.0.1 charge point connection."""

    ocpp_version = "2.0.1"

    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db = SessionLocal()

    def __del__(self):
        if hasattr(self, "db"):
            try:
                self.db.close()
            except Exception:
                pass

    def _charger(self) -> Optional[Charger]:
        return self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()

    # ── Charger → CSMS ────────────────────────────────────────────────────

    @on("BootNotification")
    async def on_boot_notification(self, charging_station: Dict[str, Any], reason: str, **kwargs):
        """Charger announces itself. Identity is nested under charging_station."""
        logger.info(f"[v201] BootNotification from {self.id} (reason={reason})")
        try:
            station = charging_station or {}
            vendor = station.get("vendor_name") or station.get("vendorName") or "Unknown"
            model = station.get("model") or "Unknown"
            modem = station.get("modem") or {}
            firmware = station.get("firmware_version") or station.get("firmwareVersion") or "Unknown"

            charger = self._charger()
            if not charger:
                charger = Charger(
                    charge_point_id=self.id,
                    vendor=vendor,
                    model=model,
                    firmware_version=firmware,
                    status="online",
                    last_heartbeat=_utcnow(),
                )
                self.db.add(charger)
                logger.info(f"[v201] registered new charge point {self.id} ({vendor} {model})")
            else:
                charger.vendor = vendor
                charger.model = model
                charger.firmware_version = firmware
                charger.status = "online"
                charger.last_heartbeat = _utcnow()

            if modem:
                logger.info(f"[v201] {self.id} modem iccid={modem.get('iccid')} imsi={modem.get('imsi')}")

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] BootNotification failed for {self.id}: {e}", exc_info=True)

        return call_result.BootNotification(
            current_time=_now_iso_z(),
            interval=HEARTBEAT_INTERVAL_SECONDS,
            status=RegistrationStatusEnumType.accepted,
        )

    @on("Heartbeat")
    async def on_heartbeat(self, **kwargs):
        try:
            charger = self._charger()
            if charger:
                charger.last_heartbeat = _utcnow()
                charger.status = "online"
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] Heartbeat failed for {self.id}: {e}")
        return call_result.Heartbeat(current_time=_now_iso_z())

    @on("StatusNotification")
    async def on_status_notification(
        self,
        timestamp: str,
        connector_status: str,
        evse_id: int,
        connector_id: int,
        **kwargs,
    ):
        """Per-connector state. Addressed by (evse_id, connector_id) in 2.0.1."""
        logger.info(
            f"[v201] StatusNotification {self.id}: evse={evse_id} conn={connector_id} → {connector_status}"
        )
        try:
            charger = self._charger()
            if not charger:
                return call_result.StatusNotification()

            mapped = _STATUS_MAP.get(connector_status, "unknown")

            # Reuse the 1.6 connector_status column so the dashboard renders
            # 2.0.1 chargers with no changes. Single-EVSE units key on the
            # connector alone; multi-EVSE units get an "evse:connector" key so
            # two EVSEs cannot overwrite each other's slot 1.
            key = str(connector_id) if int(evse_id) <= 1 else f"{evse_id}:{connector_id}"

            conn_map: Dict[str, str] = {}
            if charger.connector_status:
                try:
                    conn_map = json.loads(charger.connector_status) or {}
                except Exception:
                    conn_map = {}
            conn_map[key] = mapped
            charger.connector_status = json.dumps(conn_map)

            # Grow-only, same rule as the 1.6 path: a socket that goes quiet
            # must not shrink the count and lock the operator out of it.
            numeric = [int(k) for k in conn_map if str(k).isdigit()]
            if numeric:
                highest = max(numeric)
                if highest > (charger.number_of_connectors or 1):
                    charger.number_of_connectors = highest

            best = min(conn_map.values(), key=lambda s: _RANK.get(s, 7), default=None)
            if best:
                charger.availability = best

            charger.last_heartbeat = _utcnow()
            charger.status = "online"
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] StatusNotification failed for {self.id}: {e}", exc_info=True)

        return call_result.StatusNotification()

    # ── Guards for 1.6-only operations ────────────────────────────────────
    # active_charge_points holds both handler types, so existing code paths
    # can hand a 2.0.1 charger to a caller expecting 1.6 method names. Those
    # would otherwise die on AttributeError deep in a request. Fail loudly and
    # say why instead. 2.0.1 equivalents arrive in phases 2–4.

    def _unsupported(self, op: str, equivalent: str):
        raise NotImplementedError(
            f"{op} is an OCPP 1.6 operation and {self.id} is connected over OCPP 2.0.1. "
            f"The 2.0.1 equivalent is {equivalent}, which is not implemented yet."
        )

    async def remote_start_transaction(self, *a, **kw):
        self._unsupported("RemoteStartTransaction", "RequestStartTransaction")

    async def remote_stop_transaction(self, *a, **kw):
        self._unsupported("RemoteStopTransaction", "RequestStopTransaction")

    async def get_configuration(self, *a, **kw):
        self._unsupported("GetConfiguration", "GetVariables")

    async def change_configuration(self, *a, **kw):
        self._unsupported("ChangeConfiguration", "SetVariables")

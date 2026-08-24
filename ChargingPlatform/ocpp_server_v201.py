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
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ocpp.routing import on
from ocpp.v201 import ChargePoint as cp201
from ocpp.v201 import call, call_result
from ocpp.v201.enums import AuthorizationStatusEnumType, RegistrationStatusEnumType

from database import Charger, ChargingSession, Fault, MeterValue, SessionLocal

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


class OcppOperationUnsupported(NotImplementedError):
    """Raised when a 1.6 operation has no 2.0.1 implementation behind it.

    Distinct from a plain NotImplementedError so the API layer can turn it
    into a clear message for the operator rather than a generic 500.
    """


def _ocpi_push(kind, ref):
    """Hand a change to the OCPI push queue, never raising into OCPP."""
    try:
        from ocpi.push import enqueue
        enqueue(kind, ref)
    except Exception as e:
        logger.debug("[ocpi-push] enqueue %s %s skipped: %s", kind, ref, e)


_MYT_OFFSET = timedelta(hours=8)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_myt() -> datetime:
    """Server clock as Malaysia wall time, naive — the session/meter convention."""
    return (datetime.now(timezone.utc) + _MYT_OFFSET).replace(tzinfo=None)


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: Optional[str]) -> datetime:
    """A charger's timestamp as Malaysia wall time.

    Session and meter columns hold MYT wall time, not UTC — the 1.6 handler
    has always written them that way and every report reads them that way.
    This used to store UTC, so 2.0.1 sessions landed eight hours in the past:
    a Gresgying session that ran at 14:54 was recorded as 06:54, sitting in
    the same table as 1.6 rows that were correct.

    Chargers disagree about what a zone means, so the offset is applied only
    to values that carry one. A naive timestamp is taken at face value, which
    matches how a charger sending local time intends it to be read.
    """
    if not value:
        return _now_myt()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return _now_myt()
    if dt.tzinfo is not None:
        dt = (dt.astimezone(timezone.utc) + _MYT_OFFSET).replace(tzinfo=None)
    return dt


def _token_of(id_token: Optional[Dict[str, Any]]) -> Optional[str]:
    """Pull the raw token string out of 2.0.1's IdTokenType wrapper."""
    if not id_token:
        return None
    return id_token.get("id_token") or id_token.get("idToken")


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
                    ocpp_version=self.ocpp_version,
                    last_heartbeat=_utcnow(),
                )
                self.db.add(charger)
                logger.info(f"[v201] registered new charge point {self.id} ({vendor} {model})")
            else:
                charger.vendor = vendor
                charger.model = model
                charger.firmware_version = firmware
                charger.status = "online"
                # on_connect also records this, but a charger seen for the very
                # first time has no row until right here.
                charger.ocpp_version = self.ocpp_version
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

            # "Occupied" means the bay is taken, and that is all it means — 2.0.1
            # carries the charging state on the transaction, never here. So this
            # message can say "a car is plugged in", but it can never be the
            # thing that says "charging".
            #
            # Resolving Occupied against an open transaction was the obvious
            # guess and it is wrong: Gresying's firmware opens a transaction on
            # CablePluggedIn, before any authorisation, so a car merely plugged
            # in has both Occupied and an open transaction. Charging is claimed
            # only by the transaction stream — an explicit Charging state, or
            # real power on the cable — which _note_evse handles. Resolved below,
            # once the current slot state is known.
            occupied_downgrade = mapped == "charging"

            # Reuse the 1.6 connector_status column so the dashboard renders
            # 2.0.1 chargers unchanged. The dashboard keys slots "1", "2", "3",
            # so flatten to that wherever it is unambiguous.
            #
            # Nearly every DC unit is N EVSEs with one connector each, and
            # 2.0.1 numbers EVSEs from 1 — so the EVSE id *is* the gun number
            # and maps straight onto a plain slot key. Only an EVSE carrying
            # more than one connector needs the compound "evse:connector" form,
            # which the dashboard shows as an extra slot rather than losing it.
            key = str(evse_id) if int(connector_id) <= 1 else f"{evse_id}:{connector_id}"

            conn_map: Dict[str, str] = {}
            if charger.connector_status:
                try:
                    conn_map = json.loads(charger.connector_status) or {}
                except Exception:
                    conn_map = {}

            # Occupied resolves to "plugged in, waiting" — unless the transaction
            # stream has already established that this gun is charging, in which
            # case leave that alone rather than flapping it back on every status
            # report. Ended is what clears it.
            if occupied_downgrade:
                mapped = "charging" if conn_map.get(key) == "charging" else "preparing"

            conn_map[key] = mapped
            charger.connector_status = json.dumps(conn_map)

            # Grow-only, same rule as the 1.6 path: a socket that goes quiet
            # must not shrink the count and lock the operator out of it.
            # Count every slot, not just the plainly-numbered ones — counting
            # only numeric keys would report a multi-connector EVSE as a
            # single-gun charger, which is the exact fault that made gun 2
            # unreachable on the 1.6 side.
            slots = len(conn_map)
            highest_plain = max((int(k) for k in conn_map if str(k).isdigit()), default=0)
            detected = max(slots, highest_plain)
            if detected > (charger.number_of_connectors or 1):
                charger.number_of_connectors = detected

            best = min(conn_map.values(), key=lambda s: _RANK.get(s, 7), default=None)
            if best:
                charger.availability = best

            charger.last_heartbeat = _utcnow()
            charger.status = "online"
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] StatusNotification failed for {self.id}: {e}", exc_info=True)

        _ocpi_push("location", self.id)
        return call_result.StatusNotification()

    @on("Authorize")
    async def on_authorize(self, id_token: Dict[str, Any], **kwargs):
        """RFID / token presented at the charger.

        There is still no tag registry on the platform, so this mirrors the
        1.6 handler: accept the tokens the platform itself issues, reject the
        rest. Building a real registry is tracked separately — until then a
        physical card cannot start a session on either protocol version.
        """
        token = (id_token or {}).get("id_token") or (id_token or {}).get("idToken") or ""
        logger.info(f"[v201] Authorize from {self.id}: token={token!r}")

        known = ("APP_USER", "DASHBOARD_USER", "LOCAL_CHARGING", "")
        status = (
            AuthorizationStatusEnumType.accepted
            if token in known
            else AuthorizationStatusEnumType.invalid
        )
        if status != AuthorizationStatusEnumType.accepted:
            logger.warning(f"[v201] {self.id}: token {token!r} not recognised — no tag registry yet")

        return call_result.Authorize(id_token_info={"status": status})

    @on("TransactionEvent")
    async def on_transaction_event(
        self,
        event_type: str,
        timestamp: str,
        trigger_reason: str,
        seq_no: int,
        transaction_info: Dict[str, Any],
        **kwargs,
    ):
        """The whole charging lifecycle, in one message.

        2.0.1 folds 1.6's StartTransaction, MeterValues and StopTransaction
        into this single call, distinguished by event_type:
          Started  → open a session
          Updated  → periodic meter readings while charging
          Ended    → close the session

        The reply may carry idTokenInfo and totalCost. We keep it minimal for
        now; pricing is settled platform-side from the stored meter data, the
        same way the 1.6 path works.
        """

        info = transaction_info or {}
        ocpp_txn = info.get("transaction_id") or info.get("transactionId")
        evse = kwargs.get("evse") or {}
        evse_id = evse.get("id")
        connector_id = evse.get("connector_id") or evse.get("connectorId") or 1
        meter_values = kwargs.get("meter_value") or kwargs.get("meterValue") or []

        # Which gun this is, in the flat numbering the rest of the platform
        # uses. On a dual-gun 2.0.1 charger each gun is its own EVSE and every
        # one of them reports connectorId 1, so storing the connector id would
        # file both guns' sessions under gun 1 — the same mix-up the 1.6 path
        # hit during the Gresying test. The EVSE id is what actually addresses
        # a socket, and it is already what the outbound commands and the meter
        # values use, so follow that convention here too.
        gun_id = evse_id or connector_id

        logger.info(
            f"[v201] TransactionEvent {self.id}: {event_type} txn={ocpp_txn} "
            f"evse={evse_id} conn={connector_id} trigger={trigger_reason} seq={seq_no}"
        )

        try:
            charger = self._charger()
            if not charger or not ocpp_txn:
                return call_result.TransactionEvent()

            session = (
                self.db.query(ChargingSession)
                .filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.ocpp_transaction_id == str(ocpp_txn),
                )
                .first()
            )

            if event_type == "Started" and session is None:
                # A remote start leaves a pending session behind, holding the
                # requester's identity, and the charger answers it with this
                # event. Adopt that row rather than opening a second one: two
                # rows for one charge would leave the pending one open forever,
                # and an open pending row makes the gun look permanently busy.
                session = (
                    self.db.query(ChargingSession)
                    .filter(
                        ChargingSession.charger_id == charger.id,
                        ChargingSession.connector_id == gun_id,
                        ChargingSession.status == "pending",
                    )
                    .order_by(ChargingSession.id.desc())
                    .first()
                )
                if session is not None:
                    session.ocpp_transaction_id = str(ocpp_txn)
                    session.evse_id = evse_id
                    session.start_time = _parse_ts(timestamp)
                    session.status = "active"
                    session.transaction_id = session.id
                    logger.info(
                        f"[v201] adopted pending session {session.id} for charger txn {ocpp_txn}"
                    )
                else:
                    session = ChargingSession(
                        charger_id=charger.id,
                        transaction_id=0,  # replaced with the DB id below
                        ocpp_transaction_id=str(ocpp_txn),
                        evse_id=evse_id,
                        connector_id=gun_id,
                        start_time=_parse_ts(timestamp),
                        status="active",
                        user_id=_token_of(kwargs.get("id_token")),
                    )
                    self.db.add(session)
                    self.db.flush()  # populate session.id
                    # Mirror the 1.6 convention: the integer key the rest of the
                    # platform joins on is the row id.
                    session.transaction_id = session.id
                    logger.info(f"[v201] opened session {session.id} for charger txn {ocpp_txn}")

            if session is None:
                # Updated/Ended for a transaction we never saw start. This used
                # to open a session unconditionally, on the theory that the
                # charger was mid-charge when we came up and the energy should
                # not be dropped. That reads far more into the message than it
                # says: Gresying firmware sends a periodic MeterValuePeriodic
                # as a TransactionEvent Updated while sitting idle, carrying a
                # placeholder transaction id and nothing but zeroes. Believing
                # it put both guns into "charging" with no one plugged in, and
                # offered a Stop button for a transaction the charger then
                # refused.
                #
                # So ask the readings whether a charge is actually happening.
                # Real power, or time spent charging, means we genuinely missed
                # a Started and should recover the session. All zeroes means
                # the charger is idle and is only reporting its meter — keep
                # the readings against the connector and open nothing.
                if not self._looks_like_charging(meter_values, info):
                    logger.info(
                        f"[v201] {self.id}: {event_type} for unknown txn {ocpp_txn} with no "
                        f"power and no charging time — idle meter report, storing readings only"
                    )
                    self._store_meter_values(charger, None, meter_values, evse_id, gun_id)
                    self.db.commit()
                    return call_result.TransactionEvent()

                session = ChargingSession(
                    charger_id=charger.id,
                    transaction_id=0,
                    ocpp_transaction_id=str(ocpp_txn),
                    evse_id=evse_id,
                    connector_id=gun_id,
                    start_time=_parse_ts(timestamp),
                    status="active",
                    user_id=_token_of(kwargs.get("id_token")),
                )
                self.db.add(session)
                self.db.flush()
                session.transaction_id = session.id
                logger.warning(
                    f"[v201] {self.id}: {event_type} for unknown txn {ocpp_txn} shows real "
                    f"charging — opened session {session.id} to recover it"
                )

            # A TransactionEvent naming an EVSE is proof that EVSE exists, so
            # treat it as a second source for the gun count alongside
            # StatusNotification. Relying on StatusNotification alone is what
            # left gun 2 unreachable on the 1.6 side: the platform only learns
            # of a socket once that socket happens to report, and a charger
            # that reports sparsely stays understated indefinitely.
            self._note_evse(charger, evse_id,
                            info.get("charging_state") or info.get("chargingState"),
                            event_type,
                            self._looks_like_charging(meter_values, info))

            latest_kwh = self._store_meter_values(
                charger, session, meter_values, evse_id, connector_id
            )
            if latest_kwh is not None:
                if session.meter_start is None:
                    session.meter_start = int(latest_kwh * 1000)
                session.energy_consumed = max(
                    0.0, latest_kwh - (session.meter_start or 0) / 1000.0
                )

            if event_type == "Ended":
                session.status = "completed"
                session.stop_time = _parse_ts(timestamp)
                session.stop_reason = (
                    info.get("stopped_reason") or info.get("stoppedReason") or trigger_reason
                )
                if latest_kwh is not None:
                    session.meter_stop = int(latest_kwh * 1000)
                logger.info(
                    f"[v201] closed session {session.id} — {session.energy_consumed:.3f} kWh, "
                    f"reason={session.stop_reason}"
                )

            charger.last_heartbeat = _utcnow()
            charger.status = "online"
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] TransactionEvent failed for {self.id}: {e}", exc_info=True)

        # The branches above bind `session` only when one was resolved, and
        # UnboundLocalError is the honest signal that none was.
        try:
            _pushed = session
        except (NameError, UnboundLocalError):
            _pushed = None

        if _pushed is not None and getattr(_pushed, "id", None):
            _ocpi_push("session", _pushed.id)
            if getattr(_pushed, "status", None) in ("completed", "interrupted"):
                _ocpi_push("cdr", _pushed.id)

        return call_result.TransactionEvent()

    def _note_evse(self, charger, evse_id, charging_state, event_type, energy_flowing=None):
        """Record a gun seen on a transaction, and reflect its live state.

        Keeps the same slot map StatusNotification writes, so the dashboard
        renders 2.0.1 chargers through the existing per-gun display.

        `charging_state` is optional in the spec and Gresying's firmware omits
        it entirely. This used to fall through to a catch-all that marked the
        gun as charging, so an idle charger reporting its meter once a minute
        held its guns in "charging" forever and reasserted it every report,
        even after the state was corrected by hand. When the charger does not
        say, do not guess: use the readings if they show energy actually
        flowing, and otherwise leave whatever StatusNotification last said.
        """
        if not evse_id:
            return
        try:
            slot = str(int(evse_id))
        except (TypeError, ValueError):
            return

        conn_map: Dict[str, str] = {}
        if charger.connector_status:
            try:
                conn_map = json.loads(charger.connector_status) or {}
            except Exception:
                conn_map = {}

        if event_type == "Ended":
            conn_map[slot] = "available"
        elif charging_state in ("SuspendedEV", "SuspendedEVSE"):
            conn_map[slot] = "charging"   # paused mid-session, bay still taken
        elif charging_state == "EVConnected":
            conn_map[slot] = "preparing"
        elif charging_state == "Idle":
            conn_map[slot] = "available"
        elif charging_state == "Charging":
            conn_map[slot] = "charging"
        elif event_type == "Started" or energy_flowing:
            # No state given, but a transaction opening — or real power on the
            # cable — is evidence enough.
            conn_map[slot] = "charging"
        else:
            # Nothing here says what the gun is doing. Record that the gun
            # exists so the connector count is right, and leave its state to
            # StatusNotification, which is the message that actually reports it.
            conn_map.setdefault(slot, "unknown")

        charger.connector_status = json.dumps(conn_map)

        slots = len(conn_map)
        highest_plain = max((int(k) for k in conn_map if str(k).isdigit()), default=0)
        detected = max(slots, highest_plain)
        if detected > (charger.number_of_connectors or 1):
            charger.number_of_connectors = detected

        best = min(conn_map.values(), key=lambda s: _RANK.get(s, 7), default=None)
        if best:
            charger.availability = best

    @staticmethod
    def _looks_like_charging(meter_values, transaction_info) -> bool:
        """Is this event evidence that energy is actually flowing?

        Used only to decide whether a transaction we never saw start is worth
        recovering as a session. A charger reporting its meter while idle sends
        the same message shape as one mid-charge, so the distinction has to
        come from the values: any real power or current, any time spent
        charging, or an explicit Charging state.
        """
        info = transaction_info or {}
        try:
            if float(info.get("time_spent_charging") or info.get("timeSpentCharging") or 0) > 0:
                return True
        except (ValueError, TypeError):
            pass
        state = info.get("charging_state") or info.get("chargingState")
        if state == "Charging":
            return True

        for mv in meter_values or []:
            for sv in (mv.get("sampled_value") or mv.get("sampledValue") or []):
                if sv.get("measurand") not in ("Power.Active.Import", "Current.Import"):
                    continue
                try:
                    if float(sv.get("value", 0) or 0) > 0:
                        return True
                except (ValueError, TypeError):
                    continue
        return False

    def _store_meter_values(self, charger, session, meter_values, evse_id, connector_id):
        """Persist readings, returning the newest cumulative kWh seen.

        `session` may be None: standalone MeterValues arrive outside any
        transaction, and those readings are still worth keeping — they just
        have no transaction to attribute to.

        2.0.1 nests the unit under unitOfMeasure rather than a flat `unit`
        field, and sends value as a number rather than a string. Everything is
        normalised to the same canonical units the 1.6 path stores — power in
        kW, energy in kWh — so the dashboard and billing read one shape.
        """
        newest_kwh = None
        for mv in meter_values or []:
            ts = _parse_ts(mv.get("timestamp"))
            samples = mv.get("sampled_value") or mv.get("sampledValue") or []

            voltage = current = power = total_kwh = None
            for sv in samples:
                try:
                    value = float(sv.get("value", 0) or 0)
                except (ValueError, TypeError):
                    continue
                measurand = sv.get("measurand") or "Energy.Active.Import.Register"
                uom = sv.get("unit_of_measure") or sv.get("unitOfMeasure") or {}
                unit = (uom.get("unit") or "").strip().lower()

                if measurand == "Voltage":
                    voltage = value
                elif measurand == "Current.Import":
                    current = value
                elif measurand == "Power.Active.Import":
                    power = value / 1000.0 if (unit == "w" or (not unit and value > 1000)) else value
                elif measurand == "Energy.Active.Import.Register":
                    total_kwh = value if unit == "kwh" else value / 1000.0

            self.db.add(
                MeterValue(
                    charger_id=charger.id,
                    # 2.0.1 addresses by EVSE; each gun is its own EVSE on the
                    # DC units here, so that is the slot number to record.
                    connector_id=evse_id or connector_id,
                    transaction_id=session.transaction_id if session else None,
                    timestamp=ts,
                    voltage=voltage,
                    current=current,
                    power=power,
                    total_kwh=total_kwh,
                )
            )
            if total_kwh is not None:
                newest_kwh = total_kwh
        return newest_kwh

    @on("MeterValues")
    async def on_meter_values(self, evse_id: int, meter_value: list, **kwargs):
        """Readings sent outside a transaction — clock-aligned samples and the
        like. TransactionEvent carries readings during a session, so without
        this handler everything reported between sessions was discarded.
        """
        logger.info(f"[v201] MeterValues from {self.id}: evse={evse_id} batches={len(meter_value or [])}")
        try:
            charger = self._charger()
            if charger:
                self._store_meter_values(charger, None, meter_value, evse_id, 1)
                charger.last_heartbeat = _utcnow()
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] MeterValues failed for {self.id}: {e}", exc_info=True)
        return call_result.MeterValues()

    @on("NotifyEvent")
    async def on_notify_event(self, generated_at: str, seq_no: int, event_data: list, **kwargs):
        """Component-level events: over-temperature, RCD trip, contactor
        failure and so on.

        1.6 packed a fault code into StatusNotification. 2.0.1 splits them:
        StatusNotification says a connector is Faulted, NotifyEvent says what
        actually failed and how badly. Without this the dashboard could show
        that something is wrong but never what — the difference between
        sending a technician and sending one with the right part.
        """
        logger.info(f"[v201] NotifyEvent from {self.id}: {len(event_data or [])} event(s)")
        try:
            charger = self._charger()
            if not charger:
                return call_result.NotifyEvent()

            for ev in event_data or []:
                component = (ev.get("component") or {}).get("name") or "Unknown"
                variable = (ev.get("variable") or {}).get("name") or ""
                trigger = ev.get("trigger") or ""
                actual = ev.get("actual_value") or ev.get("actualValue") or ""
                # `cause` is an integer referencing the eventId that led to
                # this one, not a description. The human-readable part lives
                # in techCode and techInfo.
                cause = ev.get("cause")
                tech_code = ev.get("tech_code") or ev.get("techCode") or ""
                tech_info = ev.get("tech_info") or ev.get("techInfo") or ""
                cleared = bool(ev.get("cleared"))

                # "Alerting" is the trigger the spec uses when a monitored
                # value crossed a threshold — that is the problem signal.
                # Delta and Periodic are ordinary reporting. `cleared` marks
                # the recovery event for a fault reported earlier.
                # (Severity is not part of EventData; it belongs to the
                # monitor definition, so there is nothing to read here.)
                is_fault = trigger == "Alerting" and not cleared

                detail = f"{component}.{variable} = {actual} (trigger={trigger}"
                if cause is not None:
                    detail += f", causedByEvent={cause}"
                if tech_code:
                    detail += f", techCode={tech_code}"
                if tech_info:
                    detail += f", techInfo={tech_info}"
                detail += ")"

                if is_fault:
                    logger.warning(f"[v201] {self.id} FAULT: {detail}")
                    self.db.add(Fault(
                        charger_id=charger.id,
                        fault_type=f"{component}.{variable}" if variable else component,
                        message=detail,
                        timestamp=_parse_ts(generated_at),
                    ))
                elif cleared:
                    logger.warning(f"[v201] {self.id} fault cleared: {detail}")
                else:
                    logger.info(f"[v201] {self.id} event: {detail}")

            charger.last_heartbeat = _utcnow()
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"[v201] NotifyEvent failed for {self.id}: {e}", exc_info=True)
        return call_result.NotifyEvent()

    @on("FirmwareStatusNotification")
    async def on_firmware_status_notification(self, status: str, **kwargs):
        """Progress of an UpdateFirmware run."""
        logger.info(f"[v201] FirmwareStatus from {self.id}: {status} (request_id={kwargs.get('request_id')})")
        return call_result.FirmwareStatusNotification()

    @on("SecurityEventNotification")
    async def on_security_event_notification(self, type: str, timestamp: str, **kwargs):
        """Security events the charge point wants on record.

        Gresgying's unit sent 66 of these — mostly ResetOrReboot, queued from
        while it was offline — and with no handler registered the library
        answered every one with a NotImplemented error. A charger being told
        its security log was refused is a bad look on a platform that wants to
        turn on authentication, so accept them and record what arrived.

        The spec marks a few of these as critical, and those are worth a
        warning rather than a line in a stream nobody reads.
        """
        critical = type in (
            "FirmwareUpdated", "SettingSystemTime", "StartupOfDevice",
            "ResetOrReboot", "SecurityLogWasCleared", "InvalidFirmwareSignature",
            "InvalidCentralSystemCertificate", "InvalidChargingStationCertificate",
        )
        tech = kwargs.get("tech_info") or kwargs.get("techInfo")
        line = f"[v201] SecurityEvent from {self.id}: {type} at {timestamp}"
        if tech:
            line += f" — {tech}"
        (logger.warning if critical else logger.info)(line)
        return call_result.SecurityEventNotification()

    @on("DataTransfer")
    async def on_data_transfer(self, vendor_id: str, **kwargs):
        """Vendor-specific payloads. Accepted and logged rather than acted on:
        the platform has no 2.0.1 vendor extensions of its own yet, and
        rejecting would make a charger think its message failed."""
        logger.info(
            f"[v201] DataTransfer from {self.id}: vendor={vendor_id} "
            f"message_id={kwargs.get('message_id')}"
        )
        return call_result.DataTransfer(status="Accepted")

    @on("ReportChargingProfiles")
    async def on_report_charging_profiles(self, request_id: int, charging_limit_source: str,
                                          charging_profile: list, evse_id: int, **kwargs):
        """Profiles currently installed, in reply to GetChargingProfiles."""
        logger.info(
            f"[v201] ReportChargingProfiles from {self.id}: evse={evse_id} "
            f"source={charging_limit_source} profiles={len(charging_profile or [])}"
        )
        for p in charging_profile or []:
            logger.info(f"[v201]   profile id={p.get('id')} purpose={p.get('charging_profile_purpose')}")
        return call_result.ReportChargingProfiles()

    @on("NotifyChargingLimit")
    async def on_notify_charging_limit(self, charging_limit: Dict[str, Any], **kwargs):
        """An external system (not us) imposed a limit on the charger."""
        logger.warning(
            f"[v201] NotifyChargingLimit from {self.id}: evse={kwargs.get('evse_id')} "
            f"source={charging_limit.get('charging_limit_source')} limit={charging_limit}"
        )
        return call_result.NotifyChargingLimit()

    # ── CSMS → Charger ────────────────────────────────────────────────────

    async def request_start_transaction(
        self,
        evse_id: int = 1,
        id_token: str = "APP_USER",
        remote_start_id: Optional[int] = None,
    ):
        """RequestStartTransaction — 2.0.1's remote start.

        remote_start_id is how the charger ties the resulting TransactionEvent
        back to this request, so it must be unique per call rather than fixed.
        """
        try:
            if remote_start_id is None:
                remote_start_id = int(uuid.uuid4().int % 2_000_000_000)
            logger.info(
                f"[v201] RequestStartTransaction → {self.id}: evse={evse_id} "
                f"token={id_token} remote_start_id={remote_start_id}"
            )
            resp = await self.call(
                call.RequestStartTransaction(
                    id_token={"id_token": id_token, "type": "Central"},
                    remote_start_id=remote_start_id,
                    evse_id=evse_id,
                )
            )
            logger.info(f"[v201] RequestStartTransaction {self.id} → {getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"[v201] RequestStartTransaction failed for {self.id}: {e}", exc_info=True)
            return None

    async def request_stop_transaction(self, transaction_id: str):
        """RequestStopTransaction — 2.0.1's remote stop. Takes the charger's
        own string transaction id, not our internal integer."""
        try:
            logger.info(f"[v201] RequestStopTransaction → {self.id}: txn={transaction_id}")
            resp = await self.call(
                call.RequestStopTransaction(transaction_id=str(transaction_id))
            )
            logger.info(f"[v201] RequestStopTransaction {self.id} → {getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"[v201] RequestStopTransaction failed for {self.id}: {e}", exc_info=True)
            return None

    # ── 1.6-shaped adapters ───────────────────────────────────────────────
    # Ten call sites across the API, OCPI router and scheduler reach for the
    # 1.6 method names on whatever comes out of active_charge_points, which
    # now holds either handler. Translating here keeps every one of them
    # working untouched, rather than sprinkling version checks through code
    # that has no business knowing the protocol version. Both return the
    # native 2.0.1 response, whose `.status` is "Accepted"/"Rejected" just
    # like the 1.6 one, so existing result handling needs no change either.

    async def remote_start_transaction(self, connector_id: int = 1, id_tag: str = "APP_USER"):
        """1.6-shaped remote start. 1.6's connector_id maps to 2.0.1's evse_id:
        on the DC units in the fleet each gun is its own EVSE, so the numbering
        lines up."""
        return await self.request_start_transaction(evse_id=connector_id, id_token=id_tag)

    async def remote_stop_transaction(self, transaction_id: int):
        """1.6-shaped remote stop.

        Callers hold our internal integer transaction id; the charger only
        knows the string it minted. Resolve one to the other before sending.
        """
        ocpp_txn = None
        try:
            session = (
                self.db.query(ChargingSession)
                .filter(ChargingSession.transaction_id == int(transaction_id))
                .first()
            )
            if session:
                ocpp_txn = session.ocpp_transaction_id
        except Exception as e:
            logger.error(f"[v201] could not resolve transaction {transaction_id} for {self.id}: {e}")

        if not ocpp_txn:
            logger.error(
                f"[v201] cannot stop transaction {transaction_id} on {self.id}: "
                f"no ocpp_transaction_id recorded for it"
            )
            return None
        return await self.request_stop_transaction(ocpp_txn)

    # ── Device model ──────────────────────────────────────────────────────

    async def get_variables(self, items):
        """GetVariables. `items` is a list of (component, variable) pairs."""
        try:
            data = [
                {"component": {"name": comp}, "variable": {"name": var}}
                for comp, var in items
            ]
            logger.info(f"[v201] GetVariables → {self.id}: {items}")
            return await self.call(call.GetVariables(get_variable_data=data))
        except Exception as e:
            logger.error(f"[v201] GetVariables failed for {self.id}: {e}", exc_info=True)
            return None

    async def set_variables(self, items):
        """SetVariables. `items` is a list of (component, variable, value)."""
        try:
            data = [
                {"component": {"name": comp}, "variable": {"name": var},
                 "attribute_value": str(value)}
                for comp, var, value in items
            ]
            logger.info(f"[v201] SetVariables → {self.id}: {items}")
            return await self.call(call.SetVariables(set_variable_data=data))
        except Exception as e:
            logger.error(f"[v201] SetVariables failed for {self.id}: {e}", exc_info=True)
            return None

    async def get_base_report(self, report_base: str = "ConfigurationInventory"):
        """Ask the charger to publish its device model.

        This is 2.0.1's answer to "GetConfiguration with no keys". The reply
        here only acknowledges the request — the content arrives afterwards as
        one or more NotifyReport calls, which the handler below logs.
        """
        try:
            request_id = int(uuid.uuid4().int % 2_000_000_000)
            logger.info(f"[v201] GetBaseReport → {self.id}: {report_base} (request_id={request_id})")
            return await self.call(
                call.GetBaseReport(request_id=request_id, report_base=report_base)
            )
        except Exception as e:
            logger.error(f"[v201] GetBaseReport failed for {self.id}: {e}", exc_info=True)
            return None

    @on("NotifyReport")
    async def on_notify_report(self, request_id: int, generated_at: str, seq_no: int, **kwargs):
        """Device model contents, streamed in response to GetBaseReport."""
        data = kwargs.get("report_data") or kwargs.get("reportData") or []
        more = kwargs.get("tbc") or kwargs.get("tbC") or False
        logger.info(
            f"[v201] NotifyReport from {self.id}: request_id={request_id} seq={seq_no} "
            f"entries={len(data)} more_to_come={more}"
        )
        for entry in data:
            comp = (entry.get("component") or {}).get("name")
            var = (entry.get("variable") or {}).get("name")
            attrs = entry.get("variable_attribute") or entry.get("variableAttribute") or []
            value = attrs[0].get("value") if attrs else None
            logger.info(f"[v201]   {comp}.{var} = {value}")
        return call_result.NotifyReport()

    # ── 1.6-shaped adapters over the device model ─────────────────────────
    # 1.6 has a flat key space; 2.0.1 addresses (component, variable). There
    # is no lossless translation, so this maps the handful of keys the
    # platform actually asks for and otherwise expects the caller to pass
    # "Component.Variable". Anything it cannot place is reported back as an
    # unknown key rather than silently guessed at.

    _KEY_MAP = {
        "heartbeatinterval": ("OCPPCommCtrlr", "HeartbeatInterval"),
        "websocketpinginterval": ("OCPPCommCtrlr", "WebSocketPingInterval"),
        "resetretries": ("OCPPCommCtrlr", "ResetRetries"),
        "authorizeremotetxrequests": ("AuthCtrlr", "AuthorizeRemoteStart"),
        "localauthlistenabled": ("LocalAuthListCtrlr", "Enabled"),
        "metervaluesampleinterval": ("SampledDataCtrlr", "TxUpdatedInterval"),
        "connectiontimeout": ("TxCtrlr", "EVConnectionTimeOut"),
    }

    def _resolve_key(self, key: str):
        """1.6 key → (component, variable), or None if it cannot be placed."""
        if "." in key:
            comp, _, var = key.partition(".")
            return comp, var
        return self._KEY_MAP.get(key.strip().lower())

    async def get_configuration(self, keys=None):
        """1.6-shaped read. Returns an object exposing configuration_key and
        unknown_key so the existing /configuration endpoint works unchanged."""

        class _Result:
            def __init__(self, configuration_key, unknown_key):
                self.configuration_key = configuration_key
                self.unknown_key = unknown_key

        if not keys:
            # 2.0.1 has no "give me everything" on GetVariables — that is what
            # GetBaseReport is for, and it answers asynchronously. Say so
            # rather than returning an empty list that reads as "no config".
            logger.info(f"[v201] {self.id}: full-config read requested — issuing GetBaseReport")
            await self.get_base_report()
            return _Result([], ["<full inventory requested via GetBaseReport; "
                                "contents arrive asynchronously in the log>"])

        resolved, unknown = [], []
        for k in keys:
            pair = self._resolve_key(k)
            if pair:
                resolved.append((k, pair))
            else:
                unknown.append(k)

        config_key = []
        if resolved:
            resp = await self.get_variables([p for _, p in resolved])
            results = getattr(resp, "get_variable_result", None) or []
            for (orig, _pair), item in zip(resolved, results):
                status = item.get("attribute_status") or item.get("attributeStatus")
                if status == "Accepted":
                    config_key.append({
                        "key": orig,
                        "readonly": False,
                        "value": item.get("attribute_value") or item.get("attributeValue"),
                    })
                else:
                    unknown.append(orig)

        return _Result(config_key, unknown)

    async def change_configuration(self, key: str, value: str):
        """1.6-shaped write, translated to SetVariables."""
        pair = self._resolve_key(key)
        if not pair:
            logger.error(
                f"[v201] cannot set {key!r} on {self.id}: no component known for it. "
                f"Pass it as 'Component.Variable'."
            )
            return None
        comp, var = pair
        return await self.set_variables([(comp, var, value)])

    # ── Everyday operations ───────────────────────────────────────────────
    # Same names and signatures as the 1.6 handler, so the OCPP console, the
    # ops panel and the scheduler all work against a 2.0.1 charger without
    # knowing the difference.

    # The two versions do not share reset vocabulary: 1.6 says Soft/Hard,
    # 2.0.1 says OnIdle/Immediate. Callers pass whatever the 1.6 console sends,
    # so translate. Soft waits for the station to be idle; Hard reboots now.
    _RESET_TYPES = {"soft": "OnIdle", "hard": "Immediate"}

    async def reset(self, type: str = "Soft", evse_id: Optional[int] = None):
        """Reboot. 2.0.1 can target a single EVSE; 1.6 could only reset the
        whole station, so evse_id stays optional."""
        try:
            mapped = self._RESET_TYPES.get(str(type).strip().lower(), type)
            logger.info(f"[v201] Reset → {self.id}: type={type} -> {mapped} evse={evse_id}")
            kw: Dict[str, Any] = {"type": mapped}
            if evse_id:
                kw["evse_id"] = evse_id
            return await self.call(call.Reset(**kw))
        except Exception as e:
            logger.error(f"[v201] Reset failed for {self.id}: {e}", exc_info=True)
            return None

    async def change_availability(self, connector_id: int = 0, type: str = "Operative"):
        """Take a socket in or out of service.

        1.6 said Operative/Inoperative with a connector id where 0 meant the
        whole station. 2.0.1 keeps the two words but addresses an EVSE object,
        and omitting it means the station — so connector 0 maps to leaving
        `evse` out entirely.
        """
        try:
            logger.info(f"[v201] ChangeAvailability → {self.id}: {type} connector={connector_id}")
            kw: Dict[str, Any] = {"operational_status": type}
            if connector_id:
                kw["evse"] = {"id": connector_id}
            return await self.call(call.ChangeAvailability(**kw))
        except Exception as e:
            logger.error(f"[v201] ChangeAvailability failed for {self.id}: {e}", exc_info=True)
            return None

    async def unlock_connector(self, connector_id: int = 1):
        """Release a latched cable. 2.0.1 needs the EVSE and the connector
        within it; one connector per EVSE makes the inner id 1."""
        try:
            logger.info(f"[v201] UnlockConnector → {self.id}: evse={connector_id}")
            return await self.call(
                call.UnlockConnector(evse_id=connector_id, connector_id=1)
            )
        except Exception as e:
            logger.error(f"[v201] UnlockConnector failed for {self.id}: {e}", exc_info=True)
            return None

    async def trigger_message(self, requested_message: str, connector_id: Optional[int] = None):
        """Ask the charger to send something now rather than wait for it."""
        try:
            logger.info(
                f"[v201] TriggerMessage → {self.id}: {requested_message} evse={connector_id}"
            )
            kw: Dict[str, Any] = {"requested_message": requested_message}
            if connector_id:
                # StatusNotification is reported per connector, not per EVSE, so
                # naming only the EVSE leaves the charger without enough to act
                # on and it answers Rejected. Each gun here is an EVSE with a
                # single connector, so that connector is always 1.
                kw["evse"] = {"id": connector_id, "connector_id": 1}
            return await self.call(call.TriggerMessage(**kw))
        except Exception as e:
            logger.error(f"[v201] TriggerMessage failed for {self.id}: {e}", exc_info=True)
            return None

    async def data_transfer(self, vendor_id: str, message_id: Optional[str] = None,
                            data: Optional[Any] = None):
        """Vendor extension channel — how the AION-specific features are
        driven on the 1.6 side."""
        try:
            kw: Dict[str, Any] = {"vendor_id": vendor_id}
            if message_id is not None:
                kw["message_id"] = message_id
            if data is not None:
                kw["data"] = data
            logger.info(f"[v201] DataTransfer → {self.id}: vendor={vendor_id} msg={message_id}")
            return await self.call(call.DataTransfer(**kw))
        except Exception as e:
            logger.error(f"[v201] DataTransfer failed for {self.id}: {e}", exc_info=True)
            return None

    async def update_firmware(self, location: str, retrieve_date: str,
                              retries: Optional[int] = None,
                              retry_interval: Optional[int] = None):
        """Over-the-air update.

        1.6 took a bare URL and date. 2.0.1 wraps them in a firmware object
        and adds a request_id, which is what ties the FirmwareStatusNotification
        stream back to this particular request.
        """
        try:
            request_id = int(uuid.uuid4().int % 2_000_000_000)
            kw: Dict[str, Any] = {
                "request_id": request_id,
                "firmware": {"location": location, "retrieve_date_time": retrieve_date},
            }
            if retries is not None:
                kw["retries"] = retries
            if retry_interval is not None:
                kw["retry_interval"] = retry_interval
            logger.info(f"[v201] UpdateFirmware → {self.id}: {location} (request_id={request_id})")
            return await self.call(call.UpdateFirmware(**kw))
        except Exception as e:
            logger.error(f"[v201] UpdateFirmware failed for {self.id}: {e}", exc_info=True)
            return None

    # ── Smart charging ────────────────────────────────────────────────────

    async def set_charging_profile(self, connector_id: int, cs_charging_profiles: Dict):
        """Impose a power or current limit.

        Argument names follow the 1.6 handler because the existing endpoint
        passes a profile dict straight through. The dict must already be in
        2.0.1 shape: the two schemas differ enough that quietly translating
        would hand the charger a profile the operator did not write.
        """
        try:
            logger.info(f"[v201] SetChargingProfile → {self.id}: evse={connector_id}")
            return await self.call(
                call.SetChargingProfile(
                    evse_id=connector_id, charging_profile=cs_charging_profiles
                )
            )
        except Exception as e:
            logger.error(f"[v201] SetChargingProfile failed for {self.id}: {e}", exc_info=True)
            return None

    async def clear_charging_profile(self, id: Optional[int] = None,
                                     connector_id: Optional[int] = None,
                                     charging_profile_purpose: Optional[str] = None,
                                     stack_level: Optional[int] = None):
        """Remove one profile by id, or everything matching the criteria."""
        try:
            kw: Dict[str, Any] = {}
            if id is not None:
                kw["charging_profile_id"] = id
            criteria: Dict[str, Any] = {}
            if connector_id is not None:
                criteria["evse_id"] = connector_id
            if charging_profile_purpose:
                criteria["charging_profile_purpose"] = charging_profile_purpose
            if stack_level is not None:
                criteria["stack_level"] = stack_level
            if criteria:
                kw["charging_profile_criteria"] = criteria
            logger.info(f"[v201] ClearChargingProfile → {self.id}: {kw}")
            return await self.call(call.ClearChargingProfile(**kw))
        except Exception as e:
            logger.error(f"[v201] ClearChargingProfile failed for {self.id}: {e}", exc_info=True)
            return None

    async def get_composite_schedule(self, connector_id: int, duration: int,
                                     charging_rate_unit: Optional[str] = None):
        """Ask what limit the charger will actually apply once every stacked
        profile is resolved — the answer that matters when profiles overlap,
        and the one to check against real meter readings."""
        try:
            kw: Dict[str, Any] = {"evse_id": connector_id, "duration": duration}
            if charging_rate_unit:
                kw["charging_rate_unit"] = charging_rate_unit
            logger.info(f"[v201] GetCompositeSchedule → {self.id}: evse={connector_id} {duration}s")
            return await self.call(call.GetCompositeSchedule(**kw))
        except Exception as e:
            logger.error(f"[v201] GetCompositeSchedule failed for {self.id}: {e}", exc_info=True)
            return None

    async def get_charging_profiles(self, evse_id: Optional[int] = None,
                                    charging_profile: Optional[Dict] = None):
        """List installed profiles. The contents arrive asynchronously as
        ReportChargingProfiles, the same pattern GetBaseReport uses."""
        try:
            request_id = int(uuid.uuid4().int % 2_000_000_000)
            kw: Dict[str, Any] = {
                "request_id": request_id,
                "charging_profile": charging_profile or {},
            }
            if evse_id is not None:
                kw["evse_id"] = evse_id
            logger.info(f"[v201] GetChargingProfiles → {self.id} (request_id={request_id})")
            return await self.call(call.GetChargingProfiles(**kw))
        except Exception as e:
            logger.error(f"[v201] GetChargingProfiles failed for {self.id}: {e}", exc_info=True)
            return None

    # ── Not implemented yet ───────────────────────────────────────────────
    # active_charge_points holds both handler types, so an operator picking a
    # 2.0.1 charger in the console reaches these by the 1.6 name. Without a
    # stub that is an AttributeError surfacing as a 500 with no explanation.
    # Raise something that says which operation is missing and what the 2.0.1
    # equivalent is called, so the message reaching the operator is useful.

    def _unsupported(self, op: str, equivalent: str):
        raise OcppOperationUnsupported(
            f"{op} is not implemented for OCPP 2.0.1 yet "
            f"({self.id} is connected over 2.0.1). The 2.0.1 equivalent is {equivalent}."
        )

    async def clear_cache(self, *a, **kw):
        self._unsupported("ClearCache", "ClearCache — same name, not wired up")

    async def get_diagnostics(self, *a, **kw):
        self._unsupported("GetDiagnostics", "GetLog")

    async def get_local_list_version(self, *a, **kw):
        self._unsupported("GetLocalListVersion", "GetLocalListVersion — same name, not wired up")

    async def send_local_list(self, *a, **kw):
        self._unsupported("SendLocalList", "SendLocalList — same name, not wired up")

    async def reserve_now(self, *a, **kw):
        self._unsupported("ReserveNow", "ReserveNow — same name, not wired up")

    async def cancel_reservation(self, *a, **kw):
        self._unsupported("CancelReservation", "CancelReservation — same name, not wired up")

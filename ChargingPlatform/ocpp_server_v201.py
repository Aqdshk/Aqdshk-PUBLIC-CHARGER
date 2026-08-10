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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ocpp.routing import on
from ocpp.v201 import ChargePoint as cp201
from ocpp.v201 import call, call_result
from ocpp.v201.enums import AuthorizationStatusEnumType, RegistrationStatusEnumType

from database import Charger, ChargingSession, MeterValue, SessionLocal

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: Optional[str]) -> datetime:
    """OCPP timestamps are ISO-8601 with a zone; the DB columns are naive UTC."""
    if not value:
        return _utcnow()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return _utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
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
                session = ChargingSession(
                    charger_id=charger.id,
                    transaction_id=0,  # replaced with the DB id below
                    ocpp_transaction_id=str(ocpp_txn),
                    evse_id=evse_id,
                    connector_id=connector_id,
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
                # Updated/Ended for a transaction we never saw start — the
                # charger was mid-session when we came up. Recording it beats
                # dropping the energy on the floor.
                session = ChargingSession(
                    charger_id=charger.id,
                    transaction_id=0,
                    ocpp_transaction_id=str(ocpp_txn),
                    evse_id=evse_id,
                    connector_id=connector_id,
                    start_time=_parse_ts(timestamp),
                    status="active",
                    user_id=_token_of(kwargs.get("id_token")),
                )
                self.db.add(session)
                self.db.flush()
                session.transaction_id = session.id
                logger.warning(
                    f"[v201] {self.id}: {event_type} for unknown txn {ocpp_txn} — "
                    f"opened session {session.id} to retain the readings"
                )

            # A TransactionEvent naming an EVSE is proof that EVSE exists, so
            # treat it as a second source for the gun count alongside
            # StatusNotification. Relying on StatusNotification alone is what
            # left gun 2 unreachable on the 1.6 side: the platform only learns
            # of a socket once that socket happens to report, and a charger
            # that reports sparsely stays understated indefinitely.
            self._note_evse(charger, evse_id, info.get("charging_state")
                            or info.get("chargingState"), event_type)

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

        return call_result.TransactionEvent()

    def _note_evse(self, charger, evse_id, charging_state, event_type):
        """Record a gun seen on a transaction, and reflect its live state.

        Keeps the same slot map StatusNotification writes, so the dashboard
        renders 2.0.1 chargers through the existing per-gun display.
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
        else:
            conn_map[slot] = "charging"

        charger.connector_status = json.dumps(conn_map)

        slots = len(conn_map)
        highest_plain = max((int(k) for k in conn_map if str(k).isdigit()), default=0)
        detected = max(slots, highest_plain)
        if detected > (charger.number_of_connectors or 1):
            charger.number_of_connectors = detected

        best = min(conn_map.values(), key=lambda s: _RANK.get(s, 7), default=None)
        if best:
            charger.availability = best

    def _store_meter_values(self, charger, session, meter_values, evse_id, connector_id):
        """Persist readings, returning the newest cumulative kWh seen.

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
                    connector_id=connector_id,
                    transaction_id=session.transaction_id,
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

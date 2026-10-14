"""
OCPP message trace for chargers under vendor test, and the checklist read
off it.

A vendor bringing up a new charger asks two things the platform could not
show them: "what did my charger send, and what did you answer" and "have I
covered everything". Frames were only in the container log, mixed with the
whole fleet and gone after rotation.

Recording is limited to charge points assigned to a vendor account, so the
production fleet's traffic never touches this table. Like connectivity.py,
everything here is best-effort and must never raise into the OCPP connection
handler: a missing log row is acceptable, a dropped charger is not.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from database import (
    ChargerConnectionEvent, ChargingSession, OcppMessageLog, SessionLocal, VendorAccount,
)

logger = logging.getLogger(__name__)

RETENTION_DAYS = 14
MAX_PAYLOAD_CHARS = 8000
_WATCH_TTL_SECONDS = 20
_PRUNE_EVERY = 500

_lock = threading.Lock()
_watched: frozenset = frozenset()
_watched_loaded_at = 0.0
# (charge_point_id, unique_id) -> action, so a reply can be labelled with the
# call it answers. Bounded: a charger that never replies must not grow it.
_pending: "OrderedDict[tuple, str]" = OrderedDict()
_PENDING_MAX = 2000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None


# ── Which chargers are recorded ──────────────────────────────────────────────

def invalidate() -> None:
    """Forget the cached watch list; the next frame reloads it."""
    global _watched_loaded_at
    _watched_loaded_at = 0.0


def watched_ids() -> frozenset:
    """Charge point ids assigned to a usable vendor account, cached briefly."""
    global _watched, _watched_loaded_at
    now = time.monotonic()
    if _watched_loaded_at and now - _watched_loaded_at < _WATCH_TTL_SECONDS:
        return _watched
    db = SessionLocal()
    try:
        ids = set()
        for v in db.query(VendorAccount).filter(VendorAccount.is_active.is_(True)).all():
            if v.is_usable():
                ids.update(v.charger_ids())
        _watched = frozenset(ids)
    except Exception as e:
        logger.warning("[trace] could not load watch list: %s", e)
    finally:
        db.close()
        _watched_loaded_at = now
    return _watched


def is_watched(charge_point_id: str) -> bool:
    return charge_point_id in watched_ids()


# ── Recording ────────────────────────────────────────────────────────────────

def record(charge_point_id: str, direction: str, raw: Any) -> None:
    """Store one frame if this charger is under test. Never raises."""
    try:
        if not is_watched(charge_point_id):
            return
        text = raw if isinstance(raw, str) else str(raw)
        message_type = unique_id = action = None
        try:
            frame = json.loads(text)
            if isinstance(frame, list) and len(frame) >= 2:
                message_type = int(frame[0])
                unique_id = str(frame[1])[:64]
                key = (charge_point_id, unique_id)
                if message_type == 2 and len(frame) >= 3:
                    action = str(frame[2])[:64]
                    with _lock:
                        _pending[key] = action
                        while len(_pending) > _PENDING_MAX:
                            _pending.popitem(last=False)
                else:
                    with _lock:
                        action = _pending.pop(key, None)
        except (ValueError, TypeError):
            pass  # not JSON: keep the raw text, it is the interesting case

        db = SessionLocal()
        try:
            db.add(OcppMessageLog(
                charge_point_id=charge_point_id,
                at=_utcnow(),
                direction=direction,
                message_type=message_type,
                unique_id=unique_id,
                action=action,
                payload=text[:MAX_PAYLOAD_CHARS],
            ))
            db.commit()
            if random.randrange(_PRUNE_EVERY) == 0:
                cutoff = _utcnow() - timedelta(days=RETENTION_DAYS)
                db.query(OcppMessageLog).filter(OcppMessageLog.at < cutoff).delete(synchronize_session=False)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("[trace] could not record frame for %s: %s", charge_point_id, e)
        finally:
            db.close()
    except Exception as e:  # pragma: no cover - last line of defence
        logger.debug("[trace] record failed for %s: %s", charge_point_id, e)


def attach(charge_point: Any) -> None:
    """
    Tap a ChargePoint's receive and send paths.

    Wrapping the two methods on the instance covers both OCPP stacks with one
    call, since 1.6 and 2.0.1 handlers share the library's route_message and
    _send. The originals are always called, whatever the tap does.
    """
    cp_id = getattr(charge_point, "id", None)
    if not cp_id:
        return
    original_route = charge_point.route_message
    original_send = charge_point._send

    async def route_message(raw_msg):
        record(cp_id, "in", raw_msg)
        return await original_route(raw_msg)

    async def _send(message):
        record(cp_id, "out", message)
        return await original_send(message)

    charge_point.route_message = route_message
    charge_point._send = _send


# ── Reading ──────────────────────────────────────────────────────────────────

def _row(m: OcppMessageLog) -> dict:
    return {
        "id": m.id,
        "at": _iso(m.at),
        "direction": m.direction,
        "type": m.message_type,
        "unique_id": m.unique_id,
        "action": m.action,
        "payload": m.payload,
    }


def read(db: Any, charge_point_id: str, after_id: int = 0, limit: int = 200) -> List[dict]:
    """
    Frames in the order they happened. With after_id, what came after it;
    without, the newest `limit` frames.
    """
    limit = max(1, min(int(limit or 200), 1000))
    q = db.query(OcppMessageLog).filter(OcppMessageLog.charge_point_id == charge_point_id)
    if after_id:
        rows = q.filter(OcppMessageLog.id > after_id).order_by(OcppMessageLog.id.asc()).limit(limit).all()
    else:
        rows = list(reversed(q.order_by(OcppMessageLog.id.desc()).limit(limit).all()))
    return [_row(m) for m in rows]


def latest_id(db: Any, charge_point_id: str) -> int:
    value = (
        db.query(func.max(OcppMessageLog.id))
        .filter(OcppMessageLog.charge_point_id == charge_point_id)
        .scalar()
    )
    return int(value or 0)


# ── Checklist ────────────────────────────────────────────────────────────────

# OCPP 2.0.1 names for the 1.6 actions the checklist is written in.
_V201_ALIAS = {
    "RemoteStartTransaction": "RequestStartTransaction",
    "RemoteStopTransaction": "RequestStopTransaction",
    "GetConfiguration": "GetVariables",
    "ChangeConfiguration": "SetVariables",
}


def _payload_of(row: OcppMessageLog) -> dict:
    """The payload object of a frame: index 3 of a Call, 2 of a CallResult."""
    try:
        frame = json.loads(row.payload or "")
        body = frame[3] if row.message_type == 2 else frame[2]
        return body if isinstance(body, dict) else {}
    except (ValueError, TypeError, IndexError):
        return {}


class _Frames:
    """The frames of one charger after a starting point, queried by action."""

    def __init__(self, db: Any, charge_point_id: str, since_id: int):
        self.db = db
        self.cp = charge_point_id
        self.since = since_id
        counts = (
            db.query(
                OcppMessageLog.action, OcppMessageLog.direction,
                OcppMessageLog.message_type, func.count(OcppMessageLog.id),
            )
            .filter(OcppMessageLog.charge_point_id == charge_point_id, OcppMessageLog.id > since_id)
            .group_by(OcppMessageLog.action, OcppMessageLog.direction, OcppMessageLog.message_type)
            .all()
        )
        self.counts: Dict[tuple, int] = {(a, d, t): n for a, d, t, n in counts}

    def _names(self, action: str) -> List[str]:
        alias = _V201_ALIAS.get(action)
        return [action, alias] if alias else [action]

    def count(self, action: str, direction: str, message_type: int) -> int:
        return sum(self.counts.get((a, direction, message_type), 0) for a in self._names(action))

    def rows(self, action: str, direction: str, message_type: int, limit: int = 20, oldest_first: bool = False):
        if not self.count(action, direction, message_type):
            return []
        q = self.db.query(OcppMessageLog).filter(
            OcppMessageLog.charge_point_id == self.cp,
            OcppMessageLog.id > self.since,
            OcppMessageLog.action.in_(self._names(action)),
            OcppMessageLog.direction == direction,
            OcppMessageLog.message_type == message_type,
        )
        order = OcppMessageLog.id.asc() if oldest_first else OcppMessageLog.id.desc()
        return q.order_by(order).limit(limit).all()

    def error_count(self, action: str, direction: str) -> int:
        return self.count(action, direction, 4)


def _item(key: str, group: str, title: str, state: str, detail: str = "",
          at: Optional[datetime] = None, optional: bool = False) -> dict:
    return {
        "key": key, "group": group, "title": title, "state": state,
        "detail": detail, "at": _iso(at), "optional": optional,
    }


def _command_item(f: _Frames, key: str, group: str, title: str, action: str,
                  ok: tuple = ("Accepted",), optional: bool = True) -> dict:
    """A command we send and the charger answers with a status."""
    sent = f.count(action, "out", 2)
    if not sent:
        return _item(key, group, title, "waiting", "Not sent yet", optional=optional)
    replies = f.rows(action, "in", 3, limit=5)
    if not replies:
        if f.error_count(action, "in"):
            return _item(key, group, title, "fail", "Charger answered with a CallError", optional=optional)
        return _item(key, group, title, "fail", "Sent, but the charger did not answer", optional=optional)
    for r in replies:
        status = _payload_of(r).get("status")
        if status is None or status in ok:
            return _item(key, group, title, "pass", f"Charger answered {status or 'OK'}", r.at, optional)
    return _item(
        key, group, title, "fail",
        f"Charger answered {_payload_of(replies[0]).get('status')}", replies[0].at, optional,
    )


def checklist(db: Any, charge_point_id: str, since_id: int = 0) -> dict:
    """
    What the trace shows this charger has done, as a pass / waiting / fail
    list. Every verdict comes from frames actually exchanged after since_id,
    so a tester can start a clean run without anything being deleted.
    """
    f = _Frames(db, charge_point_id, since_id)
    items: List[dict] = []
    since_at = None
    if since_id:
        first = db.query(OcppMessageLog).filter(OcppMessageLog.id == since_id).first()
        since_at = first.at if first else None

    # ── Connection ──
    g = "Connection"
    conn_q = db.query(ChargerConnectionEvent).filter(
        ChargerConnectionEvent.charge_point_id == charge_point_id,
        ChargerConnectionEvent.event == "connected",
    )
    if since_at:
        conn_q = conn_q.filter(ChargerConnectionEvent.at >= since_at)
    conn = conn_q.order_by(ChargerConnectionEvent.id.desc()).first()
    if conn:
        items.append(_item("connect", g, "WebSocket connected", "pass", conn.detail or "", conn.at))
    elif any(n for (_a, d, _t), n in f.counts.items() if d == "in"):
        items.append(_item("connect", g, "WebSocket connected", "pass", "Frames are arriving"))
    else:
        items.append(_item("connect", g, "WebSocket connected", "waiting", "No connection seen yet"))

    boots = f.rows("BootNotification", "in", 2, limit=5)
    boot_replies = f.rows("BootNotification", "out", 3, limit=5)
    if not boots:
        items.append(_item("boot", g, "BootNotification accepted", "waiting", "Not received yet"))
    else:
        b = _payload_of(boots[0])
        station = b.get("chargingStation") or {}
        described = " / ".join(str(x) for x in (
            b.get("chargePointVendor") or station.get("vendorName"),
            b.get("chargePointModel") or station.get("model"),
            b.get("firmwareVersion") or station.get("firmwareVersion"),
        ) if x)
        status = _payload_of(boot_replies[0]).get("status") if boot_replies else None
        if status == "Accepted":
            items.append(_item("boot", g, "BootNotification accepted", "pass", described, boots[0].at))
        else:
            items.append(_item(
                "boot", g, "BootNotification accepted", "fail",
                f"{described} (answered {status or 'nothing'})", boots[0].at,
            ))

    hb = f.count("Heartbeat", "in", 2)
    hb_last = f.rows("Heartbeat", "in", 2, limit=1)
    items.append(_item(
        "heartbeat", g, "Heartbeat", "pass" if hb else "waiting",
        f"{hb} received" if hb else "Not received yet", hb_last[0].at if hb_last else None,
    ))

    sn = f.rows("StatusNotification", "in", 2, limit=1)
    if sn:
        p = _payload_of(sn[0])
        where = p.get("connectorId", p.get("evseId"))
        items.append(_item(
            "status", g, "StatusNotification", "pass",
            f"Connector {where}: {p.get('status') or p.get('connectorStatus')}", sn[0].at,
        ))
    else:
        items.append(_item("status", g, "StatusNotification", "waiting", "Not received yet"))

    # ── Charging ──
    g = "Charging and billing"
    items.append(_command_item(f, "remote_start", g, "RemoteStartTransaction accepted",
                               "RemoteStartTransaction", optional=False))

    auth = f.rows("Authorize", "in", 2, limit=1)
    items.append(_item(
        "authorize", g, "Authorize (RFID or local start)", "pass" if auth else "waiting",
        f"idTag {_payload_of(auth[0]).get('idTag')}" if auth else "Only needed for card or local starts",
        auth[0].at if auth else None, optional=True,
    ))

    is_v201 = bool(f.count("TransactionEvent", "in", 2))
    if is_v201:
        events = f.rows("TransactionEvent", "in", 2, limit=200)
        started = [e for e in events if _payload_of(e).get("eventType") == "Started"]
        ended = [e for e in events if _payload_of(e).get("eventType") == "Ended"]
        metered = [e for e in events if _payload_of(e).get("meterValue")]
        items.append(_item("start_tx", g, "TransactionEvent Started", "pass" if started else "waiting",
                           "Received" if started else "Not received yet", started[0].at if started else None))
        items.append(_item("meter", g, "Meter values during charging", "pass" if metered else "waiting",
                           f"{len(metered)} event(s) with readings" if metered else "Not received yet",
                           metered[0].at if metered else None))
    else:
        st = f.rows("StartTransaction", "in", 2, limit=1)
        st_reply = f.rows("StartTransaction", "out", 3, limit=1)
        if st:
            p = _payload_of(st[0])
            txn = _payload_of(st_reply[0]).get("transactionId") if st_reply else None
            items.append(_item(
                "start_tx", g, "StartTransaction", "pass",
                f"Connector {p.get('connectorId')}, meterStart {p.get('meterStart')} Wh, transaction {txn}",
                st[0].at,
            ))
        else:
            items.append(_item("start_tx", g, "StartTransaction", "waiting", "Not received yet"))

        mv_count = f.count("MeterValues", "in", 2)
        mv = f.rows("MeterValues", "in", 2, limit=10)
        if mv:
            has_energy = any(
                "Energy.Active.Import.Register" in (r.payload or "") or '"measurand"' not in (r.payload or "")
                for r in mv
            )
            items.append(_item(
                "meter", g, "MeterValues with energy register",
                "pass" if has_energy else "fail",
                f"{mv_count} received" if has_energy
                else f"{mv_count} received, none with Energy.Active.Import.Register",
                mv[0].at,
            ))
        else:
            items.append(_item("meter", g, "MeterValues with energy register", "waiting", "Not received yet"))

    items.append(_command_item(f, "remote_stop", g, "RemoteStopTransaction accepted",
                               "RemoteStopTransaction", optional=False))

    if is_v201:
        items.append(_item("stop_tx", g, "TransactionEvent Ended", "pass" if ended else "waiting",
                           "Received" if ended else "Not received yet", ended[0].at if ended else None))
    else:
        sp = f.rows("StopTransaction", "in", 2, limit=1)
        if sp:
            p = _payload_of(sp[0])
            items.append(_item(
                "stop_tx", g, "StopTransaction", "pass",
                f"meterStop {p.get('meterStop')} Wh, reason {p.get('reason') or 'not given'}", sp[0].at,
            ))
        else:
            items.append(_item("stop_tx", g, "StopTransaction", "waiting", "Not received yet"))

    items.append(_billing_item(db, charge_point_id, since_at, g))

    # ── Remote control ──
    g = "Remote control"
    items.append(_command_item(f, "trigger", g, "TriggerMessage", "TriggerMessage",
                               ok=("Accepted", "NotImplemented")))
    items.append(_command_item(f, "get_config", g, "GetConfiguration", "GetConfiguration"))
    items.append(_command_item(f, "change_config", g, "ChangeConfiguration", "ChangeConfiguration",
                               ok=("Accepted", "RebootRequired")))
    items.append(_command_item(f, "unlock", g, "UnlockConnector", "UnlockConnector",
                               ok=("Unlocked", "NotSupported")))
    items.append(_command_item(f, "reset", g, "Reset", "Reset"))

    # ── Firmware ──
    items.extend(_firmware_items(f, boots))

    required = [i for i in items if not i["optional"]]
    return {
        "since_id": since_id,
        "latest_id": latest_id(db, charge_point_id),
        "passed": sum(1 for i in required if i["state"] == "pass"),
        "failed": sum(1 for i in required if i["state"] == "fail"),
        "total": len(required),
        "items": items,
    }


def _billing_item(db: Any, charge_point_id: str, since_at: Optional[datetime], group: str) -> dict:
    """A finished session with energy on it, priced at the charger's tariff."""
    from database import Charger  # local: keeps this module's import list short

    title = "Session billed from meter readings"
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if charger is None:
        return _item("billing", group, title, "waiting", "Charger has not registered yet")
    q = db.query(ChargingSession).filter(
        ChargingSession.charger_id == charger.id,
        ChargingSession.stop_time.isnot(None),
    )
    if since_at:
        # Session clocks are Malaysia wall time; the trace is UTC.
        q = q.filter(ChargingSession.start_time >= since_at + timedelta(hours=8))
    s = q.order_by(ChargingSession.id.desc()).first()
    if s is None:
        return _item("billing", group, title, "waiting", "No finished session yet")
    energy = float(s.energy_consumed or 0)
    if s.meter_start is not None and s.meter_stop is not None and s.meter_stop >= s.meter_start:
        energy = max(energy, (s.meter_stop - s.meter_start) / 1000.0)
    tariff = float(charger.tariff_per_kwh or 0)
    if energy <= 0:
        return _item("billing", group, title, "fail",
                     f"Transaction {s.transaction_id} finished with 0 kWh recorded", None)
    return _item(
        "billing", group, title, "pass",
        f"Transaction {s.transaction_id}: {energy:.3f} kWh x RM {tariff:.2f} = RM {energy * tariff:.2f}",
    )


_FW_STEPS = ("Downloading", "Downloaded", "Installing", "Installed")
_FW_FAILURES = ("DownloadFailed", "InstallationFailed", "InstallVerificationFailed", "InvalidSignature")


def _firmware_items(f: _Frames, boots: list) -> List[dict]:
    g = "Firmware update"
    out: List[dict] = []
    requests = f.rows("UpdateFirmware", "out", 2, limit=1)
    if not requests:
        out.append(_item("fw_request", g, "UpdateFirmware accepted", "waiting", "Not sent yet"))
    else:
        req = requests[0]
        answered = [r for r in f.rows("UpdateFirmware", "in", 3, limit=5) if r.id > req.id]
        location = _payload_of(req).get("location") or (_payload_of(req).get("firmware") or {}).get("location")
        out.append(_item(
            "fw_request", g, "UpdateFirmware accepted",
            "pass" if answered else "fail",
            f"Location {location}" if answered else "Sent, but the charger did not answer", req.at,
        ))

    after = requests[0].id if requests else 0
    notes = [r for r in f.rows("FirmwareStatusNotification", "in", 2, limit=50, oldest_first=True) if r.id > after]
    seen = {}
    for r in notes:
        seen.setdefault(_payload_of(r).get("status"), r)
    failure = next((s for s in _FW_FAILURES if s in seen), None)
    for step in _FW_STEPS:
        key = "fw_" + step.lower()
        title = f"FirmwareStatusNotification: {step}"
        if step in seen and requests:
            out.append(_item(key, g, title, "pass", "", seen[step].at))
        elif failure and requests:
            out.append(_item(key, g, title, "fail", f"Charger reported {failure}", seen[failure].at))
        else:
            out.append(_item(key, g, title, "waiting", "Not received yet"))

    # The proof an update took: the charger boots again and names a different
    # version from the one it had when the update was requested.
    title = "Reboots on the new firmware version"
    installed = seen.get("Installed")
    if not requests or not installed:
        out.append(_item("fw_boot", g, title, "waiting", "Waiting for the update to finish"))
    else:
        def version(row):
            p = _payload_of(row)
            return p.get("firmwareVersion") or (p.get("chargingStation") or {}).get("firmwareVersion")

        before = next((b for b in boots if b.id < requests[0].id), None)
        newer = next((b for b in boots if b.id > requests[0].id), None)
        if newer is None:
            out.append(_item("fw_boot", g, title, "waiting", "No BootNotification since the update"))
        elif before is not None and version(before) == version(newer):
            out.append(_item("fw_boot", g, title, "fail",
                             f"Still reports {version(newer)} after the update", newer.at))
        else:
            was = f"{version(before)} -> " if before is not None else ""
            out.append(_item("fw_boot", g, title, "pass", f"{was}{version(newer)}", newer.at))
    return out

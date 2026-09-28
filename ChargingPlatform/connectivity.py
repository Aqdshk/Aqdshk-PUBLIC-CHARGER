"""
Charger connectivity: how a charger reaches us, and a log of its link.

Two questions the dashboard could not answer:

1. Is this charger on a SIM or on WiFi? OCPP 1.6 BootNotification carries the
   SIM's ICCID and IMSI when the charger has a modem, and 2.0.1 carries them
   under chargingStation.modem. Both were being dropped on the floor.

2. How stable is its link? Every connect and disconnect was written only to
   the container log, which is capped and rotated. A charger on a weak signal
   was seen dropping every two minutes with close code 1006 while the list
   showed it "online" in between.

Everything here is best-effort and never raises into the OCPP connection
handler: losing a log row is acceptable, dropping a charger's WebSocket
because the log could not be written is not.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from database import Charger, ChargerConnectionEvent, SessionLocal

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
# Pruning runs on roughly one insert in this many, so it costs nothing on
# the hot path and still keeps the table bounded.
_PRUNE_EVERY = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Classification ───────────────────────────────────────────────────────────

# Malaysian mobile network codes (MCC 502). An IMSI starts with MCC + MNC, so
# the operator can be read off it. Three-digit MNCs are checked first.
_MY_MNC = {
    "153": "unifi Mobile",
    "12": "Maxis",
    "17": "Maxis",
    "13": "CelcomDigi (Celcom)",
    "19": "CelcomDigi (Celcom)",
    "16": "CelcomDigi (Digi)",
    "10": "CelcomDigi (Digi)",
    "18": "U Mobile",
}


def operator_from_imsi(imsi: Optional[str]) -> Optional[str]:
    """Mobile operator for an IMSI, or None when it cannot be told."""
    if not imsi or not imsi.isdigit() or len(imsi) < 5:
        return None
    mcc = imsi[:3]
    if mcc != "502":
        return f"Foreign network (MCC {mcc})"
    rest = imsi[3:]
    for mnc in sorted(_MY_MNC, key=len, reverse=True):
        if rest.startswith(mnc):
            return _MY_MNC[mnc]
    return f"Malaysian network (MNC {rest[:2]})"


_OVERRIDE_LABEL = {
    "cellular": "Cellular (SIM)",
    "wifi": "WiFi",
    "ethernet": "Ethernet (LAN)",
}


def classify(charger: Any) -> dict:
    """
    What the dashboard shows for a charger's connection.

    The operator's word wins, then what the charger reported. A charger that
    reports no SIM is "unknown", not "WiFi": many firmwares leave the fields
    out whatever the hardware, and guessing WiFi would be confidently wrong.
    """
    override = (getattr(charger, "connectivity_override", None) or "").strip().lower()
    iccid = getattr(charger, "iccid", None)
    imsi = getattr(charger, "imsi", None)
    operator = operator_from_imsi(imsi)

    if override in _OVERRIDE_LABEL:
        kind = override
        source = "set by operator"
    elif iccid or imsi:
        kind = "cellular"
        source = "SIM reported by charger"
    else:
        kind = "unknown"
        source = "charger reports no SIM"

    label = _OVERRIDE_LABEL.get(kind, "Unknown")
    if kind == "cellular" and operator:
        label = f"{label} · {operator}"

    return {
        "type": kind,
        "label": label,
        "source": source,
        "operator": operator if kind == "cellular" else None,
        "iccid": iccid,
        "imsi": imsi,
        "override": override or None,
        "remote_ip": getattr(charger, "last_remote_ip", None),
    }


# WebSocket close codes, in the words an operator needs.
_CLOSE_CODES = {
    1000: "Closed normally",
    1001: "Charger went away (reboot or shutdown)",
    1002: "Protocol error",
    1005: "Closed without a status",
    1006: "Link dropped (no close frame: signal, network or power loss)",
    1008: "Rejected by server (policy)",
    1011: "Server error",
    1012: "Server restarting",
}


def describe_close(code: Optional[int], reason: Optional[str]) -> Optional[str]:
    if code is None:
        return reason or None
    text = _CLOSE_CODES.get(code, f"Close code {code}")
    return f"{text}: {reason}" if reason else text


# ── Recording ────────────────────────────────────────────────────────────────

def remote_ip_of(websocket: Any) -> Optional[str]:
    """The charger's public address, preferring what a proxy forwarded."""
    try:
        headers = getattr(getattr(websocket, "request", None), "headers", None)
        if headers is not None:
            for name in ("X-Real-IP", "X-Forwarded-For"):
                value = headers.get(name)
                if value:
                    return value.split(",")[0].strip()[:64]
        addr = getattr(websocket, "remote_address", None)
        if addr:
            return str(addr[0])[:64]
    except Exception:
        pass
    return None


def record_event(
    charge_point_id: str,
    event: str,
    *,
    close_code: Optional[int] = None,
    close_reason: Optional[str] = None,
    remote_ip: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Write one connection event. Never raises."""
    db = SessionLocal()
    try:
        now = _utcnow()
        duration = None
        if event in ("connected", "disconnected"):
            # The opposite edge before this one: a disconnect's duration is how
            # long the link had been up, a connect's is how long it was down.
            opposite = "connected" if event == "disconnected" else "disconnected"
            prev = (
                db.query(ChargerConnectionEvent)
                .filter(
                    ChargerConnectionEvent.charge_point_id == charge_point_id,
                    ChargerConnectionEvent.event.in_(("connected", "disconnected")),
                )
                .order_by(ChargerConnectionEvent.at.desc(), ChargerConnectionEvent.id.desc())
                .first()
            )
            if prev is not None and prev.event == opposite:
                duration = max(0, int((now - prev.at).total_seconds()))

        db.add(
            ChargerConnectionEvent(
                charge_point_id=charge_point_id,
                event=event,
                at=now,
                close_code=close_code,
                close_reason=(close_reason or None) and close_reason[:255],
                remote_ip=remote_ip,
                duration_seconds=duration,
                detail=(detail or None) and detail[:255],
            )
        )
        if event == "connected" and remote_ip:
            charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
            if charger is not None and charger.last_remote_ip != remote_ip:
                charger.last_remote_ip = remote_ip
        db.commit()

        if random.randrange(_PRUNE_EVERY) == 0:
            cutoff = now - timedelta(days=RETENTION_DAYS)
            removed = (
                db.query(ChargerConnectionEvent)
                .filter(ChargerConnectionEvent.at < cutoff)
                .delete(synchronize_session=False)
            )
            db.commit()
            if removed:
                logger.info("[connectivity] pruned %d events older than %d days", removed, RETENTION_DAYS)
    except Exception as e:
        db.rollback()
        logger.warning("[connectivity] could not record %s for %s: %s", event, charge_point_id, e)
    finally:
        db.close()


def record_modem(charge_point_id: str, iccid: Optional[str], imsi: Optional[str]) -> None:
    """Store the SIM identity a BootNotification reported. Never raises."""
    iccid = (iccid or "").strip()[:32] or None
    imsi = (imsi or "").strip()[:20] or None
    db = SessionLocal()
    try:
        charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        if charger is None:
            return
        changed = False
        # Only overwrite with something: a boot that omits the fields says
        # nothing about the SIM having been removed.
        if iccid and charger.iccid != iccid:
            charger.iccid = iccid
            changed = True
        if imsi and charger.imsi != imsi:
            charger.imsi = imsi
            changed = True
        if changed:
            db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("[connectivity] could not store modem info for %s: %s", charge_point_id, e)
    finally:
        db.close()


# ── Reading ──────────────────────────────────────────────────────────────────

def summarize(db: Any, charge_point_id: str, hours: int) -> dict:
    """
    Link statistics over the last `hours`, plus the events themselves.

    Uptime is measured from the event edges: time between a connect and the
    next disconnect counts as up. The state at the start of the window is
    taken from the last edge before it, so a charger that stayed connected
    the whole window reads 100%, not "no data".

    Disconnect counts come from the log, not the charger's say-so, and a
    1006 close (no close frame) is counted separately as an abnormal drop:
    that is what a lost signal looks like from here.
    """
    now = _utcnow()
    since = now - timedelta(hours=hours)

    events = (
        db.query(ChargerConnectionEvent)
        .filter(
            ChargerConnectionEvent.charge_point_id == charge_point_id,
            ChargerConnectionEvent.at >= since,
        )
        .order_by(ChargerConnectionEvent.at.asc(), ChargerConnectionEvent.id.asc())
        .all()
    )
    before = (
        db.query(ChargerConnectionEvent)
        .filter(
            ChargerConnectionEvent.charge_point_id == charge_point_id,
            ChargerConnectionEvent.at < since,
            ChargerConnectionEvent.event.in_(("connected", "disconnected")),
        )
        .order_by(ChargerConnectionEvent.at.desc(), ChargerConnectionEvent.id.desc())
        .first()
    )
    edges = [e for e in events if e.event in ("connected", "disconnected")]

    # Where measurement starts. With an edge before the window, the window's
    # start; without one (the log is newer than the window), the first edge,
    # because nothing is known about the time before it and counting it as
    # offline would be a claim the data cannot support.
    if before is not None:
        start, up = since, before.event == "connected"
    elif edges:
        start, up = edges[0].at, False
    else:
        start, up = None, False

    up_seconds = 0.0
    disconnects = 0
    drops = 0
    longest_down = 0
    if start is not None:
        cursor = start
        for e in edges:
            if e.event == "connected":
                if not up and e.at > start:
                    longest_down = max(longest_down, int((e.at - cursor).total_seconds()))
                up, cursor = True, e.at
            else:
                if up:
                    up_seconds += (e.at - cursor).total_seconds()
                up, cursor = False, e.at
                disconnects += 1
                if e.close_code == 1006:
                    drops += 1
        # The stretch from the last edge to now.
        if up:
            up_seconds += (now - cursor).total_seconds()
        else:
            longest_down = max(longest_down, int((now - cursor).total_seconds()))

    measured = (now - start).total_seconds() if start is not None else 0
    uptime = round(100.0 * up_seconds / measured, 1) if measured > 0 else None

    durations = [e.duration_seconds for e in events if e.event == "disconnected" and e.duration_seconds]
    avg_connection = int(sum(durations) / len(durations)) if durations else None

    return {
        "hours": hours,
        "uptime_percent": uptime,
        "disconnects": disconnects,
        "abnormal_drops": drops,
        "average_connection_seconds": avg_connection,
        "longest_offline_seconds": longest_down if start is not None else None,
        # When the figures start from, if later than the window: the log only
        # exists from the day this was deployed.
        "measured_since": start.replace(tzinfo=timezone.utc).isoformat() if start is not None else None,
        "events": [
            {
                "at": e.at.replace(tzinfo=timezone.utc).isoformat(),
                "event": e.event,
                "close_code": e.close_code,
                "close_text": describe_close(e.close_code, e.close_reason) if e.event == "disconnected" else None,
                "remote_ip": e.remote_ip,
                "duration_seconds": e.duration_seconds,
                "detail": e.detail,
            }
            for e in reversed(events[-300:])
        ],
    }

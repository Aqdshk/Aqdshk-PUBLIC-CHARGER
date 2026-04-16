"""
Edge Sync Router — VPS receives data pushed from local OCPP edge servers (e.g. Banana Pi).

Endpoints:  POST /api/edge/sync/charger-status
            POST /api/edge/sync/session-start
            POST /api/edge/sync/session-stop
            POST /api/edge/sync/meter-value

Auth: Authorization: Bearer <VPS_SYNC_TOKEN>

The Banana Pi runs the same codebase with LOCAL_SERVER_MODE=true and calls these
endpoints after each OCPP event so the VPS dashboard stays up-to-date in real time.
"""
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database import SessionLocal, Charger, ChargingSession, MeterValue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/edge", tags=["Edge Sync"])

_SYNC_TOKEN = os.getenv("VPS_SYNC_TOKEN", "")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _check_auth(authorization: Optional[str]):
    if not _SYNC_TOKEN:
        return  # Token not configured — open (useful in dev)
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, _SYNC_TOKEN):
        raise HTTPException(403, "Invalid edge sync token")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_dt(s: str) -> datetime:
    """Parse ISO-8601 string (with or without Z / offset) to naive UTC datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)


# ─── Payloads ─────────────────────────────────────────────────────────────────

class ChargerStatusPayload(BaseModel):
    charge_point_id: str
    status: Optional[str] = None
    availability: Optional[str] = None
    last_heartbeat: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    connector_type: Optional[str] = None
    max_power_kw: Optional[float] = None
    number_of_connectors: Optional[int] = None


class SessionStartPayload(BaseModel):
    charge_point_id: str
    transaction_id: int
    connector_id: Optional[int] = None
    start_time: str
    meter_start: Optional[int] = None
    user_id: Optional[str] = None


class SessionStopPayload(BaseModel):
    transaction_id: int
    stop_time: str
    meter_stop: Optional[int] = None
    energy_consumed: Optional[float] = None
    stop_reason: Optional[str] = None


class MeterValuePayload(BaseModel):
    charge_point_id: str
    transaction_id: Optional[int] = None
    timestamp: str
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    total_kwh: Optional[float] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/sync/charger-status")
def sync_charger_status(
    payload: ChargerStatusPayload,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)
    db = SessionLocal()
    try:
        charger = db.query(Charger).filter(Charger.charge_point_id == payload.charge_point_id).first()
        if not charger:
            charger = Charger(charge_point_id=payload.charge_point_id)
            db.add(charger)
            logger.info(f"Edge sync: auto-registered charger {payload.charge_point_id}")

        if payload.status is not None:               charger.status              = payload.status
        if payload.availability is not None:         charger.availability        = payload.availability
        if payload.vendor is not None:               charger.vendor              = payload.vendor
        if payload.model is not None:                charger.model               = payload.model
        if payload.firmware_version is not None:     charger.firmware_version    = payload.firmware_version
        if payload.connector_type is not None:       charger.connector_type      = payload.connector_type
        if payload.max_power_kw is not None:         charger.max_power_kw        = payload.max_power_kw
        if payload.number_of_connectors is not None: charger.number_of_connectors = payload.number_of_connectors
        if payload.last_heartbeat is not None:       charger.last_heartbeat      = _parse_dt(payload.last_heartbeat)

        db.commit()
        logger.debug(f"Edge sync charger-status OK: {payload.charge_point_id}")
        return {"status": "ok"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Edge sync charger-status error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))
    finally:
        db.close()


@router.post("/sync/session-start")
def sync_session_start(
    payload: SessionStartPayload,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)
    db = SessionLocal()
    try:
        charger = db.query(Charger).filter(Charger.charge_point_id == payload.charge_point_id).first()
        if not charger:
            # Auto-create charger placeholder so FK is satisfied
            charger = Charger(charge_point_id=payload.charge_point_id)
            db.add(charger)
            db.flush()
            logger.info(f"Edge sync session-start: auto-created charger {payload.charge_point_id}")

        session = db.query(ChargingSession).filter(
            ChargingSession.transaction_id == payload.transaction_id
        ).first()

        if not session:
            session = ChargingSession(
                charger_id=charger.id,
                transaction_id=payload.transaction_id,
                connector_id=payload.connector_id,
                start_time=_parse_dt(payload.start_time),
                meter_start=payload.meter_start,
                user_id=payload.user_id,
                status="active",
            )
            db.add(session)
            logger.info(f"Edge sync: session started tx={payload.transaction_id} charger={payload.charge_point_id}")
        else:
            session.status = "active"  # idempotent

        charger.availability = "charging"
        db.commit()
        return {"status": "ok"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Edge sync session-start error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))
    finally:
        db.close()


@router.post("/sync/session-stop")
def sync_session_stop(
    payload: SessionStopPayload,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)
    db = SessionLocal()
    try:
        session = db.query(ChargingSession).filter(
            ChargingSession.transaction_id == payload.transaction_id
        ).first()

        if not session:
            logger.warning(f"Edge sync session-stop: tx={payload.transaction_id} not found — skipped")
            return {"status": "skipped", "reason": "session not found"}

        session.stop_time = _parse_dt(payload.stop_time)
        session.status = "completed"
        if payload.meter_stop is not None:      session.meter_stop      = payload.meter_stop
        if payload.energy_consumed is not None: session.energy_consumed = payload.energy_consumed
        if payload.stop_reason is not None:     session.stop_reason     = payload.stop_reason

        # Update charger availability
        charger = db.query(Charger).filter(Charger.id == session.charger_id).first()
        if charger:
            charger.availability = "available"

        db.commit()
        logger.info(f"Edge sync: session stopped tx={payload.transaction_id} energy={payload.energy_consumed} kWh")
        return {"status": "ok"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Edge sync session-stop error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))
    finally:
        db.close()


@router.post("/sync/meter-value")
def sync_meter_value(
    payload: MeterValuePayload,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)
    db = SessionLocal()
    try:
        charger = db.query(Charger).filter(Charger.charge_point_id == payload.charge_point_id).first()
        if not charger:
            return {"status": "skipped", "reason": "charger not found"}

        mv = MeterValue(
            charger_id=charger.id,
            transaction_id=payload.transaction_id,
            timestamp=_parse_dt(payload.timestamp),
            voltage=payload.voltage,
            current=payload.current,
            power=payload.power,
            total_kwh=payload.total_kwh,
        )
        db.add(mv)

        # Keep session energy_consumed in sync
        if payload.transaction_id and payload.total_kwh is not None:
            session = db.query(ChargingSession).filter(
                ChargingSession.transaction_id == payload.transaction_id
            ).first()
            if session:
                session.energy_consumed = payload.total_kwh

        db.commit()
        return {"status": "ok"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Edge sync meter-value error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))
    finally:
        db.close()

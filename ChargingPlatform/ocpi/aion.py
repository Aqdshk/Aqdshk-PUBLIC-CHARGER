"""
OCPI 2.2.1 — AION Vendor Extension

Non-standard modules under the OCPI namespace that expose AION-specific
charger controls not covered by the OCPI 2.2.1 spec. Each endpoint wraps
the corresponding OCPP ChangeConfiguration (or ChangeAvailability) call
to the physical charger.

Firmware requirement: TK-AMC003-LCD_V2.0.04 or later.

Exposed:
    POST/GET  /ocpi/2.2.1/aion/lights       — StatusLight, LogoLight, BackgroundLight
    POST/GET  /ocpi/2.2.1/aion/display      — HomeNumber (LCD text) + BackSelection (wallpaper)
    POST/GET  /ocpi/2.2.1/aion/credentials  — UserName + UserPass (local admin console)
    POST/GET  /ocpi/2.2.1/aion/schedule     — Sch_State, Sch_Day, Sch_StartTime, Sch_StopTime
    POST/GET  /ocpi/2.2.1/aion/lock         — ChangeAvailability (Operative / Inoperative)

Each POST returns an OCPI-shaped envelope; each GET returns the current
values read via ChangeConfiguration cache or a fresh GetConfiguration.
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Charger, get_db
from ocpp_server import get_active_charge_point

from .router import _ocpi_auth, _to_ocpi_datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocpi/2.2.1/aion", tags=["OCPI 2.2.1 — AION Extension"])

BACKGROUND_PRESETS = [
    "Verdant Pulse", "Eco Wave", "Nature", "Cool Blue",
    "Sunset", "Aurora", "Meadow", "Ocean", "Neon", "Classic",
]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _envelope(data, message="Success", code=1000) -> dict:
    return {
        "status_code": code,
        "status_message": message,
        "timestamp": _to_ocpi_datetime(datetime.utcnow()),
        "data": data,
    }


def _get_charger_or_404(db: Session, charger_id: str) -> Charger:
    row = db.query(Charger).filter(Charger.charge_point_id == charger_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Charger {charger_id} not found")
    return row


def _get_cp_or_503(charger_id: str):
    """Return live OCPP ChargePoint or raise 503 if the charger's WebSocket
    is not currently connected — cannot deliver OCPP commands otherwise."""
    cp = get_active_charge_point(charger_id)
    if cp is None:
        raise HTTPException(
            status_code=503,
            detail=f"Charger {charger_id} has no active OCPP connection",
        )
    return cp


async def _change_config(charger_id: str, key: str, value: str) -> None:
    """Fire ChangeConfiguration on the live OCPP link; raise 502 on rejection."""
    cp = _get_cp_or_503(charger_id)
    resp = await cp.change_configuration(key, str(value))
    status = getattr(resp, "status", None) if resp else None
    if status != "Accepted":
        raise HTTPException(
            status_code=502,
            detail=f"Charger rejected ChangeConfiguration({key}={value}) — status: {status or 'no response'}",
        )
    logger.info(f"[aion] {charger_id} ChangeConfig {key}={value}")


async def _read_configs(charger_id: str, keys: List[str]) -> dict:
    """Fire GetConfiguration for the given keys and return a {key: value} dict.
    Missing keys are simply omitted from the result."""
    cp = _get_cp_or_503(charger_id)
    resp = await cp.get_configuration(keys)
    out: dict = {}
    if resp and hasattr(resp, "configuration_key"):
        for item in resp.configuration_key or []:
            k = item.get("key") if isinstance(item, dict) else getattr(item, "key", None)
            v = item.get("value") if isinstance(item, dict) else getattr(item, "value", None)
            if k is not None:
                out[k] = v
    return out


def _bool_to_str(v: Optional[bool]) -> Optional[str]:
    if v is None:
        return None
    return "true" if v else "false"


def _str_to_bool(v) -> Optional[bool]:
    if v is None:
        return None
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Lights — Status / Logo / Background LEDs
# ═══════════════════════════════════════════════════════════════════════════

class LightsPayload(BaseModel):
    charger_id: str = Field(..., min_length=1, max_length=64)
    status_light: Optional[bool] = None
    logo_light: Optional[bool] = None
    background_light: Optional[bool] = None


@router.post("/lights", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def set_lights(payload: LightsPayload, db: Session = Depends(get_db)):
    """Toggle the three LEDs on the AION front housing. Only fields supplied
    are updated; omit a field to leave it as-is."""
    _get_charger_or_404(db, payload.charger_id)
    applied: List[str] = []
    if payload.status_light is not None:
        await _change_config(payload.charger_id, "StatusLight", _bool_to_str(payload.status_light))
        applied.append("StatusLight")
    if payload.logo_light is not None:
        await _change_config(payload.charger_id, "LogoLight", _bool_to_str(payload.logo_light))
        applied.append("LogoLight")
    if payload.background_light is not None:
        await _change_config(payload.charger_id, "BackgroundLight", _bool_to_str(payload.background_light))
        applied.append("BackgroundLight")
    if not applied:
        raise HTTPException(status_code=400, detail="No light field supplied")
    return _envelope({
        "charger_id": payload.charger_id,
        "applied": applied,
    })


@router.get("/lights", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_lights(charger_id: str, db: Session = Depends(get_db)):
    _get_charger_or_404(db, charger_id)
    cfg = await _read_configs(charger_id, ["StatusLight", "LogoLight", "BackgroundLight"])
    return _envelope({
        "charger_id": charger_id,
        "status_light":     _str_to_bool(cfg.get("StatusLight")),
        "logo_light":       _str_to_bool(cfg.get("LogoLight")),
        "background_light": _str_to_bool(cfg.get("BackgroundLight")),
    })


# ═══════════════════════════════════════════════════════════════════════════
# 2. Display — HomeNumber (LCD text) + BackSelection (wallpaper)
# ═══════════════════════════════════════════════════════════════════════════

class DisplayPayload(BaseModel):
    charger_id: str = Field(..., min_length=1, max_length=64)
    home_number: Optional[str] = Field(default=None, max_length=24)
    background: Optional[str] = Field(default=None, max_length=32,
                                      description=f"Preset name. Known values: {', '.join(BACKGROUND_PRESETS)}")


@router.post("/display", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def set_display(payload: DisplayPayload, db: Session = Depends(get_db)):
    """Update the LCD screen text (home number) and/or background image preset."""
    _get_charger_or_404(db, payload.charger_id)
    applied: List[str] = []
    if payload.home_number is not None:
        await _change_config(payload.charger_id, "HomeNumber", payload.home_number)
        applied.append("HomeNumber")
    if payload.background is not None:
        await _change_config(payload.charger_id, "BackSelection", payload.background)
        applied.append("BackSelection")
    if not applied:
        raise HTTPException(status_code=400, detail="No display field supplied")
    return _envelope({
        "charger_id": payload.charger_id,
        "applied": applied,
    })


@router.get("/display", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_display(charger_id: str, db: Session = Depends(get_db)):
    _get_charger_or_404(db, charger_id)
    cfg = await _read_configs(charger_id, ["HomeNumber", "BackSelection"])
    return _envelope({
        "charger_id": charger_id,
        "home_number": cfg.get("HomeNumber"),
        "background":  cfg.get("BackSelection"),
    })


# ═══════════════════════════════════════════════════════════════════════════
# 3. Credentials — local admin console username / password
# ═══════════════════════════════════════════════════════════════════════════

class CredentialsPayload(BaseModel):
    charger_id: str = Field(..., min_length=1, max_length=64)
    username: Optional[str] = Field(default=None, max_length=32)
    password: Optional[str] = Field(default=None, max_length=32)


@router.post("/credentials", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def set_credentials(payload: CredentialsPayload, db: Session = Depends(get_db)):
    """Change the local admin console credentials on the AION unit. These are
    the credentials a technician uses to log in to the charger's on-device
    web UI — unrelated to the OCPI/OCPP tokens the platform uses."""
    _get_charger_or_404(db, payload.charger_id)
    applied: List[str] = []
    if payload.username is not None:
        await _change_config(payload.charger_id, "UserName", payload.username)
        applied.append("UserName")
    if payload.password is not None:
        await _change_config(payload.charger_id, "UserPass", payload.password)
        applied.append("UserPass")
    if not applied:
        raise HTTPException(status_code=400, detail="No credential field supplied")
    return _envelope({
        "charger_id": payload.charger_id,
        "applied": applied,
    })


@router.get("/credentials", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_credentials(charger_id: str, db: Session = Depends(get_db)):
    """Returns the username only. Password is never echoed back — rotate via
    POST if the password is lost."""
    _get_charger_or_404(db, charger_id)
    cfg = await _read_configs(charger_id, ["UserName"])
    return _envelope({
        "charger_id": charger_id,
        "username": cfg.get("UserName"),
    })


# ═══════════════════════════════════════════════════════════════════════════
# 4. Schedule — auto start/stop window (AION firmware ≥ V2.0.04)
# ═══════════════════════════════════════════════════════════════════════════

class SchedulePayload(BaseModel):
    charger_id: str = Field(..., min_length=1, max_length=64)
    enabled: Optional[bool] = None
    day: Optional[int] = Field(default=None, ge=0, le=6,
                               description="0=Sunday ... 6=Saturday")
    start_time: Optional[str] = Field(default=None,
                                      description="HH:MM (24-hour)",
                                      pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    stop_time: Optional[str] = Field(default=None,
                                     description="HH:MM (24-hour)",
                                     pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@router.post("/schedule", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def set_schedule(payload: SchedulePayload, db: Session = Depends(get_db)):
    """Configure the single auto start/stop window supported by AION V2.0.04.
    Send `enabled: false` to disable the schedule entirely."""
    _get_charger_or_404(db, payload.charger_id)
    applied: List[str] = []
    if payload.enabled is not None:
        await _change_config(payload.charger_id, "Sch_State", "1" if payload.enabled else "0")
        applied.append("Sch_State")
    if payload.day is not None:
        await _change_config(payload.charger_id, "Sch_Day", str(payload.day))
        applied.append("Sch_Day")
    if payload.start_time is not None:
        await _change_config(payload.charger_id, "Sch_StartTime", payload.start_time)
        applied.append("Sch_StartTime")
    if payload.stop_time is not None:
        await _change_config(payload.charger_id, "Sch_StopTime", payload.stop_time)
        applied.append("Sch_StopTime")
    if not applied:
        raise HTTPException(status_code=400, detail="No schedule field supplied")
    return _envelope({
        "charger_id": payload.charger_id,
        "applied": applied,
    })


@router.get("/schedule", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_schedule(charger_id: str, db: Session = Depends(get_db)):
    _get_charger_or_404(db, charger_id)
    cfg = await _read_configs(charger_id,
                              ["Sch_State", "Sch_Day", "Sch_StartTime", "Sch_StopTime"])
    day = cfg.get("Sch_Day")
    try:
        day = int(day) if day is not None else None
    except (TypeError, ValueError):
        pass
    return _envelope({
        "charger_id": charger_id,
        "enabled":    _str_to_bool(cfg.get("Sch_State")),
        "day":        day,
        "start_time": cfg.get("Sch_StartTime"),
        "stop_time":  cfg.get("Sch_StopTime"),
    })


# ═══════════════════════════════════════════════════════════════════════════
# 5. Lock — availability toggle via OCPP ChangeAvailability
# ═══════════════════════════════════════════════════════════════════════════

class LockPayload(BaseModel):
    charger_id: str = Field(..., min_length=1, max_length=64)
    action: str = Field(..., pattern=r"^(lock|unlock)$",
                        description="lock = Inoperative (refuse new sessions); "
                                    "unlock = Operative (normal)")
    connector_id: int = Field(default=0, ge=0, le=10,
                              description="0 = whole charger; 1..N = specific connector")


@router.post("/lock", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def set_lock(payload: LockPayload, db: Session = Depends(get_db)):
    """Lock/unlock a charger (or a specific connector) via OCPP
    ChangeAvailability. Active sessions are NOT interrupted; only new
    sessions are affected."""
    charger = _get_charger_or_404(db, payload.charger_id)
    cp = _get_cp_or_503(payload.charger_id)
    availability_type = "Inoperative" if payload.action == "lock" else "Operative"
    resp = await cp.change_availability(
        connector_id=payload.connector_id,
        type=availability_type,
    )
    status = getattr(resp, "status", None) if resp else None
    if status not in ("Accepted", "Scheduled"):
        raise HTTPException(
            status_code=502,
            detail=f"Charger rejected ChangeAvailability — status: {status or 'no response'}",
        )
    # Reflect in DB immediately so the admin dashboard is consistent
    try:
        if payload.connector_id == 0:
            charger.availability = "unavailable" if payload.action == "lock" else "available"
            db.commit()
    except Exception:
        db.rollback()
    logger.info(f"[aion] {payload.charger_id} lock action={payload.action} "
                f"connector={payload.connector_id} → {status}")
    return _envelope({
        "charger_id":   payload.charger_id,
        "connector_id": payload.connector_id,
        "action":       payload.action,
        "ocpp_status":  status,
    })


@router.get("/lock", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_lock(charger_id: str, db: Session = Depends(get_db)):
    """Read the last known availability from our records. `locked=true` means
    the charger is refusing new sessions."""
    charger = _get_charger_or_404(db, charger_id)
    availability = (charger.availability or "").lower()
    locked = availability in ("unavailable", "inoperative", "faulted")
    return _envelope({
        "charger_id":   charger_id,
        "locked":       locked,
        "availability": availability or "unknown",
    })

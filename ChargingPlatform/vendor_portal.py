"""
Vendor test portal: a login for charger manufacturers that reaches only the
charge points assigned to it.

    /vendor                      the page (templates/vendor.html)
    /api/vendor/*                what that page calls, X-Vendor-Token
    /api/admin/vendors*          accounts, managed from /admin

Every charger-facing route resolves the charge point through
`_charger_scope`, which is the one place the "is this one of yours" decision
is made. A vendor never supplies a transaction id or a database id: starts
and stops are addressed by charge point only, so there is nothing to guess
that would reach another operator's session.

The router is built by `build_router` rather than imported ready-made,
because the admin guard, the rate limiter and the start/stop handlers live in
api.py, which is also what includes this router.
"""
from __future__ import annotations

import dataclasses
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

import connectivity as conn_info
import ocpp_trace
from database import (
    Charger, ChargingSession, VendorAccount, VendorSession, get_db,
)
from ocpp_server import get_active_charge_point
from ocpp_server_v201 import OcppOperationUnsupported

logger = logging.getLogger(__name__)

SESSION_TTL_HOURS = 12
_CP_ID = re.compile(r"^[A-Za-z0-9._:-]{3,64}$")
# What a vendor may ask a charger to send. BootNotification is included on
# purpose: it is how a tester re-reads the firmware version without a reboot.
# How many charge points one account may hold once the vendor adds their own.
MAX_CHARGERS_PER_VENDOR = 5
TRIGGERABLE = (
    "BootNotification", "Heartbeat", "StatusNotification", "MeterValues",
    "FirmwareStatusNotification", "DiagnosticsStatusNotification",
)


# The rest of OCPP 1.6, beyond the commands that have their own buttons. One
# table drives both the form the page draws and what the server will accept,
# so a field cannot be offered without being validated, or the reverse.
#   field: (name, label, kind, default, choices-or-None)   kind: int | text | choice
_CONNECTOR0 = ("connector_id", "Connector (0 = whole charger)", "int", 0, None)
_CONNECTOR1 = ("connector_id", "Connector", "int", 1, None)
OPERATIONS = {
    "ChangeAvailability": {
        "about": "Take a connector out of service or put it back.",
        "fields": [_CONNECTOR0, ("type", "Availability", "choice", "Inoperative", ["Inoperative", "Operative"])],
        "ok": ("Accepted", "Scheduled"),
    },
    "ClearCache": {"about": "Clear the charger's authorization cache.", "fields": []},
    "GetLocalListVersion": {"about": "Read the version of the local authorization list.", "fields": []},
    "SendLocalList": {
        "about": "Replace or update the local authorization list. Each tag is sent as Accepted.",
        "fields": [
            ("list_version", "List version", "int", 1, None),
            ("update_type", "Update type", "choice", "Full", ["Full", "Differential"]),
            ("id_tags", "ID tags, comma separated", "text", "", None),
        ],
    },
    "ReserveNow": {
        "about": "Reserve a connector for an ID tag.",
        "fields": [
            _CONNECTOR1,
            ("id_tag", "ID tag", "text", "TESTTAG01", None),
            ("reservation_id", "Reservation ID", "int", 1, None),
            ("minutes", "Valid for (minutes)", "int", 15, None),
        ],
    },
    "CancelReservation": {
        "about": "Cancel a reservation by its ID.",
        "fields": [("reservation_id", "Reservation ID", "int", 1, None)],
    },
    "SetChargingProfile": {
        "about": "Limit charging with a simple TxDefaultProfile: one period, starting now.",
        "fields": [
            _CONNECTOR1,
            ("limit", "Limit", "int", 16, None),
            ("unit", "Unit", "choice", "A", ["A", "W"]),
            ("profile_id", "Profile ID", "int", 1, None),
            ("stack_level", "Stack level", "int", 0, None),
        ],
    },
    "ClearChargingProfile": {
        "about": "Remove charging profiles. Leave the profile ID at 0 to clear all of them.",
        "fields": [("profile_id", "Profile ID (0 = all)", "int", 0, None)],
        "ok": ("Accepted", "Unknown"),
    },
    "GetCompositeSchedule": {
        "about": "Ask what limit the charger will actually apply.",
        "fields": [
            _CONNECTOR1,
            ("duration", "Duration (seconds)", "int", 3600, None),
            ("unit", "Unit", "choice", "A", ["A", "W"]),
        ],
    },
    "GetDiagnostics": {
        "about": "Ask the charger to upload its diagnostics file to an address it can reach.",
        "fields": [("location", "Upload address (ftp:// or http://)", "text", "", None)],
    },
    "DataTransfer": {
        "about": "Send a vendor-specific message.",
        "fields": [
            ("vendor_id", "Vendor ID", "text", "", None),
            ("message_id", "Message ID", "text", "", None),
            ("data", "Data", "text", "", None),
        ],
    },
}


def _operations_public() -> list:
    return [
        {
            "name": name, "about": spec["about"],
            "fields": [
                {"name": f[0], "label": f[1], "kind": f[2], "default": f[3], "choices": f[4]}
                for f in spec["fields"]
            ],
        }
        for name, spec in OPERATIONS.items()
    ]


def _clean_params(operation: str, raw: dict) -> dict:
    """Coerce a submitted form to the table's types; anything not in the
    table is dropped, so only declared fields ever reach a charger."""
    out = {}
    for name, label, kind, default, choices in OPERATIONS[operation]["fields"]:
        value = (raw or {}).get(name, default)
        if kind == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{label}: enter a whole number") from None
            if not 0 <= value <= 1_000_000:
                raise HTTPException(status_code=400, detail=f"{label}: out of range")
        elif kind == "choice":
            if value not in choices:
                raise HTTPException(status_code=400, detail=f"{label}: choose one of {', '.join(choices)}")
        else:
            value = str(value or "").strip()
            if len(value) > 1000:
                raise HTTPException(status_code=400, detail=f"{label}: too long")
        out[name] = value
    return out


async def _run_operation(cp: Any, operation: str, p: dict) -> Any:
    if operation == "ChangeAvailability":
        return await cp.change_availability(p["connector_id"], p["type"])
    if operation == "ClearCache":
        return await cp.clear_cache()
    if operation == "GetLocalListVersion":
        return await cp.get_local_list_version()
    if operation == "SendLocalList":
        tags = [t.strip() for t in p["id_tags"].split(",") if t.strip()]
        if any(len(t) > 20 for t in tags):
            raise HTTPException(status_code=400, detail="An ID tag is at most 20 characters")
        return await cp.send_local_list(
            list_version=p["list_version"], update_type=p["update_type"],
            local_authorization_list=[{"id_tag": t, "id_tag_info": {"status": "Accepted"}} for t in tags],
        )
    if operation == "ReserveNow":
        if not p["id_tag"] or len(p["id_tag"]) > 20:
            raise HTTPException(status_code=400, detail="ID tag: 1 to 20 characters")
        expiry = datetime.now(timezone.utc) + timedelta(minutes=max(1, min(p["minutes"], 1440)))
        return await cp.reserve_now(
            connector_id=p["connector_id"], expiry_date=expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
            id_tag=p["id_tag"], reservation_id=p["reservation_id"],
        )
    if operation == "CancelReservation":
        return await cp.cancel_reservation(p["reservation_id"])
    if operation == "SetChargingProfile":
        return await cp.set_charging_profile(p["connector_id"], {
            "charging_profile_id": p["profile_id"],
            "stack_level": p["stack_level"],
            "charging_profile_purpose": "TxDefaultProfile",
            "charging_profile_kind": "Absolute",
            "charging_schedule": {
                "charging_rate_unit": p["unit"],
                "start_schedule": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "charging_schedule_period": [{"start_period": 0, "limit": p["limit"]}],
            },
        })
    if operation == "ClearChargingProfile":
        return await cp.clear_charging_profile(id=p["profile_id"] or None)
    if operation == "GetCompositeSchedule":
        return await cp.get_composite_schedule(
            connector_id=p["connector_id"], duration=p["duration"], charging_rate_unit=p["unit"],
        )
    if operation == "GetDiagnostics":
        if not re.match(r"^(https?|ftps?)://[^\s]+$", p["location"], re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Upload address must be an http, https or ftp URL")
        return await cp.get_diagnostics(location=p["location"])
    if operation == "DataTransfer":
        if not p["vendor_id"]:
            raise HTTPException(status_code=400, detail="Vendor ID is required")
        return await cp.data_transfer(p["vendor_id"], p["message_id"] or None, p["data"] or None)
    raise HTTPException(status_code=400, detail="Unknown operation")


def _response_fields(resp: Any) -> dict:
    """A charger's answer as plain data, whatever shape the library gave it."""
    if resp is None:
        return {}
    try:
        if dataclasses.is_dataclass(resp) and not isinstance(resp, type):
            data = dataclasses.asdict(resp)
        else:
            data = dict(vars(resp))
    except TypeError:
        return {"value": str(resp)}
    return {k: v for k, v in data.items() if v is not None and not k.startswith("_")}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None


def _iso_myt(dt: Optional[datetime]) -> Optional[str]:
    """Session clocks are naive Malaysia wall time; say so on the way out."""
    return dt.replace(tzinfo=timezone(timedelta(hours=8))).isoformat() if dt else None


def _clean_ids(raw: Any) -> List[str]:
    """Normalise a list or comma/space separated string of charge point ids."""
    parts = raw if isinstance(raw, (list, tuple)) else re.split(r"[,\s]+", str(raw or ""))
    out: List[str] = []
    for p in parts:
        p = str(p).strip()
        if not p:
            continue
        if not _CP_ID.match(p):
            raise HTTPException(status_code=400, detail=f"Invalid charge point id: {p}")
        if p not in out:
            out.append(p)
    return out


# ── Request bodies ───────────────────────────────────────────────────────────

class VendorLogin(BaseModel):
    email: str
    password: str


class VendorIn(BaseModel):
    company: str = Field(..., min_length=1, max_length=120)
    email: str
    contact_name: Optional[str] = Field(None, max_length=120)
    charge_point_ids: Any = ""
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=255)


class VendorPatch(BaseModel):
    company: Optional[str] = Field(None, min_length=1, max_length=120)
    contact_name: Optional[str] = Field(None, max_length=120)
    charge_point_ids: Optional[Any] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    clear_expiry: bool = False
    notes: Optional[str] = Field(None, max_length=255)
    reset_password: bool = False


class ClaimIn(BaseModel):
    charge_point_id: str = Field(..., min_length=3, max_length=64)


class OperationIn(BaseModel):
    operation: str
    params: dict = Field(default_factory=dict)


class StartIn(BaseModel):
    connector_id: int = Field(1, ge=1, le=16)


class ResetIn(BaseModel):
    type: str = Field("Soft", pattern="^(Soft|Hard)$")


class TriggerIn(BaseModel):
    requested_message: str
    connector_id: Optional[int] = Field(None, ge=0, le=16)


class ConfigGetIn(BaseModel):
    keys: Optional[List[str]] = None


class ConfigSetIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=50)
    value: str = Field(..., max_length=500)


class UnlockIn(BaseModel):
    connector_id: int = Field(1, ge=1, le=16)


class FirmwareIn(BaseModel):
    location: str = Field(..., min_length=8, max_length=512)
    retries: Optional[int] = Field(None, ge=0, le=10)
    retry_interval: Optional[int] = Field(None, ge=0, le=3600)


# ── Serialisers ──────────────────────────────────────────────────────────────

def _vendor_public(v: VendorAccount) -> dict:
    return {
        "id": v.id,
        "company": v.company,
        "contact_name": v.contact_name,
        "email": v.email,
        "charge_point_ids": v.charger_ids(),
        "is_active": bool(v.is_active),
        "expires_at": _iso_utc(v.expires_at),
        "expired": bool(v.expires_at and v.expires_at <= _utcnow()),
        "notes": v.notes,
        "created_at": _iso_utc(v.created_at),
        "last_login": _iso_utc(v.last_login),
    }


def _charger_view(db: Session, cp_id: str, offline_after_minutes: int) -> dict:
    """What a vendor sees of one of their chargers, registered or not."""
    charger = db.query(Charger).filter(Charger.charge_point_id == cp_id).first()
    connected = get_active_charge_point(cp_id) is not None
    view: dict = {
        "charge_point_id": cp_id,
        "registered": charger is not None,
        "connected": connected,
    }
    if charger is None:
        return view

    heartbeat_fresh = bool(
        charger.last_heartbeat
        and (_utcnow() - charger.last_heartbeat).total_seconds() < offline_after_minutes * 60
    )
    active = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.charger_id == charger.id,
            ChargingSession.status.in_(["active", "pending", "stopping"]),
            # A session the charger has already closed is over, whatever its
            # status says: a stop acknowledged after StopTransaction arrived
            # can leave "stopping" behind.
            ChargingSession.stop_time.is_(None),
        )
        # A real transaction before a placeholder: a start that is still being
        # set up carries a negative id until the charger's StartTransaction.
        .order_by(desc(ChargingSession.transaction_id > 0), desc(ChargingSession.id))
        .first()
    )
    view.update({
        "online": connected or heartbeat_fresh,
        "vendor": charger.vendor,
        "model": charger.model,
        "firmware_version": charger.firmware_version,
        "ocpp_version": charger.ocpp_version,
        "availability": charger.availability,
        "connector_status": charger.connector_status,
        "number_of_connectors": charger.number_of_connectors or 1,
        "last_heartbeat": _iso_utc(charger.last_heartbeat),
        "tariff_per_kwh": float(charger.tariff_per_kwh or 0),
        "connectivity": conn_info.classify(charger)["label"],
        "remote_ip": charger.last_remote_ip,
        "active_session": _session_view(active, charger) if active else None,
    })
    return view


def _session_view(s: ChargingSession, charger: Charger) -> dict:
    energy = float(s.energy_consumed or 0)
    if s.meter_start is not None and s.meter_stop is not None and s.meter_stop >= s.meter_start:
        energy = max(energy, (s.meter_stop - s.meter_start) / 1000.0)
    tariff = float(charger.tariff_per_kwh or 0)
    return {
        # Negative ids are the platform's own placeholder for a start the
        # charger has not confirmed yet; they mean nothing to a vendor.
        "transaction_id": s.transaction_id if (s.transaction_id or 0) > 0 else None,
        "connector_id": s.connector_id,
        "status": s.status,
        "start_time": _iso_myt(s.start_time),
        "stop_time": _iso_myt(s.stop_time),
        "meter_start_wh": s.meter_start,
        "meter_stop_wh": s.meter_stop,
        "energy_kwh": round(energy, 3),
        "stop_reason": s.stop_reason,
        "tariff_per_kwh": tariff,
        "amount_rm": round(energy * tariff, 2),
    }


def _reply(resp: Any, ok: tuple = ("Accepted",)) -> dict:
    """Turn a charger's answer to a command into something the page can show."""
    if resp is None:
        return {"success": False, "message": "No response from the charger."}
    status = getattr(resp, "status", None)
    if status is None:
        return {"success": True, "message": "Charger acknowledged."}
    return {"success": status in ok, "message": f"Charger answered {status}.", "status": status}


# ── Router ───────────────────────────────────────────────────────────────────

def build_router(
    *,
    require_admin: Callable,
    enforce_rate_limit: Callable,
    start_charging: Callable,
    stop_charging: Callable,
    start_request_model: Any,
    stop_request_model: Any,
    offline_after_minutes: int = 5,
) -> APIRouter:
    router = APIRouter(tags=["Vendor Test Portal"])

    # ── Vendor auth ──

    def current_vendor(request: Request, db: Session = Depends(get_db)) -> VendorAccount:
        token = (request.headers.get("X-Vendor-Token") or "").strip()
        if not token:
            raise HTTPException(status_code=401, detail="Vendor sign-in required")
        row = (
            db.query(VendorSession)
            .filter(VendorSession.token == token, VendorSession.expires_at > _utcnow())
            .first()
        )
        vendor = db.query(VendorAccount).filter(VendorAccount.id == row.vendor_id).first() if row else None
        # Checked on every request, not only at login, so switching an account
        # off or letting it expire ends access at once.
        if vendor is None or not vendor.is_usable():
            raise HTTPException(status_code=401, detail="Vendor sign-in required")
        return vendor

    def _charger_scope(cp_id: str, vendor: VendorAccount) -> str:
        """The only gate between a vendor and a charge point. 404, not 403, so
        the answer for "not yours" and "does not exist" is the same."""
        if cp_id not in vendor.charger_ids():
            raise HTTPException(status_code=404, detail="Charger not found")
        return cp_id

    def _live(cp_id: str):
        cp = get_active_charge_point(cp_id)
        if cp is None:
            raise HTTPException(status_code=409, detail="The charger is not connected right now.")
        return cp

    @router.post("/api/vendor/login")
    async def vendor_login(body: VendorLogin, request: Request, db: Session = Depends(get_db)):
        enforce_rate_limit(request, "vendor-login", max_requests=10, window_seconds=300)
        email = (body.email or "").strip().lower()
        vendor = db.query(VendorAccount).filter(VendorAccount.email == email).first()
        # One message for every failure: unknown email, wrong password,
        # disabled and expired are indistinguishable from outside.
        if vendor is None or not vendor.check_password(body.password) or not vendor.is_usable():
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = secrets.token_urlsafe(48)
        now = _utcnow()
        db.query(VendorSession).filter(VendorSession.expires_at <= now).delete(synchronize_session=False)
        db.add(VendorSession(
            vendor_id=vendor.id, token=token, expires_at=now + timedelta(hours=SESSION_TTL_HOURS),
        ))
        vendor.last_login = now
        db.commit()
        logger.warning("AUDIT vendor login vendor=%s (%s)", vendor.id, vendor.company)
        return {"token": token, "vendor": _vendor_public(vendor)}

    @router.post("/api/vendor/logout")
    async def vendor_logout(request: Request, db: Session = Depends(get_db)):
        token = (request.headers.get("X-Vendor-Token") or "").strip()
        if token:
            db.query(VendorSession).filter(VendorSession.token == token).delete(synchronize_session=False)
            db.commit()
        return {"success": True}

    # ── Vendor reads ──

    @router.get("/api/vendor/overview")
    async def vendor_overview(
        request: Request,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        host = request.headers.get("x-forwarded-host") or request.url.hostname or ""
        return {
            "vendor": _vendor_public(vendor),
            "connection": {
                "ws_url": f"ws://{host}:9000/{{charge_point_id}}",
                "wss_url": f"wss://{host}/ocpp/{{charge_point_id}}",
                "subprotocols": ["ocpp1.6", "ocpp2.0.1"],
                "firmware_download_base": f"http://{host}/static/firmware/",
            },
            "triggerable": list(TRIGGERABLE),
            "max_chargers": MAX_CHARGERS_PER_VENDOR,
            "operations": _operations_public(),
            "chargers": [_charger_view(db, c, offline_after_minutes) for c in vendor.charger_ids()],
        }

    @router.get("/api/vendor/chargers/{cp_id}/live")
    async def vendor_live(
        cp_id: str, after_id: int = 0, limit: int = 200,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        """State and new frames in one call, so the page polls once."""
        _charger_scope(cp_id, vendor)
        return {
            "charger": _charger_view(db, cp_id, offline_after_minutes),
            "messages": ocpp_trace.read(db, cp_id, after_id=after_id, limit=limit),
        }

    @router.get("/api/vendor/chargers/{cp_id}/checklist")
    async def vendor_checklist(
        cp_id: str, since_id: int = 0,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        _charger_scope(cp_id, vendor)
        return ocpp_trace.checklist(db, cp_id, since_id=max(0, since_id))

    @router.get("/api/vendor/chargers/{cp_id}/sessions")
    async def vendor_sessions(
        cp_id: str,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        _charger_scope(cp_id, vendor)
        charger = db.query(Charger).filter(Charger.charge_point_id == cp_id).first()
        if charger is None:
            return {"sessions": []}
        rows = (
            db.query(ChargingSession)
            .filter(ChargingSession.charger_id == charger.id)
            .order_by(desc(ChargingSession.id))
            .limit(20)
            .all()
        )
        return {"sessions": [_session_view(s, charger) for s in rows]}

    # ── Vendor: choosing their own charge point ids ──

    def _taken(db: Session, cp_id: str, vendor: VendorAccount) -> bool:
        """Whether an id already belongs to someone: a charger the platform
        knows, or another vendor's list. Compared without regard to case, so
        "dc3001" cannot be used to sit beside "DC3001"."""
        wanted = cp_id.lower()
        if db.query(Charger.id).filter(func.lower(Charger.charge_point_id) == wanted).first():
            return True
        for other in db.query(VendorAccount).filter(VendorAccount.id != vendor.id).all():
            if wanted in (c.lower() for c in other.charger_ids()):
                return True
        return False

    @router.post("/api/vendor/chargers", status_code=201)
    async def vendor_add_charger(
        body: ClaimIn, request: Request,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        """
        A vendor names the charge point id they will put on their charger.

        Only an id nobody has: this is the one route where a vendor widens
        their own reach, so an id that is already a charger on the platform is
        refused, or typing "DC3001" would hand over a live public charger. The
        refusal is worded the same whoever holds the id.
        """
        enforce_rate_limit(request, "vendor-claim", max_requests=20, window_seconds=300)
        cp_id = body.charge_point_id.strip()
        if not _CP_ID.match(cp_id):
            raise HTTPException(
                status_code=400,
                detail="Use 3 to 64 letters, digits, dots, underscores, colons or hyphens, with no spaces.",
            )
        mine = vendor.charger_ids()
        if cp_id.lower() in (c.lower() for c in mine):
            return {"charge_point_ids": mine}
        if len(mine) >= MAX_CHARGERS_PER_VENDOR:
            raise HTTPException(
                status_code=409,
                detail=f"This account can hold {MAX_CHARGERS_PER_VENDOR} charge points. Remove one first, or ask PlagSini.",
            )
        if _taken(db, cp_id, vendor):
            raise HTTPException(status_code=409, detail="That ID is not available. Please choose another.")
        vendor.charge_point_ids = ",".join(mine + [cp_id])
        db.commit()
        ocpp_trace.invalidate()
        logger.warning("AUDIT vendor=%s added charge point %s", vendor.id, cp_id)
        return {"charge_point_ids": vendor.charger_ids()}

    @router.delete("/api/vendor/chargers/{cp_id}")
    async def vendor_remove_charger(
        cp_id: str,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        """Take back an id that was never used, e.g. a typo. Once the charger
        has connected it is a real charger with history, and letting go of it
        could not be undone from here, so that is left to an administrator."""
        _charger_scope(cp_id, vendor)
        if db.query(Charger.id).filter(Charger.charge_point_id == cp_id).first():
            raise HTTPException(
                status_code=409,
                detail="This charger has already connected. Ask PlagSini to remove it.",
            )
        vendor.charge_point_ids = ",".join(c for c in vendor.charger_ids() if c != cp_id)
        db.commit()
        ocpp_trace.invalidate()
        logger.warning("AUDIT vendor=%s removed charge point %s", vendor.id, cp_id)
        return {"charge_point_ids": vendor.charger_ids()}

    # ── Vendor commands ──

    @router.post("/api/vendor/chargers/{cp_id}/start")
    async def vendor_start(
        cp_id: str, body: StartIn,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        _charger_scope(cp_id, vendor)
        logger.warning("AUDIT vendor=%s start %s connector=%s", vendor.id, cp_id, body.connector_id)
        # The tag the dashboard's own manual start uses: chargers that check
        # with us before starting (Authorize) already accept it, and it bills
        # nobody's wallet.
        result = await start_charging(
            start_request_model(charger_id=cp_id, connector_id=body.connector_id, id_tag="DASHBOARD_USER"),
            db, {"mode": "vendor", "vendor_id": vendor.id},
        )
        return {"success": result.success, "message": result.message, "transaction_id": result.transaction_id}

    @router.post("/api/vendor/chargers/{cp_id}/stop")
    async def vendor_stop(
        cp_id: str,
        vendor: VendorAccount = Depends(current_vendor), db: Session = Depends(get_db),
    ):
        _charger_scope(cp_id, vendor)
        logger.warning("AUDIT vendor=%s stop %s", vendor.id, cp_id)
        # Addressed by charger only: transaction_id 0 makes the handler find
        # whatever is running on this charge point, never one named by the caller.
        result = await stop_charging(
            stop_request_model(transaction_id=0, charger_id=cp_id),
            db, {"mode": "vendor", "vendor_id": vendor.id},
        )
        return {"success": result.success, "message": result.message, "transaction_id": result.transaction_id}

    async def _command(vendor: VendorAccount, cp_id: str, name: str, send: Callable, ok: tuple = ("Accepted",)):
        _charger_scope(cp_id, vendor)
        cp = _live(cp_id)
        logger.warning("AUDIT vendor=%s %s %s", vendor.id, name, cp_id)
        try:
            return _reply(await send(cp), ok)
        except OcppOperationUnsupported as e:
            return {"success": False, "message": str(e) or f"{name} is not available on OCPP 2.0.1."}

    @router.post("/api/vendor/chargers/{cp_id}/reset")
    async def vendor_reset(cp_id: str, body: ResetIn, vendor: VendorAccount = Depends(current_vendor)):
        return await _command(vendor, cp_id, "Reset", lambda cp: cp.reset(body.type))

    @router.post("/api/vendor/chargers/{cp_id}/trigger")
    async def vendor_trigger(cp_id: str, body: TriggerIn, vendor: VendorAccount = Depends(current_vendor)):
        if body.requested_message not in TRIGGERABLE:
            raise HTTPException(status_code=400, detail="That message cannot be triggered")
        return await _command(
            vendor, cp_id, "TriggerMessage",
            lambda cp: cp.trigger_message(
                requested_message=body.requested_message, connector_id=body.connector_id,
            ),
            ok=("Accepted", "NotImplemented"),
        )

    @router.post("/api/vendor/chargers/{cp_id}/unlock")
    async def vendor_unlock(cp_id: str, body: UnlockIn, vendor: VendorAccount = Depends(current_vendor)):
        return await _command(
            vendor, cp_id, "UnlockConnector",
            lambda cp: cp.unlock_connector(body.connector_id), ok=("Unlocked",),
        )

    @router.post("/api/vendor/chargers/{cp_id}/configuration/get")
    async def vendor_get_configuration(
        cp_id: str, body: ConfigGetIn, vendor: VendorAccount = Depends(current_vendor),
    ):
        _charger_scope(cp_id, vendor)
        cp = _live(cp_id)
        logger.warning("AUDIT vendor=%s GetConfiguration %s", vendor.id, cp_id)
        keys = [k.strip() for k in (body.keys or []) if k and k.strip()] or None
        resp = await cp.get_configuration(keys)
        if resp is None:
            return {"success": False, "message": "No response from the charger."}
        return {
            "success": True,
            "message": "Configuration received.",
            "configuration": list(getattr(resp, "configuration_key", None) or []),
            "unknown": list(getattr(resp, "unknown_key", None) or []),
        }

    @router.post("/api/vendor/chargers/{cp_id}/configuration/set")
    async def vendor_set_configuration(
        cp_id: str, body: ConfigSetIn, vendor: VendorAccount = Depends(current_vendor),
    ):
        return await _command(
            vendor, cp_id, f"ChangeConfiguration {body.key}",
            lambda cp: cp.change_configuration(body.key, body.value),
            ok=("Accepted", "RebootRequired"),
        )

    @router.post("/api/vendor/chargers/{cp_id}/firmware")
    async def vendor_update_firmware(
        cp_id: str, body: FirmwareIn, vendor: VendorAccount = Depends(current_vendor),
    ):
        location = body.location.strip()
        if not re.match(r"^(https?|ftps?)://[^\s]+$", location, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Location must be an http, https or ftp URL")
        # "Now", in the form every 1.6 firmware we have met parses.
        retrieve = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return await _command(
            vendor, cp_id, f"UpdateFirmware {location}",
            lambda cp: cp.update_firmware(
                location=location, retrieve_date=retrieve,
                retries=body.retries, retry_interval=body.retry_interval,
            ),
        )

    @router.post("/api/vendor/chargers/{cp_id}/operation")
    async def vendor_operation(
        cp_id: str, body: OperationIn, vendor: VendorAccount = Depends(current_vendor),
    ):
        """Any other OCPP 1.6 operation, from the OPERATIONS table."""
        _charger_scope(cp_id, vendor)
        spec = OPERATIONS.get(body.operation)
        if spec is None:
            raise HTTPException(status_code=400, detail="Unknown operation")
        params = _clean_params(body.operation, body.params)
        cp = _live(cp_id)
        logger.warning("AUDIT vendor=%s %s %s %s", vendor.id, body.operation, cp_id, params)
        try:
            resp = await _run_operation(cp, body.operation, params)
        except OcppOperationUnsupported as e:
            return {"success": False, "message": str(e) or f"{body.operation} is not available on OCPP 2.0.1."}
        out = _reply(resp, spec.get("ok", ("Accepted",)))
        out["response"] = _response_fields(resp)
        return out

    # ── Admin: accounts ──

    @router.get("/api/admin/vendors")
    async def admin_list_vendors(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
        rows = db.query(VendorAccount).order_by(VendorAccount.id.desc()).all()
        return {"vendors": [_vendor_public(v) for v in rows]}

    @router.post("/api/admin/vendors", status_code=201)
    async def admin_create_vendor(body: VendorIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
        email = (body.email or "").strip().lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise HTTPException(status_code=400, detail="Invalid email address")
        if db.query(VendorAccount).filter(VendorAccount.email == email).first():
            raise HTTPException(status_code=409, detail="A vendor account with that email already exists")
        password = body.password or secrets.token_urlsafe(12)
        vendor = VendorAccount(
            company=body.company.strip(),
            contact_name=(body.contact_name or "").strip() or None,
            email=email,
            charge_point_ids=",".join(_clean_ids(body.charge_point_ids)),
            expires_at=_naive_utc(body.expires_at),
            notes=(body.notes or "").strip() or None,
        )
        vendor.set_password(password)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        ocpp_trace.invalidate()
        out = _vendor_public(vendor)
        # Shown once. Only the hash is stored, so it cannot be read back later.
        out["password"] = password
        return out

    @router.patch("/api/admin/vendors/{vendor_id}")
    async def admin_update_vendor(
        vendor_id: int, body: VendorPatch,
        db: Session = Depends(get_db), _: dict = Depends(require_admin),
    ):
        vendor = db.query(VendorAccount).filter(VendorAccount.id == vendor_id).first()
        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor account not found")
        if body.company is not None:
            vendor.company = body.company.strip()
        if body.contact_name is not None:
            vendor.contact_name = body.contact_name.strip() or None
        if body.charge_point_ids is not None:
            vendor.charge_point_ids = ",".join(_clean_ids(body.charge_point_ids))
        if body.notes is not None:
            vendor.notes = body.notes.strip() or None
        if body.clear_expiry:
            vendor.expires_at = None
        elif body.expires_at is not None:
            vendor.expires_at = _naive_utc(body.expires_at)
        if body.is_active is not None:
            vendor.is_active = body.is_active
        new_password = None
        if body.reset_password:
            new_password = secrets.token_urlsafe(12)
            vendor.set_password(new_password)
        # A disabled account or a new password should not leave an old browser
        # tab signed in.
        if new_password or body.is_active is False:
            db.query(VendorSession).filter(VendorSession.vendor_id == vendor.id).delete(synchronize_session=False)
        db.commit()
        db.refresh(vendor)
        ocpp_trace.invalidate()
        out = _vendor_public(vendor)
        if new_password:
            out["password"] = new_password
        return out

    @router.delete("/api/admin/vendors/{vendor_id}")
    async def admin_delete_vendor(vendor_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
        vendor = db.query(VendorAccount).filter(VendorAccount.id == vendor_id).first()
        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor account not found")
        # Explicit, because SQLite does not enforce the cascade.
        db.query(VendorSession).filter(VendorSession.vendor_id == vendor.id).delete(synchronize_session=False)
        db.delete(vendor)
        db.commit()
        ocpp_trace.invalidate()
        return {"success": True}

    return router


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

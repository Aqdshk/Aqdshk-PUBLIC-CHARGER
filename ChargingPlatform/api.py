"""
PlagSini EV — Charging Platform REST API

Main FastAPI application. Handles:
  - Dashboard routes (/, /chargers, /sessions, etc.)
  - OCPP operations (RemoteStart, UpdateFirmware, etc.)
  - User auth, wallet, charging, rewards
  - Admin & staff endpoints
  - Payment gateway callbacks
  - OCPI integration (via router)
"""
import asyncio
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.orm import Session

from database import (
    CATEGORY_DEPARTMENT_MAP, DEPARTMENTS, STAFF_ROLES, TICKET_SLA_HOURS,
    AuditLog,
    Charger, ChargerReview, ChargerBooking, ChargingSchedule, ChargingSession, Fault, MaintenanceRecord, MeterValue,
    OTPVerification, PaymentGatewayConfig, PaymentTransaction,
    Pricing, StaffSession, SupportStaff, SupportTicket, TicketMessage,
    User, Vehicle, Wallet, WalletTransaction,
    SessionLocal, get_db, init_db,
)
from email_service import generate_otp, send_otp_email, send_ticket_confirmation, send_ticket_update, send_ticket_reminder, send_charging_receipt
from ocpp_server import get_active_charge_point, active_charge_points, firmware_events
from payment_gateway import (
    get_gateway,
    generate_transaction_ref,
    GATEWAY_REGISTRY,
    is_callback_already_processed,
)
from security import (
    create_tokens,
    verify_access_token,
    verify_refresh_token,
    get_current_user,
    get_current_user_optional,
    require_admin,
    verify_resource_owner,
    validate_topup_amount,
    validate_topup_daily_limit,
    get_wallet_with_lock,
    audit_log,
    get_client_ip,
    create_access_token,
)

logger = logging.getLogger(__name__)


def _utcnow():
    """Timezone-safe replacement for deprecated _utcnow()"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Charger metadata helpers ─────────────────────────────────────────────────

def _parse_power_from_model(model: Optional[str]) -> Optional[float]:
    """Extract kW rating from model name, e.g. '30kW' → 30.0, '7.4kw' → 7.4."""
    if not model:
        return None
    match = re.search(r'(\d+\.?\d*)\s*kw', model, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _infer_connector_type(max_power_kw: Optional[float]) -> Optional[str]:
    """Infer connector type from power rating. >22kW = DC CCS2, else AC Type 2."""
    if max_power_kw is None:
        return None
    return "CCS2" if max_power_kw > 22 else "Type 2"


def _effective_charger_specs(
    max_power_kw: Optional[float],
    connector_type: Optional[str],
    model: Optional[str],
) -> tuple[Optional[float], Optional[str]]:
    """Return (max_power_kw, connector_type) filling blanks from model name heuristics."""
    power = max_power_kw
    if power is None:
        power = _parse_power_from_model(model)
    ctype = connector_type
    if ctype is None:
        ctype = _infer_connector_type(power)
    return power, ctype


# Base path for templates/static — use __file__ so paths work regardless of CWD
_BASE_DIR = Path(__file__).resolve().parent

# ─── App & Configuration ──────────────────────────────────────────────────
app = FastAPI(title="Charging Platform Management System")

# Charger status: consider offline if no heartbeat within this many minutes
OFFLINE_THRESHOLD_MINUTES = int(os.getenv("OFFLINE_THRESHOLD_MINUTES", "5"))
# Pending sessions: include in "active" list if started within this many minutes
PENDING_SESSION_WINDOW_MINUTES = int(os.getenv("PENDING_SESSION_WINDOW_MINUTES", "10"))

# Malaysia time for OCPP-derived naive datetimes (charger sends +08, DB stores naive wall time)
MYT = timezone(timedelta(hours=8))
UTC = timezone.utc


def _iso_myt_naive_local(v: Optional[datetime]) -> Optional[str]:
    """Serialize naive datetimes as Malaysia wall time (sessions, meter samples from OCPP)."""
    if v is None:
        return None
    if v.tzinfo is None:
        return v.replace(tzinfo=MYT).isoformat()
    return v.astimezone(MYT).isoformat()


def _iso_utc_naive_to_myt(v: Optional[datetime]) -> Optional[str]:
    """Serialize naive datetimes stored from _utcnow() as UTC, then show as MYT."""
    if v is None:
        return None
    if v.tzinfo is None:
        return v.replace(tzinfo=UTC).astimezone(MYT).isoformat()
    return v.astimezone(MYT).isoformat()


def _want_online_only_list(online_only_param: Optional[str]) -> bool:
    """
    True when the client asks for a short list (metering/sessions/ops dropdowns).
    Uses string parsing so proxies/CDNs cannot break bool coercion (?online_only=true).
    """
    if online_only_param is None:
        return False
    s = str(online_only_param).strip().lower()
    return s in ("1", "true", "yes", "on")

# ─── Rate Limiting (in-memory; single-instance only) ────────────────────────
_RATE_LIMIT_BUCKETS: Dict[str, List[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_LAST_CLEANUP: float = 0.0
_RATE_LIMIT_CLEANUP_INTERVAL = 300  # sweep stale keys every 5 minutes


def _rate_limit_cleanup() -> None:
    """Remove expired entries from _RATE_LIMIT_BUCKETS to prevent unbounded growth."""
    global _RATE_LIMIT_LAST_CLEANUP
    now = time.time()
    if now - _RATE_LIMIT_LAST_CLEANUP < _RATE_LIMIT_CLEANUP_INTERVAL:
        return
    cutoff = now - 3600  # remove buckets with no requests in the last hour
    with _RATE_LIMIT_LOCK:
        stale = [k for k, v in _RATE_LIMIT_BUCKETS.items() if not v or max(v) < cutoff]
        for k in stale:
            del _RATE_LIMIT_BUCKETS[k]
        _RATE_LIMIT_LAST_CLEANUP = now
        if stale:
            logger.debug(f"Rate-limit cleanup: removed {len(stale)} stale buckets")


def _require_callback_secret(request: Request, gateway_name: str) -> None:
    """
    Enforce shared-secret protection for payment callbacks.
    Reject callbacks unless PAYMENT_CALLBACK_SECRET is configured and matches.
    """
    expected_secret = os.getenv("PAYMENT_CALLBACK_SECRET", "").strip()
    if not expected_secret:
        raise HTTPException(
            status_code=503,
            detail="Payment callback secret is not configured on the server",
        )

    provided_secret = request.headers.get("X-Callback-Secret", "").strip()
    if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
        logger.warning("Rejected callback for gateway '%s': invalid callback secret", gateway_name)
        raise HTTPException(status_code=401, detail="Invalid callback secret")


def _gateway_env_prefix(gateway_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", (gateway_name or "").strip().lower()).strip("_")
    return f"PAYMENT_{(normalized or 'UNKNOWN').upper()}"


def _gateway_env_name(gateway_name: str, field: str) -> str:
    return f"{_gateway_env_prefix(gateway_name)}_{field}"


def _allow_legacy_db_gateway_secrets() -> bool:
    """If True, fall back to DB-stored api_key/api_secret when env vars are empty."""
    return os.getenv("ALLOW_DB_GATEWAY_SECRETS", "0").strip().lower() in ("1", "true", "yes")


def _resolve_gateway_runtime_config(gw: PaymentGatewayConfig) -> Dict[str, Any]:
    """
    Build runtime gateway config with env-first credentials.
    By default, DB-stored secrets are ignored for security.
    """
    gateway_name = (gw.gateway_name or "").strip().lower()
    api_key_env = _gateway_env_name(gateway_name, "API_KEY")
    api_secret_env = _gateway_env_name(gateway_name, "API_SECRET")

    api_key = os.getenv(api_key_env, "").strip()
    api_secret = os.getenv(api_secret_env, "").strip()

    if _allow_legacy_db_gateway_secrets():
        if not api_key:
            api_key = (gw.api_key or "").strip()
        if not api_secret:
            api_secret = (gw.api_secret or "").strip()

    return {
        "gateway_name": gw.gateway_name,
        "merchant_id": gw.merchant_id,
        "api_key": api_key,
        "api_secret": api_secret,
        "is_sandbox": gw.is_sandbox,
        "sandbox_url": gw.sandbox_url,
        "production_url": gw.production_url,
        "callback_url": gw.callback_url,
        "redirect_url": gw.redirect_url,
        "extra_config": gw.extra_config,
        "api_key_env": api_key_env,
        "api_secret_env": api_secret_env,
    }


def _gateway_credential_status(gw: PaymentGatewayConfig) -> Dict[str, str]:
    runtime = _resolve_gateway_runtime_config(gw)
    key_ok = bool((runtime.get("api_key") or "").strip())
    secret_ok = bool((runtime.get("api_secret") or "").strip())
    if key_ok or secret_ok:
        source = "env" if not _allow_legacy_db_gateway_secrets() else "env_or_legacy_db"
    else:
        source = "missing"
    return {
        "api_key": "configured" if key_ok else "missing",
        "api_secret": "configured" if secret_ok else "missing",
        "credential_source": source,
        "api_key_env": runtime["api_key_env"],
        "api_secret_env": runtime["api_secret_env"],
    }


def _request_headers_to_dict(request: Request) -> Dict[str, str]:
    """Normalize request headers to a case-insensitive plain dict."""
    out: Dict[str, str] = {}
    for k, v in request.headers.items():
        out[k] = v
        out[k.lower()] = v
    return out


async def _extract_callback_payload(request: Request) -> Dict[str, Any]:
    """
    Support JSON and form-url-encoded callback payloads.
    Some providers send callbacks as application/x-www-form-urlencoded.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return {str(k): str(v) for k, v in form.items()}

    try:
        data = await request.json()
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.debug("Could not extract JSON body: %s", e)

    try:
        form = await request.form()
        return {str(k): str(v) for k, v in form.items()}
    except Exception as e:
        logger.debug("Could not extract form body: %s", e)
        return {}


def _enforce_rate_limit(
    request: Request,
    key: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    """
    Simple in-memory sliding-window rate limiter by IP + key.
    Used for login, forgot-password, reset-password, staff-login.
    Raises HTTPException(429) if limit exceeded.
    """
    _rate_limit_cleanup()
    now = time.time()
    client_ip = get_client_ip(request)
    bucket_key = f"{key}:{client_ip}"
    cutoff = now - float(window_seconds)
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.get(bucket_key, [])
        bucket = [ts for ts in bucket if ts >= cutoff]
        if len(bucket) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
        bucket.append(now)
        _RATE_LIMIT_BUCKETS[bucket_key] = bucket


def _normalize_and_validate_email(raw_email: str) -> str:
    """Normalize basic email input and reject obviously invalid values."""
    email = (raw_email or "").strip().lower()
    if not email or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid email address")
    return email


_STAFF_SESSION_TTL_DAYS = 7  # sessions last 7 days


def _extract_staff_token(request: Request) -> Optional[str]:
    """Extract staff session token from header only.
    Query-string tokens are not accepted — they leak into server logs and browser history.
    """
    header_token = request.headers.get("X-Staff-Token")
    if header_token:
        return header_token.strip()
    return None


def _get_staff_session_db(token: str, db: Session) -> Optional[dict]:
    """Look up a staff session from the database. Returns staff info dict or None."""
    now = _utcnow()
    row = (
        db.query(StaffSession)
        .filter(StaffSession.token == token, StaffSession.expires_at > now)
        .first()
    )
    if not row:
        return None
    staff = db.query(SupportStaff).filter(SupportStaff.id == row.staff_id).first()
    if not staff or not staff.is_active:
        return None
    return {
        "id": staff.id,
        "name": staff.name,
        "email": staff.email,
        "department": staff.department,
        "role": staff.role,
    }


async def require_admin_or_staff_admin(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Authorize admin APIs using either:
    1) JWT admin user (mobile/user auth), or
    2) Staff portal session token with admin role.
    """
    if current_user and current_user.is_admin:
        return {"mode": "jwt_admin", "user_id": current_user.id}

    staff_token = _extract_staff_token(request)
    if staff_token:
        session = _get_staff_session_db(staff_token, db)
        if session and session.get("role") == "admin":
            return {"mode": "staff_admin", "staff_id": session.get("id")}

    raise HTTPException(status_code=401, detail="Admin authentication required")


async def require_admin_or_staff_manager(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Authorize charging operations: admin or manager.
    Less restrictive than require_admin_or_staff_admin for Start/Stop.
    """
    if current_user and current_user.is_admin:
        return {"mode": "jwt_admin", "user_id": current_user.id}

    staff_token = _extract_staff_token(request)
    if staff_token:
        session = _get_staff_session_db(staff_token, db)
        if session and session.get("role") in ("admin", "manager"):
            return {"mode": "staff_admin", "staff_id": session.get("id")}

    raise HTTPException(status_code=401, detail="Authentication required")

# ── CORS — restrict origins in production ──
_allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]
_app_env = os.getenv("APP_ENV", "development").strip().lower()
if not _allowed_origins and _app_env in {"prod", "production"}:
    # Production fail-safe: deny cross-origin unless explicitly configured.
    _allowed_origins = []
elif not _allowed_origins:
    # Default: allow localhost for development
    _allowed_origins = [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:5000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Idempotency-Key", "X-Staff-Token"],
)

# Mount static files (resolve path relative to this file)
app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

# OCPI 2.2.1 - CPO interface for roaming (TNG integration)
from ocpi import router as ocpi_router
app.include_router(ocpi_router)

# Edge Sync - receive charger/session data pushed from local OCPP edge servers (Banana Pi)
from edge_sync import router as edge_sync_router
app.include_router(edge_sync_router)

# App Features — reviews, bookings, cost estimate, carbon footprint, kW graph, issue report
from features_router import router as features_router
app.include_router(features_router)


# ─── Health Check & Global Exception Handler ───────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 if the API is up and can connect to the database.
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> Any:
    """
    Catch-all handler for unhandled exceptions.
    Logs the error and returns a consistent 500 response.
    HTTPException is re-raised so FastAPI handles it normally.
    """
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "success": False},
    )


# ─── Pydantic Models & Dashboard Routes ───────────────────────────────────
class ChargerStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    charge_point_id: str
    vendor: Optional[str]
    model: Optional[str]
    firmware_version: Optional[str]
    status: str
    availability: str
    last_heartbeat: Optional[datetime]
    active_transaction_id: Optional[int] = None
    number_of_connectors: Optional[int] = None
    # Physical / location info
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    connector_type: Optional[str] = None
    max_power_kw: Optional[float] = None
    # Pricing (filled at query time)
    price_per_kwh: Optional[float] = None

    @field_serializer("last_heartbeat")
    def _ser_hb(self, v: Optional[datetime], _info) -> Optional[str]:
        return _iso_utc_naive_to_myt(v)


class CreateChargerRequest(BaseModel):
    """Request to manually register a charger (e.g. before OCPP BootNotification)."""
    charge_point_id: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None


class ChargingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    connector_id: Optional[int] = None
    start_time: datetime
    stop_time: Optional[datetime]
    energy_consumed: float
    status: str
    charger_id: int
    charge_point_id: str

    @field_serializer("start_time", "stop_time")
    def _ser_session_dt(self, v: Optional[datetime], _info) -> Optional[str]:
        return _iso_myt_naive_local(v)


class MeterValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    voltage: Optional[float]
    current: Optional[float]
    power: Optional[float]
    total_kwh: Optional[float]
    transaction_id: Optional[int]

    @field_serializer("timestamp")
    def _ser_mv_ts(self, v: datetime, _info) -> str:
        out = _iso_myt_naive_local(v)
        return out if out is not None else ""


class FaultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fault_type: str
    message: Optional[str]
    timestamp: datetime
    cleared: bool
    cleared_at: Optional[datetime]
    charger_id: int
    charge_point_id: str

    @field_serializer("timestamp", "cleared_at")
    def _ser_fault_dt(self, v: Optional[datetime], _info) -> Optional[str]:
        return _iso_utc_naive_to_myt(v)


class DeviceInfo(BaseModel):
    charge_point_id: str
    vendor: Optional[str]
    model: Optional[str]
    firmware_version: Optional[str]
    
    class Config:
        from_attributes = True


class ConfigurationKey(BaseModel):
    key: str
    readonly: Optional[bool] = None
    value: Optional[str] = None


class ConfigurationResponse(BaseModel):
    success: bool
    message: str
    configuration: List[ConfigurationKey] = []


class ChangeConfigurationRequest(BaseModel):
    key: str
    value: str


class ChangeConfigurationResponse(BaseModel):
    success: bool
    message: str


# ─── Maintenance Models ────────────────────────────────────────────────────

class MaintenanceCreate(BaseModel):
    charger_id: str  # charge_point_id
    maintenance_type: str  # repair, part_replacement, inspection, cleaning, firmware_update, other
    issue_description: Optional[str] = None
    work_performed: str
    parts_replaced: Optional[str] = None
    cost: Optional[float] = None
    technician_name: Optional[str] = None
    status: str = "completed"  # scheduled, in_progress, completed, cancelled
    date_scheduled: Optional[datetime] = None
    date_completed: Optional[datetime] = None
    notes: Optional[str] = None


class MaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = None
    issue_description: Optional[str] = None
    work_performed: Optional[str] = None
    parts_replaced: Optional[str] = None
    cost: Optional[float] = None
    technician_name: Optional[str] = None
    status: Optional[str] = None
    date_scheduled: Optional[datetime] = None
    date_completed: Optional[datetime] = None
    notes: Optional[str] = None


class MaintenanceResponse(BaseModel):
    id: int
    charger_id: int
    charge_point_id: str
    maintenance_type: str
    issue_description: Optional[str]
    work_performed: str
    parts_replaced: Optional[str]
    cost: Optional[float]
    technician_name: Optional[str]
    status: str
    date_reported: datetime
    date_scheduled: Optional[datetime]
    date_completed: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ─── Dashboard & HTML Page Routes ─────────────────────────────────────────
@app.get("/")
async def root():
    """Serve the dashboard"""
    try:
        file_path = _BASE_DIR / "templates" / "dashboard.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading dashboard: {str(e)}")


@app.get("/chargers")
async def chargers_page():
    """Serve the chargers page"""
    try:
        file_path = _BASE_DIR / "templates" / "chargers.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Chargers template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading chargers page: {str(e)}")


@app.get("/sessions")
async def sessions_page():
    """Serve the sessions page"""
    try:
        file_path = _BASE_DIR / "templates" / "sessions.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Sessions template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading sessions page: {str(e)}")


@app.get("/metering")
async def metering_page():
    """Serve the metering page"""
    try:
        file_path = _BASE_DIR / "templates" / "metering.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Metering template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metering page: {str(e)}")


@app.get("/faults")
async def faults_page():
    """Serve the faults page"""
    try:
        file_path = _BASE_DIR / "templates" / "faults.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Faults template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading faults page: {str(e)}")


@app.get("/settings")
async def settings_page():
    """Serve the settings/configuration page"""
    try:
        file_path = _BASE_DIR / "templates" / "settings.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Settings template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading settings page: {str(e)}")


@app.get("/payment-settings")
async def payment_settings_page():
    """Serve the payment gateway settings page"""
    file_path = Path("templates/payment_settings.html")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Payment settings template not found")
    return FileResponse(file_path, media_type="text/html")


@app.get("/api/chargers", response_model=List[ChargerStatus])
async def get_chargers(
    db: Session = Depends(get_db),
    online_only: Optional[str] = Query(
        None,
        description="If 1/true: only chargers that are OCPP-online OR charging/preparing OR have an active transaction id.",
    ),
):
    """Get all chargers with their status. Use online_only=1 for dropdowns (metering, sessions, operations)."""
    chargers = db.query(Charger).all()

    # Load pricing once: per-charger entries keyed by charger_id; fallback = charger_id IS NULL
    all_pricing = db.query(Pricing).filter(Pricing.is_active == True).all()
    pricing_by_charger: dict[Optional[int], float] = {}
    default_price: float = 0.50
    for p in all_pricing:
        if p.charger_id is None:
            default_price = float(p.price_per_kwh)
        else:
            pricing_by_charger[p.charger_id] = float(p.price_per_kwh)

    # Add active transaction_id for each charger
    result = []
    for charger in chargers:
        # Find active session for this charger
        # Include both active and recent pending sessions (within PENDING_SESSION_WINDOW_MINUTES)
        pending_cutoff = _utcnow() - timedelta(minutes=PENDING_SESSION_WINDOW_MINUTES)
        # Include interrupted/stopping so Stop button still gets a real OCPP transaction id
        active_session = db.query(ChargingSession).filter(
            ChargingSession.charger_id == charger.id,
            ChargingSession.transaction_id > 0,
            or_(
                ChargingSession.status.in_(["active", "interrupted", "stopping"]),
                and_(
                    ChargingSession.status == "pending",
                    ChargingSession.start_time >= pending_cutoff
                ),
            ),
        ).order_by(desc(ChargingSession.start_time)).first()

        # Compute effective status: recent heartbeat = online.
        # active_charge_points is in-memory and can desync on race conditions;
        # last_heartbeat in DB is the reliable source of truth.
        # If heartbeat is stale (> threshold), charger is offline regardless.
        heartbeat_age_ok = False
        if charger.last_heartbeat:
            age = _utcnow() - charger.last_heartbeat.replace(tzinfo=None)
            heartbeat_age_ok = age.total_seconds() < (OFFLINE_THRESHOLD_MINUTES * 60)

        if heartbeat_age_ok:
            effective_status = "online"
        else:
            effective_status = "offline"

        # Only expose a valid active transaction id (>0). Pending placeholders (<=0) shouldn't drive UI.
        active_txn_id = None
        if active_session and getattr(active_session, "transaction_id", None):
            if int(active_session.transaction_id) > 0:
                active_txn_id = int(active_session.transaction_id)

        # Trust charger.availability from StatusNotification (source of truth from device)
        # Don't use active_txn_id to force "charging" - session can be stale if charger stopped locally
        effective_availability = charger.availability or "unknown"
        if effective_status == "offline":
            effective_availability = "unavailable"

        if _want_online_only_list(online_only):
            include = (
                effective_status == "online"
                or effective_availability in ("charging", "preparing")
                or (active_txn_id is not None and active_txn_id > 0)
            )
            if not include:
                continue

        price_per_kwh = pricing_by_charger.get(charger.id, default_price)

        # Fill max_power_kw / connector_type from model name if not manually set
        eff_power, eff_connector = _effective_charger_specs(
            charger.max_power_kw, charger.connector_type, charger.model
        )

        charger_dict = {
            "id": charger.id,
            "charge_point_id": charger.charge_point_id,
            "vendor": charger.vendor,
            "model": charger.model,
            "firmware_version": charger.firmware_version,
            "status": effective_status,
            "availability": effective_availability,
            "last_heartbeat": charger.last_heartbeat,
            "active_transaction_id": active_txn_id,
            "number_of_connectors": charger.number_of_connectors,
            "location": charger.location,
            "latitude": charger.latitude,
            "longitude": charger.longitude,
            "connector_type": eff_connector,
            "max_power_kw": eff_power,
            "price_per_kwh": price_per_kwh,
        }
        result.append(ChargerStatus(**charger_dict))
    
    return result


@app.get("/api/chargers/{charge_point_id}/status", response_model=ChargerStatus)
async def get_charger_status(charge_point_id: str, db: Session = Depends(get_db)):
    """Get status of a specific charger"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")

    heartbeat_age_ok = False
    if charger.last_heartbeat:
        age = _utcnow() - charger.last_heartbeat.replace(tzinfo=None)
        heartbeat_age_ok = age.total_seconds() < (OFFLINE_THRESHOLD_MINUTES * 60)

    if heartbeat_age_ok:
        effective_status = "online"
    else:
        effective_status = "offline"

    effective_availability = charger.availability or "unknown"
    if effective_status == "offline":
        effective_availability = "unavailable"

    return ChargerStatus(
        id=charger.id,
        charge_point_id=charger.charge_point_id,
        vendor=charger.vendor,
        model=charger.model,
        firmware_version=charger.firmware_version,
        status=effective_status,
        availability=effective_availability,
        last_heartbeat=charger.last_heartbeat,
        active_transaction_id=None,
    )


@app.get("/api/events/firmware")
async def get_firmware_events(since: str = ""):
    """
    Return recent firmware status events.
    Frontend polls this to show toast notifications.
    Optional ?since=<ISO timestamp> to get only events after that time.
    """
    if not since:
        return {"events": firmware_events[-20:]}
    try:
        from datetime import datetime, timezone, timedelta
        since_dt = datetime.fromisoformat(since)
        filtered = [e for e in firmware_events if datetime.fromisoformat(e["timestamp"]) > since_dt]
        return {"events": filtered}
    except Exception:
        return {"events": firmware_events[-20:]}


@app.post("/api/admin/chargers", response_model=ChargerStatus)
async def admin_create_charger(
    req: CreateChargerRequest,
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
    db: Session = Depends(get_db),
):
    """
    Manually register a charger (e.g. ESP32) before it connects via OCPP.
    Charger will appear in dashboard; status becomes 'online' when it sends BootNotification.
    """
    import re
    cp_id = (req.charge_point_id or "").strip()
    if not cp_id or len(cp_id) < 3:
        raise HTTPException(status_code=400, detail="charge_point_id required (min 3 chars)")
    if not re.match(r"^[A-Za-z0-9._:-]{3,64}$", cp_id):
        raise HTTPException(status_code=400, detail="charge_point_id: alphanumeric, dots, _, -, : only")
    existing = db.query(Charger).filter(Charger.charge_point_id == cp_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Charger {cp_id} already exists")
    charger = Charger(
        charge_point_id=cp_id,
        vendor=req.vendor or "Manual",
        model=req.model or "ESP32",
        firmware_version=req.firmware_version or "Unknown",
        status="offline",
        availability="unknown",
    )
    db.add(charger)
    db.commit()
    db.refresh(charger)
    logger.info(f"Charger {cp_id} manually registered by admin")
    return charger


class UpdateChargerInfoRequest(BaseModel):
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    connector_type: Optional[str] = None
    max_power_kw: Optional[float] = None


@app.patch("/api/admin/chargers/{charge_point_id}/info")
async def update_charger_info(
    charge_point_id: str,
    req: UpdateChargerInfoRequest,
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
    db: Session = Depends(get_db),
):
    """Manually update charger physical info: location, GPS, connector type, max power."""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")
    if req.location is not None:
        charger.location = req.location
    if req.latitude is not None:
        charger.latitude = req.latitude
    if req.longitude is not None:
        charger.longitude = req.longitude
    if req.connector_type is not None:
        charger.connector_type = req.connector_type
    if req.max_power_kw is not None:
        charger.max_power_kw = req.max_power_kw
    db.commit()
    logger.info(f"Charger {charge_point_id} info updated by admin")
    eff_power, eff_connector = _effective_charger_specs(charger.max_power_kw, charger.connector_type, charger.model)
    return {
        "success": True,
        "charge_point_id": charge_point_id,
        "location": charger.location,
        "latitude": charger.latitude,
        "longitude": charger.longitude,
        "connector_type": eff_connector,
        "max_power_kw": eff_power,
    }


@app.post("/api/admin/chargers/{charge_point_id}/auto-detect")
async def auto_detect_charger_info(
    charge_point_id: str,
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
    db: Session = Depends(get_db),
):
    """
    Query the charger via OCPP GetConfiguration to auto-detect location (GPS keys)
    and update max_power_kw/connector_type from model name if not already set.
    """
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")

    updates = {}

    # Auto-fill power + connector from model name if not manually set
    if charger.max_power_kw is None and charger.model:
        parsed = _parse_power_from_model(charger.model)
        if parsed:
            charger.max_power_kw = parsed
            updates["max_power_kw"] = parsed

    if charger.connector_type is None and charger.max_power_kw is not None:
        inferred = _infer_connector_type(charger.max_power_kw)
        if inferred:
            charger.connector_type = inferred
            updates["connector_type"] = inferred

    # Try GetConfiguration for GPS location keys
    cp = get_active_charge_point(charge_point_id)
    gps_found = False
    if cp:
        try:
            gps_keys = [
                "ChargePointLatitude", "ChargePointLongitude",
                "GPSLatitude", "GPSLongitude",
                "Latitude", "Longitude",
                "ChargePointLocation",
            ]
            config_resp = await cp.get_configuration(key=gps_keys)
            if config_resp and hasattr(config_resp, 'configuration_key'):
                config_map = {
                    item['key'].lower(): item.get('value', '')
                    for item in (config_resp.configuration_key or [])
                }
                lat_val = (
                    config_map.get('chargepointlatitude') or
                    config_map.get('gpslatitude') or
                    config_map.get('latitude')
                )
                lng_val = (
                    config_map.get('chargepointlongitude') or
                    config_map.get('gpslongitude') or
                    config_map.get('longitude')
                )
                if lat_val and lng_val:
                    try:
                        charger.latitude = float(lat_val)
                        charger.longitude = float(lng_val)
                        updates["latitude"] = charger.latitude
                        updates["longitude"] = charger.longitude
                        gps_found = True
                    except ValueError:
                        pass
        except Exception as e:
            logger.warning(f"GetConfiguration for GPS failed on {charge_point_id}: {e}")

    db.commit()
    return {
        "success": True,
        "charge_point_id": charge_point_id,
        "updates": updates,
        "gps_found_via_ocpp": gps_found,
        "message": "GPS not available via OCPP — please set location manually via PATCH /api/admin/chargers/{id}/info" if not gps_found else "GPS coordinates retrieved from charger",
    }


@app.get("/api/sessions", response_model=List[ChargingSessionResponse])
async def get_sessions(
    limit: int = 50,
    charger_id: Optional[int] = None,
    charge_point_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get charging sessions"""
    query = db.query(ChargingSession)
    
    if charger_id:
        query = query.filter(ChargingSession.charger_id == charger_id)
    elif charge_point_id:
        charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        if charger:
            query = query.filter(ChargingSession.charger_id == charger.id)
        else:
            return []
    
    sessions = query.order_by(desc(ChargingSession.start_time)).limit(limit).all()
    
    # Add charge_point_id to each session
    result = []
    for session in sessions:
        charger = db.query(Charger).filter(Charger.id == session.charger_id).first()
        session_dict = {
            **session.__dict__,
            "charge_point_id": charger.charge_point_id if charger else "Unknown"
        }
        result.append(ChargingSessionResponse(**session_dict))
    
    return result


@app.get("/api/metering/{charge_point_id}", response_model=List[MeterValueResponse])
async def get_metering(
    charge_point_id: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get metering data for a charger"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    meter_values = db.query(MeterValue).filter(
        MeterValue.charger_id == charger.id
    ).order_by(desc(MeterValue.timestamp)).limit(limit).all()
    
    return meter_values


@app.get("/api/metering/{charge_point_id}/latest", response_model=MeterValueResponse)
async def get_latest_metering(charge_point_id: str, db: Session = Depends(get_db)):
    """Get latest metering data for a charger"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")
    
    meter_value = db.query(MeterValue).filter(
        MeterValue.charger_id == charger.id
    ).order_by(desc(MeterValue.timestamp)).first()
    
    if not meter_value:
        raise HTTPException(status_code=404, detail="No metering data found")
    
    return meter_value


@app.get("/api/faults", response_model=List[FaultResponse])
async def get_faults(
    cleared: Optional[bool] = None,
    charger_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get faults"""
    query = db.query(Fault)
    
    if cleared is not None:
        query = query.filter(Fault.cleared == cleared)
    
    if charger_id:
        query = query.filter(Fault.charger_id == charger_id)
    
    faults = query.order_by(desc(Fault.timestamp)).all()
    
    # Add charge_point_id to each fault
    result = []
    for fault in faults:
        charger = db.query(Charger).filter(Charger.id == fault.charger_id).first()
        fault_dict = {
            **fault.__dict__,
            "charge_point_id": charger.charge_point_id if charger else "Unknown"
        }
        result.append(FaultResponse(**fault_dict))
    
    return result


@app.get("/api/device/{charge_point_id}", response_model=DeviceInfo)
async def get_device_info(charge_point_id: str, db: Session = Depends(get_db)):
    """Get device information"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found")
    return charger


@app.get("/api/chargers/{charge_point_id}/configuration", response_model=ConfigurationResponse)
async def get_charger_configuration(
    charge_point_id: str,
    keys: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get charger configuration via OCPP GetConfiguration (like SteVe).

    - `keys` (optional, comma-separated): limit to specific keys
    - If no keys → request full configuration
    """
    try:
        logger.info(f"GetConfiguration API called for charger {charge_point_id} with keys={keys}")

        # Ensure charger exists
        charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")

        # Ensure charger is connected to OCPP server
        cp = get_active_charge_point(charge_point_id)
        if not cp:
            return ConfigurationResponse(
                success=False,
                message=f"Charger {charge_point_id} is not currently connected to OCPP server.",
                configuration=[],
            )

        # Parse keys (comma-separated string → list)
        key_list: Optional[List[str]] = None
        if keys:
            key_list = [k.strip() for k in keys.split(",") if k.strip()]

        resp = await cp.get_configuration(key_list)
        if not resp:
            return ConfigurationResponse(
                success=False,
                message="No response from charger (GetConfiguration).",
                configuration=[],
            )

        config_items: List[ConfigurationKey] = []

        # `configuration_key` is a list of objects with: key, readonly, value
        for item in getattr(resp, "configuration_key", []) or []:
            try:
                config_items.append(
                    ConfigurationKey(
                        key=item.get("key") if isinstance(item, dict) else getattr(item, "key", None),
                        readonly=item.get("readonly") if isinstance(item, dict) else getattr(item, "readonly", None),
                        value=item.get("value") if isinstance(item, dict) else getattr(item, "value", None),
                    )
                )
            except Exception as e:
                logger.error(f"Error parsing configuration item {item}: {e}", exc_info=True)

        # Unknown keys (if any)
        unknown_keys = getattr(resp, "unknown_key", []) or []
        msg_suffix = ""
        if unknown_keys:
            msg_suffix = f" Some keys were unknown: {', '.join(unknown_keys)}"

        return ConfigurationResponse(
            success=True,
            message=f"Received {len(config_items)} configuration key(s).{msg_suffix}",
            configuration=config_items,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling GetConfiguration API for {charge_point_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting configuration: {str(e)}")


@app.post("/api/chargers/{charge_point_id}/configuration/change", response_model=ChangeConfigurationResponse)
async def change_charger_configuration(
    charge_point_id: str,
    request: ChangeConfigurationRequest,
    db: Session = Depends(get_db),
):
    """
    Change charger configuration via OCPP ChangeConfiguration.

    Example body:
    {
      "key": "HeartbeatInterval",
      "value": "10"
    }
    """
    try:
        logger.info(f"ChangeConfiguration API called for charger {charge_point_id}: {request.key}={request.value}")

        charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")

        cp = get_active_charge_point(charge_point_id)
        if not cp:
            return ChangeConfigurationResponse(
                success=False,
                message=f"Charger {charge_point_id} is not currently connected to OCPP server.",
            )

        resp = await cp.change_configuration(request.key, request.value)
        if not resp:
            return ChangeConfigurationResponse(
                success=False,
                message="No response from charger (ChangeConfiguration).",
            )

        status = getattr(resp, "status", None) or "Unknown"
        if status != "Accepted":
            return ChangeConfigurationResponse(
                success=False,
                message=f"ChangeConfiguration rejected by charger: {status}",
            )

        # If HeartbeatInterval successfully changed, store it in DB too (for BootNotification interval)
        if request.key == "HeartbeatInterval":
            try:
                charger.heartbeat_interval = int(request.value)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to persist HeartbeatInterval={request.value} for {charge_point_id}: {e}", exc_info=True)
                db.rollback()

        return ChangeConfigurationResponse(
            success=True,
            message=f"Configuration '{request.key}' updated to '{request.value}' (status={status}).",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling ChangeConfiguration API for {charge_point_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error changing configuration: {str(e)}")


# ==================== OCPP 1.6 OPERATIONS API ====================

class OcppOperationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None


class ChangeAvailabilityRequest(BaseModel):
    connector_id: int = 0
    type: str = "Inoperative"  # Operative or Inoperative


class ResetRequest(BaseModel):
    type: str = "Soft"  # Hard or Soft


class UnlockConnectorRequest(BaseModel):
    connector_id: int = 1


class GetDiagnosticsRequest(BaseModel):
    location: str  # URI where diagnostics file should be uploaded
    retries: Optional[int] = None
    retry_interval: Optional[int] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None


class UpdateFirmwareRequest(BaseModel):
    location: str  # URI of firmware
    retrieve_date: str  # ISO 8601 datetime
    retries: Optional[int] = None
    retry_interval: Optional[int] = None


class BulkUpdateFirmwareRequest(BaseModel):
    charge_point_ids: List[str]  # list of charger IDs to update; empty = all connected
    location: str
    retrieve_date: str
    retries: Optional[int] = None
    retry_interval: Optional[int] = None
    delay_between_seconds: Optional[float] = 1.0  # stagger commands to avoid flood


class ReserveNowRequest(BaseModel):
    connector_id: int = 0
    expiry_date: str  # ISO 8601 datetime
    id_tag: str
    reservation_id: int


class CancelReservationRequest(BaseModel):
    reservation_id: int


class DataTransferRequest(BaseModel):
    vendor_id: str
    message_id: Optional[str] = None
    data: Optional[str] = None


class GacSetChargingScheduleRequest(BaseModel):
    """GAC vendor-specific SetChargingSchedule via DataTransfer.

    dateSchedule: list of day numbers — 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun
    start_time / end_time: "HH:MM" 24-hour format (e.g. "08:00", "18:30") in MYT (UTC+8)
    date: optional "YYYY-MM-DD" — defaults to today in MYT. Use to schedule a future date.
    reservation_id: integer, default 1
    recurrency: true = repeats weekly on dateSchedule days; false = one-shot
    purpose: "set" to set schedule, "clear" to remove
    """
    start_time: str           # "HH:MM"
    end_time: str             # "HH:MM"
    date_schedule: list[int]  # e.g. [1,2,3,4,5] for weekdays
    date: Optional[str] = None  # "YYYY-MM-DD", defaults to today MYT
    reservation_id: int = 1
    recurrency: bool = True
    purpose: str = "set"


class SendLocalListRequest(BaseModel):
    list_version: int
    update_type: str = "Full"  # Full or Differential
    local_authorization_list: Optional[list] = None


class TriggerMessageRequest(BaseModel):
    requested_message: str  # e.g. BootNotification, StatusNotification, Heartbeat, MeterValues
    connector_id: Optional[int] = None


class GetCompositeScheduleRequest(BaseModel):
    connector_id: int = 1
    duration: int = 3600
    charging_rate_unit: Optional[str] = None  # W or A


class ClearChargingProfileRequest(BaseModel):
    id: Optional[int] = None
    connector_id: Optional[int] = None
    charging_profile_purpose: Optional[str] = None
    stack_level: Optional[int] = None


class SetChargingProfileRequest(BaseModel):
    connector_id: int = 1
    cs_charging_profiles: Dict


# Serve OCPP Operations page
@app.get("/operations")
async def operations_page():
    """Serve the OCPP 1.6 Operations page"""
    try:
        file_path = Path("templates/operations.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Operations template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading operations page: {str(e)}")


@app.get("/staff-portal")
async def staff_portal_page():
    """Serve the staff portal page"""
    try:
        file_path = Path("templates/staff_portal.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Staff portal template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading staff portal: {str(e)}")


@app.get("/login")
async def login_page():
    """Centralized staff login page — redirects to appropriate portal based on role."""
    try:
        file_path = Path("templates/login.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Login page not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading login page: {str(e)}")


@app.get("/my-tickets")
async def my_tickets_page():
    """My Tickets page — shows tickets assigned to the logged-in staff member."""
    try:
        file_path = Path("templates/my_tickets.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="My Tickets page not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading my tickets page: {str(e)}")


@app.get("/topup")
async def topup_page():
    """User-facing top-up page — login, select amount, pay via TNG QR."""
    try:
        file_path = Path("templates/topup.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Top-up page not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading top-up page: {str(e)}")


@app.get("/pay")
async def quick_pay_page():
    """Guest-facing quick-pay page — opened from the QR sticker on a charger.
    Reads ?charger=<id>&connector=<n> from the URL, asks for amount + email,
    creates a payment via /api/charging/quick-pay, then polls for completion
    while showing the TNG QR. On success the backend triggers RemoteStart."""
    try:
        file_path = _BASE_DIR / "templates" / "pay.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Pay page not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading pay page: {str(e)}")


@app.post("/api/ocpp/{charge_point_id}/change-availability", response_model=OcppOperationResponse)
async def ocpp_change_availability(charge_point_id: str, request: ChangeAvailabilityRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 ChangeAvailability"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.change_availability(request.connector_id, request.type)
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status in ("Accepted", "Scheduled"), message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/clear-cache", response_model=OcppOperationResponse)
async def ocpp_clear_cache(charge_point_id: str, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 ClearCache"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.clear_cache()
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/reset", response_model=OcppOperationResponse)
async def ocpp_reset(charge_point_id: str, request: ResetRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 Reset"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.reset(request.type)
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/unlock-connector", response_model=OcppOperationResponse)
async def ocpp_unlock_connector(charge_point_id: str, request: UnlockConnectorRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 UnlockConnector"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.unlock_connector(request.connector_id)
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Unlocked", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/get-diagnostics", response_model=OcppOperationResponse)
async def ocpp_get_diagnostics(charge_point_id: str, request: GetDiagnosticsRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 GetDiagnostics"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.get_diagnostics(
        location=request.location, retries=request.retries,
        retry_interval=request.retry_interval,
        start_time=request.start_time, stop_time=request.stop_time
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    file_name = getattr(resp, "file_name", None)
    return OcppOperationResponse(success=True, message=f"Diagnostics file: {file_name or 'N/A'}", data={"file_name": file_name})


@app.post("/api/ocpp/{charge_point_id}/update-firmware", response_model=OcppOperationResponse)
async def ocpp_update_firmware(charge_point_id: str, request: UpdateFirmwareRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 UpdateFirmware"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.update_firmware(
        location=request.location, retrieve_date=request.retrieve_date,
        retries=request.retries, retry_interval=request.retry_interval
    )
    return OcppOperationResponse(success=True, message="UpdateFirmware command sent (no response expected in OCPP 1.6).")


@app.post("/api/ocpp/bulk/update-firmware")
async def ocpp_bulk_update_firmware(request: BulkUpdateFirmwareRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """Send UpdateFirmware to multiple chargers at once. If charge_point_ids is empty, targets all currently connected chargers."""
    from ocpp_server import active_charge_points

    if request.charge_point_ids:
        target_ids = request.charge_point_ids
    else:
        target_ids = list(active_charge_points.keys())

    if not target_ids:
        return {"success": False, "message": "No chargers specified and none are currently connected.", "results": []}

    delay = max(0.0, min(float(request.delay_between_seconds or 1.0), 10.0))
    results = []

    for idx, cp_id in enumerate(target_ids):
        if idx > 0 and delay > 0:
            await asyncio.sleep(delay)

        cp = get_active_charge_point(cp_id)
        if not cp:
            results.append({"charge_point_id": cp_id, "success": False, "message": "Not connected"})
            continue

        try:
            await cp.update_firmware(
                location=request.location,
                retrieve_date=request.retrieve_date,
                retries=request.retries,
                retry_interval=request.retry_interval,
            )
            results.append({"charge_point_id": cp_id, "success": True, "message": "Command sent"})
            logger.info(f"Bulk UpdateFirmware sent to {cp_id}")
        except Exception as e:
            results.append({"charge_point_id": cp_id, "success": False, "message": str(e)})
            logger.error(f"Bulk UpdateFirmware error for {cp_id}: {e}")

    sent = sum(1 for r in results if r["success"])
    failed = len(results) - sent
    return {
        "success": failed == 0,
        "message": f"Sent to {sent}/{len(results)} charger(s). {failed} failed.",
        "results": results,
    }


@app.post("/api/ocpp/{charge_point_id}/reserve-now", response_model=OcppOperationResponse)
async def ocpp_reserve_now(charge_point_id: str, request: ReserveNowRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 ReserveNow"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.reserve_now(
        connector_id=request.connector_id, expiry_date=request.expiry_date,
        id_tag=request.id_tag, reservation_id=request.reservation_id
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/cancel-reservation", response_model=OcppOperationResponse)
async def ocpp_cancel_reservation(charge_point_id: str, request: CancelReservationRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 CancelReservation"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.cancel_reservation(request.reservation_id)
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/data-transfer", response_model=OcppOperationResponse)
async def ocpp_data_transfer(charge_point_id: str, request: DataTransferRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 DataTransfer"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.data_transfer(vendor_id=request.vendor_id, message_id=request.message_id, data=request.data)
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    resp_data = getattr(resp, "data", None)
    if status == "Invalid":
        msg = (
            "Status: Invalid — charger rejected the vendor payload (wrong schedule fields, time window, "
            "or feature not enabled). GAC firmware uses non-standard OCPP DataTransfer status."
        )
    elif status == "Timeout":
        msg = (
            "Status: Timeout — no CallResult from the charger within 90s. "
            "Some GAC firmware only replies to Message ID ChargingSchedule (not SetChargingSchedule); "
            "if both time out, the station may not support this vendor command."
        )
    else:
        msg = f"Status: {status}"
    return OcppOperationResponse(success=status == "Accepted", message=msg, data={"status": status, "data": resp_data})


@app.post("/api/ocpp/{charge_point_id}/gac-set-charging-schedule", response_model=OcppOperationResponse)
async def ocpp_gac_set_charging_schedule(
    charge_point_id: str,
    request: GacSetChargingScheduleRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_or_staff_admin),
):
    """GAC vendor-specific scheduled charging via DataTransfer.

    Sends SetChargingSchedule with base64-encoded JSON payload as required by GAC firmware.
    Confirmed format: full ISO datetime with timezone (e.g. "2026-04-13T11:30:00+08:00").

    dateSchedule day numbers: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun
    startTime / endTime: "HH:MM" 24-hour format — server builds full ISO datetime in MYT (UTC+8).
    """
    import base64, json as _json

    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")

    # Validate time format
    time_pattern = re.compile(r'^\d{2}:\d{2}$')
    if not time_pattern.match(request.start_time) or not time_pattern.match(request.end_time):
        raise HTTPException(status_code=400, detail="startTime and endTime must be in HH:MM format (e.g. '08:00')")

    # Validate day numbers
    valid_days = set(range(1, 8))  # 1–7
    if not all(d in valid_days for d in request.date_schedule):
        raise HTTPException(status_code=400, detail="dateSchedule values must be 1–7 (1=Mon ... 7=Sun)")

    # Build full ISO datetime with MYT timezone (+08:00)
    myt = timezone(timedelta(hours=8))
    if request.date:
        try:
            base_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format")
    else:
        base_date = datetime.now(myt).date()

    start_h, start_m = map(int, request.start_time.split(":"))
    end_h, end_m = map(int, request.end_time.split(":"))

    start_dt = datetime(base_date.year, base_date.month, base_date.day, start_h, start_m, 0, tzinfo=myt)
    end_dt = datetime(base_date.year, base_date.month, base_date.day, end_h, end_m, 0, tzinfo=myt)

    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # Build payload and base64-encode as required by GAC firmware
    payload = {
        "purpose": request.purpose,
        "reservationId": request.reservation_id,
        "recurrency": request.recurrency,
        "startTime": start_iso,
        "endTime": end_iso,
        "dateSchedule": request.date_schedule,
    }
    encoded_data = base64.b64encode(_json.dumps(payload, separators=(',', ':')).encode()).decode()

    logger.info(
        f"GAC SetChargingSchedule → {charge_point_id}: "
        f"days={request.date_schedule} {start_iso}–{end_iso} "
        f"recurrency={request.recurrency} purpose={request.purpose}"
    )

    resp = await cp.data_transfer(
        vendor_id="GAC",
        message_id="SetChargingSchedule",
        data=encoded_data,
    )

    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")

    status = getattr(resp, "status", "Unknown")
    resp_data = getattr(resp, "data", None)

    if status == "Accepted":
        day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri",6:"Sat",7:"Sun"}
        days_str = ", ".join(day_names.get(d, str(d)) for d in request.date_schedule)
        msg = f"Schedule set: {request.start_time}–{request.end_time} on {days_str}"
    elif status == "Invalid":
        msg = "Charger rejected the schedule (status: Invalid). Check time format or whether the feature is enabled on this unit."
    elif status == "Timeout":
        msg = "No response from charger within timeout. The unit may not support SetChargingSchedule."
    else:
        msg = f"Status: {status}"

    return OcppOperationResponse(
        success=status == "Accepted",
        message=msg,
        data={"status": status, "payload_sent": payload, "data": resp_data},
    )


@app.post("/api/ocpp/{charge_point_id}/get-local-list-version", response_model=OcppOperationResponse)
async def ocpp_get_local_list_version(charge_point_id: str, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 GetLocalListVersion"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.get_local_list_version()
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    version = getattr(resp, "list_version", None)
    return OcppOperationResponse(success=True, message=f"Local list version: {version}", data={"list_version": version})


@app.post("/api/ocpp/{charge_point_id}/send-local-list", response_model=OcppOperationResponse)
async def ocpp_send_local_list(charge_point_id: str, request: SendLocalListRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 SendLocalList"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.send_local_list(
        list_version=request.list_version, update_type=request.update_type,
        local_authorization_list=request.local_authorization_list
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/trigger-message", response_model=OcppOperationResponse)
async def ocpp_trigger_message(charge_point_id: str, request: TriggerMessageRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 TriggerMessage"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.trigger_message(
        requested_message=request.requested_message, connector_id=request.connector_id
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status in ("Accepted", "NotImplemented"), message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/get-composite-schedule", response_model=OcppOperationResponse)
async def ocpp_get_composite_schedule(charge_point_id: str, request: GetCompositeScheduleRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 GetCompositeSchedule"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.get_composite_schedule(
        connector_id=request.connector_id, duration=request.duration,
        charging_rate_unit=request.charging_rate_unit
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    schedule = getattr(resp, "charging_schedule", None)
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status, "charging_schedule": schedule})


@app.post("/api/ocpp/{charge_point_id}/clear-charging-profile", response_model=OcppOperationResponse)
async def ocpp_clear_charging_profile(charge_point_id: str, request: ClearChargingProfileRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 ClearChargingProfile"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.clear_charging_profile(
        id=request.id, connector_id=request.connector_id,
        charging_profile_purpose=request.charging_profile_purpose,
        stack_level=request.stack_level
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


@app.post("/api/ocpp/{charge_point_id}/set-charging-profile", response_model=OcppOperationResponse)
async def ocpp_set_charging_profile(charge_point_id: str, request: SetChargingProfileRequest, db: Session = Depends(get_db), _: dict = Depends(require_admin_or_staff_admin)):
    """OCPP 1.6 SetChargingProfile"""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")
    cp = get_active_charge_point(charge_point_id)
    if not cp:
        return OcppOperationResponse(success=False, message=f"Charger {charge_point_id} is not connected.")
    resp = await cp.set_charging_profile(
        connector_id=request.connector_id,
        cs_charging_profiles=request.cs_charging_profiles
    )
    if not resp:
        return OcppOperationResponse(success=False, message="No response from charger.")
    status = getattr(resp, "status", "Unknown")
    return OcppOperationResponse(success=status == "Accepted", message=f"Status: {status}", data={"status": status})


# Charging Control Endpoints
class StartChargingRequest(BaseModel):
    charger_id: str  # charge_point_id
    connector_id: int = 1
    id_tag: str = "APP_USER"


class StopChargingRequest(BaseModel):
    transaction_id: int = 0
    charger_id: Optional[str] = None  # optional charge_point_id for best-effort stop


class ChargingResponse(BaseModel):
    success: bool
    message: str
    transaction_id: Optional[int] = None


@app.post("/api/charging/start", response_model=ChargingResponse, status_code=200)
async def start_charging(request: StartChargingRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_manager)):
    """
    Start charging session via RemoteStartTransaction
    
    Flow:
    1. AppEV sends request → ChargingPlatform API
    2. ChargingPlatform validates charger status
    3. ChargingPlatform sends RemoteStartTransaction to charger via OCPP
    4. Charger starts charging and sends StartTransaction back
    5. Returns success response to AppEV
    """
    try:
        logger.info(f"Start charging request received: charger_id={request.charger_id}, connector_id={request.connector_id}, id_tag={request.id_tag}")
        
        # Check if charger exists
        charger = db.query(Charger).filter(Charger.charge_point_id == request.charger_id).first()
        if not charger:
            logger.warning(f"Charger {request.charger_id} not found")
            return ChargingResponse(
                success=False,
                message=f"Charger {request.charger_id} not found"
            )
        
        # Validate connector_id
        max_connectors = charger.number_of_connectors if hasattr(charger, 'number_of_connectors') and charger.number_of_connectors else 1
        if request.connector_id < 1 or request.connector_id > max_connectors:
            logger.warning(f"Invalid connector_id {request.connector_id} for charger with {max_connectors} connector(s)")
            return ChargingResponse(
                success=False,
                message=f"Invalid connector_id. Charger has {max_connectors} connector(s)"
            )
        
        # Check if charger is online
        if charger.status != "online":
            logger.warning(f"Charger {request.charger_id} is offline (status: {charger.status})")
            return ChargingResponse(
                success=False,
                message=f"Charger {request.charger_id} is offline"
            )
        
        # Check if charger is available
        if charger.availability not in ["available", "preparing"]:
            logger.warning(f"Charger {request.charger_id} is not available (status: {charger.availability})")
            return ChargingResponse(
                success=False,
                message=f"Charger {request.charger_id} is not available (status: {charger.availability})"
            )
        
        # Get active charge point connection
        charge_point = get_active_charge_point(request.charger_id)
        if not charge_point:
            logger.error(f"Charger {request.charger_id} is not connected to OCPP server")
            return ChargingResponse(
                success=False,
                message=f"Charger {request.charger_id} is not connected. Please ensure charger is connected to OCPP server."
            )
        
        # Send RemoteStartTransaction to charger via OCPP
        logger.info(f"Sending RemoteStartTransaction to charger {request.charger_id}")
        response = await charge_point.remote_start_transaction(
            connector_id=request.connector_id,
            id_tag=request.id_tag
        )
        
        if response and response.status == "Accepted":
            # Create charging session record
            # Note: Transaction ID will be updated when StartTransaction is received from charger
            # Don't create session with transaction_id = 0 (unique constraint violation)
            # Instead, create pending session without transaction_id, or wait for StartTransaction
            try:
                # Check if pending session already exists
                existing_pending = db.query(ChargingSession).filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.status == "pending"
                ).first()
                
                if not existing_pending:
                    # Create pending session using a unique negative transaction_id.
                    # We flush first to get the auto-increment PK, then set
                    # transaction_id = -session.id so it's unique and clearly temporary.
                    # on_start_transaction will overwrite it with the real assigned ID.
                    session = ChargingSession(
                        charger_id=charger.id,
                        transaction_id=0,  # placeholder; replaced below after flush
                        start_time=datetime.now(MYT).replace(tzinfo=None),
                        status="pending",
                        user_id=request.id_tag
                    )
                    db.add(session)
                    db.flush()  # populate session.id from auto-increment
                    session.transaction_id = -session.id  # unique negative value
                    db.commit()
                
                # Update charger availability to "charging" or "unavailable" since it's now in use
                # This ensures dashboard and AppEV show correct state immediately
                charger.availability = "charging"  # Set to charging since we just started
                db.commit()
                
                logger.info(f"Charging started successfully for charger {request.charger_id}, availability set to 'charging'")
                return ChargingResponse(
                    success=True,
                    message="Charging started successfully. Charger is starting...",
                    transaction_id=0  # Will be updated when transaction starts
                )
            except Exception as e:
                logger.error(f"Error creating pending session: {e}", exc_info=True)
                db.rollback()
                # Still return success - charger might start charging anyway
                return ChargingResponse(
                    success=True,
                    message="Charging request sent. Waiting for charger to start...",
                    transaction_id=0
                )
        else:
            # Charger didn't respond or rejected
            if not response:
                # Timeout or no response - charger might still start charging locally
                # Don't fail, just log and return success
                logger.warning(f"Charger {request.charger_id} did not respond to RemoteStartTransaction. Charger may start charging locally.")
                # Update charger availability to preparing
                charger.availability = "preparing"
                db.commit()
                return ChargingResponse(
                    success=True,
                    message="Charging request sent. Charger may start charging locally. Waiting for confirmation...",
                    transaction_id=0
                )
            else:
                status = response.status if hasattr(response, 'status') else str(response)
                if status == "Rejected":
                    error_msg = "Charger rejected the start request. Charger may be unavailable or already charging."
                elif status == "NotSupported":
                    error_msg = "Charger does not support RemoteStartTransaction."
                else:
                    error_msg = f"Failed to start charging: {status}"
                
                logger.error(f"RemoteStartTransaction failed for {request.charger_id}: {error_msg}")
                return ChargingResponse(
                    success=False,
                    message=error_msg
                )
            
    except Exception as e:
        logger.error(f"Error starting charging: {e}", exc_info=True)
        return ChargingResponse(
            success=False,
            message="An unexpected error occurred"
        )


@app.post("/api/charging/stop", response_model=ChargingResponse, status_code=200)
async def stop_charging(request: StopChargingRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_manager)):
    """
    Stop charging session via RemoteStopTransaction
    
    Flow:
    1. AppEV sends stop request → ChargingPlatform API
    2. ChargingPlatform finds active session
    3. ChargingPlatform sends RemoteStopTransaction to charger via OCPP
    4. Charger stops charging and sends StopTransaction back
    5. Returns success response to AppEV
    """
    try:
        logger.info(f"Stop charging request received: transaction_id={request.transaction_id}, charger_id={request.charger_id}")
        
        session = None
        charger = None

        # 1) Normal path: have real transaction_id → look up session
        if request.transaction_id and request.transaction_id > 0:
            session = db.query(ChargingSession).filter(
                ChargingSession.transaction_id == request.transaction_id,
                ChargingSession.status.in_(["active", "pending", "interrupted", "stopping"]),
            ).first()
            if not session:
                logger.warning(f"Session with transaction_id {request.transaction_id} not found")
        # 2) Resolve charger + session when caller sends charger_id (dashboard often sends transaction_id=0)
        if not session and request.charger_id:
            logger.info(f"Resolving session by charger_id={request.charger_id}")
            charger = db.query(Charger).filter(Charger.charge_point_id == request.charger_id).first()
            if not charger:
                logger.error("Charger not found for fallback stop")
                return ChargingResponse(
                    success=False,
                    message=f"Charger {request.charger_id} not found"
                )
            session = (
                db.query(ChargingSession)
                .filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.transaction_id > 0,
                    ChargingSession.status.in_(
                        ["active", "pending", "interrupted", "stopping"]
                    ),
                )
                .order_by(desc(ChargingSession.start_time))
                .first()
            )
            if session:
                logger.info(
                    f"Using session transaction_id={session.transaction_id} status={session.status} for RemoteStop"
                )
        elif session:
            charger = db.query(Charger).filter(Charger.id == session.charger_id).first()
            if not charger:
                logger.error("Charger not found for session")
                return ChargingResponse(
                    success=False,
                    message="Charger not found"
                )
        
        if not charger:
            # Neither a valid session nor charger_id provided
            return ChargingResponse(
                success=False,
                message="No active charging session found and no charger_id provided for fallback stop"
            )

        # Get active charge point connection
        charge_point = get_active_charge_point(charger.charge_point_id)
        if not charge_point:
            logger.error(f"Charger {charger.charge_point_id} is not connected to OCPP server")
            return ChargingResponse(
                success=False,
                message=f"Charger {charger.charge_point_id} is not connected"
            )
        
        # OCPP RemoteStopTransaction requires the charger's current transaction id — never send 0
        txn_id_for_stop = 0
        if session and session.transaction_id and int(session.transaction_id) > 0:
            txn_id_for_stop = int(session.transaction_id)
        elif request.transaction_id and request.transaction_id > 0:
            txn_id_for_stop = int(request.transaction_id)
        if txn_id_for_stop <= 0:
            logger.error(
                f"Cannot RemoteStop: no transaction id (charger={charger.charge_point_id}, session={session})"
            )
            return ChargingResponse(
                success=False,
                message="No active transaction to stop. Refresh the page; if charging continues, check OCPP session state.",
            )

        logger.info(f"Sending RemoteStopTransaction to charger {charger.charge_point_id} using transaction_id={txn_id_for_stop}")
        response = await charge_point.remote_stop_transaction(
            transaction_id=txn_id_for_stop
        )
        
        status = getattr(response, "status", None) if response else None
        if response and status == "Accepted":
            if session:
                session.status = "stopping"
                db.commit()
            logger.info(f"Charging stop requested successfully for charger {charger.charge_point_id} (txn_id={txn_id_for_stop}, status={status})")
            return ChargingResponse(
                success=True,
                message="Charging stop request sent to charger. It may take a few seconds to stop.",
                transaction_id=txn_id_for_stop,
            )
        if not response:
            logger.error("RemoteStopTransaction: no response from charger")
            return ChargingResponse(
                success=False,
                message="No response from charger for RemoteStopTransaction.",
            )
        logger.error(f"RemoteStopTransaction failed: {status}")
        return ChargingResponse(
            success=False,
            message=f"Failed to stop charging: {status}",
        )
    except Exception as e:
        logger.error(f"Error stopping charging: {e}", exc_info=True)
        return ChargingResponse(
            success=False,
            message="An unexpected error occurred"
        )


# ==================== CHARGING SCHEDULES ====================

class ChargingScheduleRequest(BaseModel):
    connector_id: int = 1
    id_tag: str = "APP_USER"
    start_time: str          # "HH:MM" 24h
    stop_time: str           # "HH:MM" 24h
    days_of_week: str = "daily"  # "daily" or "0,1,2,..." where 0=Sun
    enabled: bool = True


class ChargingScheduleResponse(BaseModel):
    id: int
    charge_point_id: str
    connector_id: int
    id_tag: str
    start_time: str
    stop_time: str
    days_of_week: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _validate_hhmm(s: str) -> bool:
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


@app.get("/api/chargers/{charge_point_id}/schedules", response_model=List[ChargingScheduleResponse])
async def list_charging_schedules(
    charge_point_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all charging schedules for a charger belonging to the current user."""
    rows = db.query(ChargingSchedule).filter(
        ChargingSchedule.charge_point_id == charge_point_id,
        ChargingSchedule.user_id == current_user.id,
    ).order_by(ChargingSchedule.created_at.desc()).all()
    return rows


@app.post("/api/chargers/{charge_point_id}/schedules", response_model=ChargingScheduleResponse)
async def create_charging_schedule(
    charge_point_id: str,
    payload: ChargingScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create (or replace) a charging schedule for this charger.
    Simplest UX: one schedule per user per charger — if exists, update it."""
    if not _validate_hhmm(payload.start_time) or not _validate_hhmm(payload.stop_time):
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM (24h).")

    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {charge_point_id} not found")

    # Upsert: one schedule per user per charger
    existing = db.query(ChargingSchedule).filter(
        ChargingSchedule.charge_point_id == charge_point_id,
        ChargingSchedule.user_id == current_user.id,
    ).first()

    if existing:
        existing.connector_id  = payload.connector_id
        existing.id_tag        = payload.id_tag
        existing.start_time    = payload.start_time
        existing.stop_time     = payload.stop_time
        existing.days_of_week  = payload.days_of_week
        existing.enabled       = payload.enabled
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated schedule #{existing.id} for user {current_user.id} / {charge_point_id}")
        return existing

    row = ChargingSchedule(
        user_id         = current_user.id,
        charger_id      = charger.id,
        charge_point_id = charge_point_id,
        connector_id    = payload.connector_id,
        id_tag          = payload.id_tag,
        start_time      = payload.start_time,
        stop_time       = payload.stop_time,
        days_of_week    = payload.days_of_week,
        enabled         = payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"Created schedule #{row.id} for user {current_user.id} / {charge_point_id}")
    return row


@app.patch("/api/chargers/{charge_point_id}/schedules/{schedule_id}/toggle", response_model=ChargingScheduleResponse)
async def toggle_charging_schedule(
    charge_point_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(ChargingSchedule).filter(
        ChargingSchedule.id == schedule_id,
        ChargingSchedule.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    row.enabled = not row.enabled
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/chargers/{charge_point_id}/schedules/{schedule_id}")
async def delete_charging_schedule(
    charge_point_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(ChargingSchedule).filter(
        ChargingSchedule.id == schedule_id,
        ChargingSchedule.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "Schedule deleted"}


# ==================== USER API MODELS ====================

class UserRegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    phone: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserProfileResponse(BaseModel):
    id: int
    email: str
    phone: Optional[str]
    name: str
    avatar_url: Optional[str]
    is_verified: bool
    created_at: datetime
    wallet_balance: float = 0.0
    wallet_points: int = 0
    
    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class WalletResponse(BaseModel):
    balance: float
    points: int
    currency: str


class WalletTopUpRequest(BaseModel):
    amount: float
    payment_method: str = "manual"  # manual, fpx, tng, grabpay, card


class WalletTransactionResponse(BaseModel):
    id: int
    transaction_type: str
    amount: float
    balance_before: float
    balance_after: float
    points_amount: int
    description: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class VehicleRequest(BaseModel):
    plate_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    battery_capacity_kwh: Optional[float] = None
    connector_type: Optional[str] = None
    is_primary: bool = False


class VehicleResponse(BaseModel):
    id: int
    plate_number: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    year: Optional[int]
    battery_capacity_kwh: Optional[float]
    connector_type: Optional[str]
    is_primary: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserProfileResponse] = None
    token: Optional[str] = None  # JWT access token
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None  # seconds


# ==================== OTP VERIFICATION ====================

class SendOTPRequest(BaseModel):
    email: str

class SendOTPResponse(BaseModel):
    success: bool
    message: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp_code: str

class VerifyOTPResponse(BaseModel):
    success: bool
    message: str
    verified: bool = False


@app.post("/api/auth/send-otp", response_model=SendOTPResponse)
async def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    """Send OTP verification code to email."""
    email = request.email.strip().lower()

    if not email or "@" not in email:
        return SendOTPResponse(success=False, message="Invalid email address")

    # Check if email already registered — return generic message to prevent enumeration
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return SendOTPResponse(success=True, message="Verification code sent to your email")

    try:
        # Rate limit: max 1 OTP per email per 60 seconds
        recent_otp = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email == email,
                OTPVerification.created_at > _utcnow() - timedelta(seconds=60),
            )
            .first()
        )
        if recent_otp:
            return SendOTPResponse(
                success=False,
                message="Please wait 60 seconds before requesting a new code"
            )

        # Invalidate old OTPs for this email
        db.query(OTPVerification).filter(OTPVerification.email == email).delete()

        # Generate new OTP and hash before storing
        import hashlib
        otp_code = generate_otp()
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        otp_record = OTPVerification(
            email=email,
            otp_code=otp_hash,  # store hash, not plaintext
            expires_at=_utcnow() + timedelta(minutes=5),
        )
        db.add(otp_record)
        db.commit()

        # Send email (send plaintext OTP to user, never store it)
        sent = await send_otp_email(email, otp_code)
        if not sent:
            return SendOTPResponse(
                success=False,
                message="Failed to send verification email. Please try again."
            )

        logger.info(f"📧 OTP sent to {email}")
        return SendOTPResponse(
            success=True,
            message="Verification code sent to your email"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Send OTP error: {e}", exc_info=True)
        return SendOTPResponse(success=False, message="Failed to send OTP")


@app.post("/api/auth/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Verify OTP code for email verification."""
    email = request.email.strip().lower()
    otp_code = request.otp_code.strip()

    try:
        otp_record = (
            db.query(OTPVerification)
            .filter(OTPVerification.email == email, OTPVerification.is_verified == False)
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if not otp_record:
            return VerifyOTPResponse(
                success=False, message="No OTP found. Please request a new code.", verified=False
            )

        # Check expiry
        if otp_record.is_expired():
            return VerifyOTPResponse(
                success=False, message="Code has expired. Please request a new code.", verified=False
            )

        # Check attempts (max 5)
        if otp_record.attempts >= 5:
            return VerifyOTPResponse(
                success=False, message="Too many attempts. Please request a new code.", verified=False
            )

        # Verify code — compare against stored hash
        import hashlib
        otp_record.attempts += 1
        if otp_record.otp_code != hashlib.sha256(otp_code.encode()).hexdigest():
            db.commit()
            remaining = 5 - otp_record.attempts
            return VerifyOTPResponse(
                success=False,
                message=f"Invalid code. {remaining} attempts remaining.",
                verified=False,
            )

        # Success — mark as verified
        otp_record.is_verified = True
        db.commit()

        logger.info(f"✅ OTP verified for {email}")
        return VerifyOTPResponse(
            success=True, message="Email verified successfully!", verified=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Verify OTP error: {e}", exc_info=True)
        return VerifyOTPResponse(success=False, message="Verification failed", verified=False)


# ==================== FORGOT / RESET PASSWORD ====================

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp_code: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, req: Request, db: Session = Depends(get_db)):
    """Send OTP for password reset."""
    _enforce_rate_limit(req, "forgot-password", max_requests=5, window_seconds=300)
    email = _normalize_and_validate_email(request.email)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Don't reveal whether email exists — always say "sent"
        return {"success": True, "message": "If that email is registered, a reset code has been sent."}

    try:
        otp_code = generate_otp()
        otp_record = OTPVerification(
            email=email,
            otp_code=otp_code,
            expires_at=_utcnow() + timedelta(minutes=5),
        )
        db.add(otp_record)
        db.commit()

        await send_otp_email(email, otp_code)
        logger.info(f"Password reset OTP sent to {email}")
        return {"success": True, "message": "If that email is registered, a reset code has been sent."}
    except Exception as e:
        db.rollback()
        logger.error(f"Forgot password error: {e}", exc_info=True)
        return {"success": False, "message": "Failed to send reset code"}


@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest, req: Request, db: Session = Depends(get_db)):
    """Reset password using OTP code."""
    _enforce_rate_limit(req, "reset-password", max_requests=8, window_seconds=300)
    email = _normalize_and_validate_email(request.email)
    otp_code = request.otp_code.strip()

    if len(request.new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}

    try:
        # Verify OTP
        otp_record = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email == email,
                OTPVerification.otp_code == otp_code,
                OTPVerification.is_verified == True,
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if not otp_record:
            # Also check unverified but mark as verified first (direct reset flow)
            otp_record = (
                db.query(OTPVerification)
                .filter(
                    OTPVerification.email == email,
                    OTPVerification.otp_code == otp_code,
                    OTPVerification.is_verified == False,
                    OTPVerification.expires_at > _utcnow(),
                )
                .order_by(OTPVerification.created_at.desc())
                .first()
            )
            if not otp_record:
                return {"success": False, "message": "Invalid or expired reset code"}
            otp_record.is_verified = True

        # Find user and reset password
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {"success": False, "message": "User not found"}

        user.set_password(request.new_password)
        db.commit()
        logger.info(f"Password reset for {email}")
        return {"success": True, "message": "Password has been reset successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Reset password error: {e}", exc_info=True)
        return {"success": False, "message": "Failed to reset password"}


@app.put("/api/users/{user_id}/change-password")
async def change_password(
    user_id: int,
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for authenticated user (owner only)."""
    verify_resource_owner(current_user, user_id)
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found"}

        if not user.verify_password(request.current_password):
            return {"success": False, "message": "Current password is incorrect"}

        if len(request.new_password) < 6:
            return {"success": False, "message": "New password must be at least 6 characters"}

        user.set_password(request.new_password)
        db.commit()
        logger.info(f"Password changed for user {user_id}")
        return {"success": True, "message": "Password changed successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Change password error: {e}", exc_info=True)
        return {"success": False, "message": "Failed to change password"}


# ==================== USER API ENDPOINTS ====================

class RegisterWithOTPRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    phone: Optional[str] = None
    otp_code: str


@app.post("/api/users/register", response_model=AuthResponse)
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user (legacy — no OTP required)."""
    try:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            return AuthResponse(success=False, message="Email already registered")
        
        # Check if phone already exists (if provided)
        if request.phone:
            existing_phone = db.query(User).filter(User.phone == request.phone).first()
            if existing_phone:
                return AuthResponse(success=False, message="Phone number already registered")
        
        # Create new user
        new_user = User(
            email=request.email,
            name=request.name,
            phone=request.phone
        )
        new_user.set_password(request.password)
        
        db.add(new_user)
        db.flush()  # Get the user ID
        
        # Create wallet for user
        wallet = Wallet(user_id=new_user.id, balance=0.0, points=0)
        db.add(wallet)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"New user registered: {new_user.email} (ID: {new_user.id})")
        
        # Return user profile with wallet info
        user_profile = UserProfileResponse(
            id=new_user.id,
            email=new_user.email,
            phone=new_user.phone,
            name=new_user.name,
            avatar_url=new_user.avatar_url,
            is_verified=new_user.is_verified,
            created_at=new_user.created_at,
            wallet_balance=float(wallet.balance),
            wallet_points=wallet.points
        )
        
        tokens = create_tokens(new_user)
        return AuthResponse(
            success=True,
            message="Registration successful",
            user=user_profile,
            token=tokens["access_token"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            expires_in=tokens["expires_in"],
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}", exc_info=True)
        return AuthResponse(success=False, message=f"Registration failed: {str(e)}")


@app.post("/api/users/register-with-otp", response_model=AuthResponse)
async def register_user_with_otp(request: RegisterWithOTPRequest, db: Session = Depends(get_db)):
    """Register a new user with email OTP verification."""
    email = request.email.strip().lower()
    otp_code = request.otp_code.strip()

    try:
        # 1. Verify OTP
        otp_record = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email == email,
                OTPVerification.otp_code == otp_code,
                OTPVerification.is_verified == True,
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if not otp_record:
            return AuthResponse(
                success=False,
                message="Email not verified. Please verify your email first."
            )

        # Check OTP not older than 10 minutes (grace period after verification)
        if otp_record.created_at < _utcnow() - timedelta(minutes=10):
            return AuthResponse(
                success=False,
                message="Verification expired. Please verify your email again."
            )

        # 2. Check if email already registered
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return AuthResponse(success=False, message="Email already registered")

        # Check phone
        if request.phone:
            existing_phone = db.query(User).filter(User.phone == request.phone).first()
            if existing_phone:
                return AuthResponse(success=False, message="Phone number already registered")

        # 3. Create user (verified!)
        new_user = User(
            email=email,
            name=request.name,
            phone=request.phone,
            is_verified=True,  # Email verified via OTP
        )
        new_user.set_password(request.password)

        db.add(new_user)
        db.flush()

        # Create wallet
        wallet = Wallet(user_id=new_user.id, balance=0.0, points=0)
        db.add(wallet)

        # Clean up OTP records for this email
        db.query(OTPVerification).filter(OTPVerification.email == email).delete()

        db.commit()
        db.refresh(new_user)

        logger.info(f"✅ New user registered (OTP verified): {new_user.email} (ID: {new_user.id})")

        user_profile = UserProfileResponse(
            id=new_user.id,
            email=new_user.email,
            phone=new_user.phone,
            name=new_user.name,
            avatar_url=new_user.avatar_url,
            is_verified=new_user.is_verified,
            created_at=new_user.created_at,
            wallet_balance=float(wallet.balance),
            wallet_points=wallet.points,
        )

        tokens = create_tokens(new_user)
        return AuthResponse(
            success=True,
            message="Registration successful! Email verified.",
            user=user_profile,
            token=tokens["access_token"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            expires_in=tokens["expires_in"],
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Registration (OTP) error: {e}", exc_info=True)
        return AuthResponse(success=False, message=f"Registration failed: {str(e)}")


@app.post("/api/users/login", response_model=AuthResponse)
async def login_user(request: UserLoginRequest, req: Request, db: Session = Depends(get_db)):
    """Login user — returns JWT access + refresh tokens."""
    try:
        _enforce_rate_limit(req, "user-login", max_requests=15, window_seconds=300)
        email = _normalize_and_validate_email(request.email)
        user = db.query(User).filter(User.email == email).first()
        client_ip = get_client_ip(req)
        
        if not user:
            return AuthResponse(success=False, message="Invalid email or password")
        
        # Check if account is locked
        if user.is_locked():
            audit_log("login_locked", user.id, f"Account locked, IP={client_ip}", client_ip)
            return AuthResponse(success=False, message="Account temporarily locked. Please try again in 15 minutes.")
        
        if not user.verify_password(request.password):
            user.record_failed_login()
            db.commit()
            audit_log("login_failed", user.id, f"Wrong password, IP={client_ip}", client_ip)
            return AuthResponse(success=False, message="Invalid email or password")
        
        if not user.is_active:
            return AuthResponse(success=False, message="Account is deactivated")
        
        # Successful login — reset failed attempts
        user.reset_failed_logins()
        user.last_login = _utcnow()
        db.commit()
        
        # Get wallet
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        
        # Create JWT tokens
        tokens = create_tokens(user)
        
        logger.info(f"User logged in: {user.email} (ID: {user.id})")
        audit_log("login", user.id, f"Login success, IP={client_ip}", client_ip)
        
        user_profile = UserProfileResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
            created_at=user.created_at,
            wallet_balance=float(wallet.balance) if wallet else 0.0,
            wallet_points=wallet.points if wallet else 0
        )
        
        return AuthResponse(
            success=True,
            message="Login successful",
            user=user_profile,
            token=tokens["access_token"],  # backward compat
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            expires_in=tokens["expires_in"],
        )
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return AuthResponse(success=False, message=f"Login failed: {str(e)}")


# ── Token Refresh ──
class RefreshTokenRequest(BaseModel):
    refresh_token: str


@app.post("/api/auth/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    new_access = create_access_token(user.id, user.email, user.is_admin)
    return {
        "success": True,
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": 30 * 60,
    }


@app.get("/api/users/{user_id}", response_model=AuthResponse)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user profile by ID (authenticated, owner or admin)."""
    try:
        verify_resource_owner(current_user, user_id)
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return AuthResponse(success=False, message="User not found")
        
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        
        user_profile = UserProfileResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
            created_at=user.created_at,
            wallet_balance=float(wallet.balance) if wallet else 0.0,
            wallet_points=wallet.points if wallet else 0
        )
        
        return AuthResponse(success=True, message="Profile retrieved", user=user_profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}", exc_info=True)
        return AuthResponse(success=False, message="An unexpected error occurred")


@app.put("/api/users/{user_id}", response_model=AuthResponse)
async def update_user_profile(
    user_id: int,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user profile (authenticated, owner or admin)."""
    try:
        verify_resource_owner(current_user, user_id)
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return AuthResponse(success=False, message="User not found")
        
        # Update fields if provided
        if request.name is not None:
            user.name = request.name
        if request.phone is not None:
            # Check if phone is already used by another user
            existing = db.query(User).filter(User.phone == request.phone, User.id != user_id).first()
            if existing:
                return AuthResponse(success=False, message="Phone number already in use")
            user.phone = request.phone
        if request.avatar_url is not None:
            user.avatar_url = request.avatar_url
        
        db.commit()
        db.refresh(user)
        
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        
        user_profile = UserProfileResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
            created_at=user.created_at,
            wallet_balance=float(wallet.balance) if wallet else 0.0,
            wallet_points=wallet.points if wallet else 0
        )
        
        logger.info(f"User profile updated: {user.email} (ID: {user.id})")
        return AuthResponse(success=True, message="Profile updated", user=user_profile)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update profile error: {e}", exc_info=True)
        return AuthResponse(success=False, message="An unexpected error occurred")


# ==================== WALLET API ENDPOINTS ====================

@app.get("/api/users/{user_id}/wallet", response_model=WalletResponse)
async def get_wallet(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user wallet balance (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return WalletResponse(
        balance=float(wallet.balance),
        points=wallet.points,
        currency=wallet.currency
    )


@app.post("/api/users/{user_id}/wallet/topup")
async def topup_wallet(
    user_id: int,
    request: WalletTopUpRequest,
    req: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-only manual wallet top-up (e.g. cash/bank-transfer adjustments).
    Regular users must top up via /api/payment/topup (payment gateway flow).
    """
    try:
        client_ip = get_client_ip(req)

        # Validate amount with financial safeguards
        dec_amount = validate_topup_amount(request.amount)
        validate_topup_daily_limit(db, user_id, dec_amount)

        # Row-level locking to prevent race conditions
        wallet = get_wallet_with_lock(db, user_id)
        
        balance_before = wallet.balance
        wallet.balance = Decimal(str(wallet.balance)) + dec_amount
        balance_after = wallet.balance
        
        # Create transaction record with idempotency
        transaction = WalletTransaction(
            user_id=user_id,
            wallet_id=wallet.id,
            transaction_type="topup",
            amount=dec_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            points_before=wallet.points,
            points_after=wallet.points,
            payment_method=request.payment_method,
            status="completed",
            description=f"Top-up via {request.payment_method}"
        )
        db.add(transaction)

        # Audit log
        audit_log("topup", user_id, f"RM{dec_amount} via {request.payment_method}", client_ip, float(dec_amount), db=db)

        db.commit()
        
        logger.info(f"Wallet top-up: User {user_id}, Amount RM{dec_amount}, New balance RM{wallet.balance}")
        
        return {
            "success": True,
            "message": f"Successfully topped up RM{dec_amount:.2f}",
            "new_balance": float(wallet.balance),
            "transaction_id": transaction.id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Top-up error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/users/{user_id}/wallet/transactions", response_model=List[WalletTransactionResponse])
async def get_wallet_transactions(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get wallet transaction history (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    transactions = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == user_id
    ).order_by(desc(WalletTransaction.created_at)).offset(offset).limit(limit).all()
    
    return [
        WalletTransactionResponse(
            id=t.id,
            transaction_type=t.transaction_type,
            amount=t.amount,
            balance_before=t.balance_before,
            balance_after=t.balance_after,
            points_amount=t.points_amount,
            description=t.description,
            status=t.status,
            created_at=t.created_at
        )
        for t in transactions
    ]


# ==================== REWARDS API ENDPOINTS ====================

class RedeemRewardRequest(BaseModel):
    reward_type: str  # voucher_10, free_charge, premium_membership
    points_cost: int


class RedeemRewardResponse(BaseModel):
    success: bool
    message: str
    reward_type: Optional[str] = None
    points_before: int = 0
    points_after: int = 0
    wallet_credit: Optional[float] = None


class RewardHistoryItem(BaseModel):
    id: int
    reward_type: str
    reward_title: str
    points_cost: int
    wallet_credit: Optional[float]
    status: str
    redeemed_at: datetime

    class Config:
        from_attributes = True


# Reward catalog
REWARD_CATALOG = {
    "voucher_10": {
        "title": "RM 10 Voucher",
        "description": "Get RM 10 off your next charging",
        "points_cost": 1000,
        "wallet_credit": 10.0,
        "icon": "card_giftcard",
    },
    "free_charge": {
        "title": "Free Charging Session",
        "description": "One free charging session up to 50 kWh",
        "points_cost": 2000,
        "wallet_credit": 25.0,  # RM25 equivalent credit
        "icon": "bolt",
    },
    "premium_membership": {
        "title": "Premium Membership",
        "description": "Coming soon — 1 month premium membership with discounts",
        "points_cost": 5000,
        "wallet_credit": 0.0,
        "icon": "star",
        "unavailable": True,
    },
    "voucher_5": {
        "title": "RM 5 Voucher",
        "description": "Get RM 5 off your next charging",
        "points_cost": 500,
        "wallet_credit": 5.0,
        "icon": "local_offer",
    },
    "voucher_25": {
        "title": "RM 25 Voucher",
        "description": "Get RM 25 off your next charging",
        "points_cost": 2500,
        "wallet_credit": 25.0,
        "icon": "card_giftcard",
    },
}


@app.get("/api/rewards/catalog")
async def get_reward_catalog():
    """Get available rewards catalog"""
    catalog = []
    for reward_type, info in REWARD_CATALOG.items():
        catalog.append({
            "reward_type": reward_type,
            **info,
        })
    return catalog


@app.post("/api/users/{user_id}/rewards/redeem", response_model=RedeemRewardResponse)
async def redeem_reward(
    user_id: int,
    request: RedeemRewardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Redeem a reward using points (authenticated, owner only)."""
    verify_resource_owner(current_user, user_id)
    try:
        # Validate reward type
        reward_info = REWARD_CATALOG.get(request.reward_type)
        if not reward_info:
            return RedeemRewardResponse(
                success=False, message="Invalid reward type",
                reward_type=request.reward_type
            )

        if reward_info.get("unavailable"):
            return RedeemRewardResponse(
                success=False,
                message=f"{reward_info['title']} is not yet available. Your points have not been deducted.",
                reward_type=request.reward_type,
            )

        # Validate points cost matches catalog
        expected_cost = reward_info["points_cost"]
        if request.points_cost != expected_cost:
            return RedeemRewardResponse(
                success=False,
                message=f"Points cost mismatch. Expected {expected_cost}, got {request.points_cost}",
                reward_type=request.reward_type
            )

        # Get user wallet
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            return RedeemRewardResponse(
                success=False, message="Wallet not found",
                reward_type=request.reward_type
            )

        # Check sufficient points
        if wallet.points < expected_cost:
            return RedeemRewardResponse(
                success=False,
                message=f"Insufficient points. You have {wallet.points} points but need {expected_cost}.",
                reward_type=request.reward_type,
                points_before=wallet.points,
                points_after=wallet.points,
            )

        # Deduct points
        points_before = wallet.points
        wallet.points -= expected_cost
        points_after = wallet.points

        # Credit wallet if applicable (vouchers)
        wallet_credit = reward_info.get("wallet_credit", 0.0)
        balance_before = wallet.balance
        if wallet_credit and wallet_credit > 0:
            wallet.balance = Decimal(str(wallet.balance)) + Decimal(str(wallet_credit))

        # Create transaction record
        transaction = WalletTransaction(
            user_id=user_id,
            wallet_id=wallet.id,
            transaction_type="points_redeemed",
            amount=wallet_credit if wallet_credit else 0.0,
            balance_before=balance_before,
            balance_after=wallet.balance,
            points_amount=-expected_cost,
            points_before=points_before,
            points_after=points_after,
            status="completed",
            description=f"Redeemed: {reward_info['title']}"
        )
        db.add(transaction)
        db.commit()

        logger.info(
            f"Reward redeemed: User {user_id}, {request.reward_type}, "
            f"-{expected_cost} pts, +RM{wallet_credit}"
        )

        return RedeemRewardResponse(
            success=True,
            message=f"Successfully redeemed {reward_info['title']}!",
            reward_type=request.reward_type,
            points_before=points_before,
            points_after=points_after,
            wallet_credit=wallet_credit if wallet_credit else None,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Redeem reward error: {e}", exc_info=True)
        return RedeemRewardResponse(
            success=False,
            message=f"Error redeeming reward: {str(e)}",
            reward_type=request.reward_type,
        )


@app.get("/api/users/{user_id}/rewards/history")
async def get_reward_history(
    user_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's reward redemption history (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    try:
        transactions = db.query(WalletTransaction).filter(
            WalletTransaction.user_id == user_id,
            WalletTransaction.transaction_type == "points_redeemed",
        ).order_by(desc(WalletTransaction.created_at)).limit(limit).all()

        result = []
        for t in transactions:
            # Parse reward type from description
            desc_text = t.description or ""
            reward_title = desc_text.replace("Redeemed: ", "") if desc_text.startswith("Redeemed: ") else desc_text

            # Try to find reward type from catalog
            reward_type = "unknown"
            for rtype, rinfo in REWARD_CATALOG.items():
                if rinfo["title"] == reward_title:
                    reward_type = rtype
                    break

            result.append({
                "id": t.id,
                "reward_type": reward_type,
                "reward_title": reward_title,
                "points_cost": abs(t.points_amount) if t.points_amount else 0,
                "wallet_credit": float(t.amount) if t.amount and t.amount > 0 else None,
                "status": t.status,
                "redeemed_at": t.created_at.isoformat(),
            })

        return result
    except Exception as e:
        logger.error(f"Get reward history error: {e}", exc_info=True)
        return []


# ==================== VEHICLE API ENDPOINTS ====================

@app.get("/api/users/{user_id}/vehicles", response_model=List[VehicleResponse])
async def get_user_vehicles(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's vehicles (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user_id).all()
    return vehicles


@app.post("/api/users/{user_id}/vehicles", response_model=VehicleResponse)
async def add_vehicle(
    user_id: int,
    request: VehicleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a new vehicle for user (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    try:
        # If this is set as primary, unset other primary vehicles
        if request.is_primary:
            db.query(Vehicle).filter(
                Vehicle.user_id == user_id,
                Vehicle.is_primary == True
            ).update({"is_primary": False})
        
        vehicle = Vehicle(
            user_id=user_id,
            plate_number=request.plate_number,
            brand=request.brand,
            model=request.model,
            year=request.year,
            battery_capacity_kwh=request.battery_capacity_kwh,
            connector_type=request.connector_type,
            is_primary=request.is_primary
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        
        logger.info(f"Vehicle added: User {user_id}, Plate {request.plate_number}")
        return vehicle
    except Exception as e:
        db.rollback()
        logger.error(f"Add vehicle error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/users/{user_id}/vehicles/{vehicle_id}")
async def delete_vehicle(
    user_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a vehicle (authenticated, owner or admin)."""
    verify_resource_owner(current_user, user_id)
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == user_id
    ).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    db.delete(vehicle)
    db.commit()
    
    return {"success": True, "message": "Vehicle deleted"}


# ==================== ADMIN API MODELS ====================

class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    message: str
    is_admin: bool = False
    admin_token: Optional[str] = None
    user_id: Optional[int] = None
    name: Optional[str] = None


class AdminUserResponse(BaseModel):
    id: int
    email: str
    phone: Optional[str]
    name: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    wallet_balance: float = 0.0
    wallet_points: int = 0
    
    class Config:
        from_attributes = True


class AdminUserCreateRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    phone: Optional[str] = None
    is_admin: bool = False


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None
    wallet_balance: Optional[float] = None
    wallet_points: Optional[int] = None
    new_password: Optional[str] = None


# Simple admin token storage (in production, use JWT or session)
# Format: {token: user_id}
admin_sessions = {}


def verify_admin_token(admin_token: str, db: Session) -> Optional[User]:
    """Verify admin token and return admin user if valid.

    Checks legacy admin_sessions dict AND the DB-backed staff sessions.
    """
    if not admin_token:
        return None
    
    # 1. Check legacy admin_sessions (in-memory, kept for backwards compat)
    if admin_token in admin_sessions:
        user_id = admin_sessions[admin_token]
        user = db.query(User).filter(User.id == user_id, User.is_admin == True).first()
        if user:
            return user

    # 2. Check DB-backed staff sessions (admin role)
    staff_session = _get_staff_session_db(admin_token, db)
    if staff_session and staff_session.get("role") == "admin":
        # Try to find a User account matching the staff email (admin users who log in via staff portal)
        staff_email = staff_session.get("email")
        if staff_email:
            matched_user = db.query(User).filter(User.email == staff_email, User.is_admin == True).first()
            if matched_user:
                return matched_user
        # Staff member without a matching admin User account — return first admin as fallback
        return db.query(User).filter(User.is_admin == True).first()

    return None


def get_admin_token_from_request(
    request: Request,
    admin_token: Optional[str] = Query(None),
) -> str:
    """Resolve legacy admin API token from query `admin_token` or `X-Staff-Token` header."""
    raw = (admin_token or "").strip() or (request.headers.get("X-Staff-Token") or "").strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Admin token required")
    return raw


def get_admin_token_from_request_optional(
    request: Request,
    admin_token: Optional[str] = Query(None),
) -> Optional[str]:
    raw = (admin_token or "").strip() or (request.headers.get("X-Staff-Token") or "").strip()
    return raw or None


# ==================== ADMIN API ENDPOINTS ====================

@app.post("/api/admin/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    """Admin login - only admins can access"""
    try:
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            return AdminLoginResponse(success=False, message="Invalid credentials", is_admin=False)
        
        if not user.verify_password(request.password):
            return AdminLoginResponse(success=False, message="Invalid credentials", is_admin=False)
        
        if not user.is_admin:
            return AdminLoginResponse(success=False, message="Access denied. Admin only.", is_admin=False)
        
        if not user.is_active:
            return AdminLoginResponse(success=False, message="Account is deactivated", is_admin=False)
        
        admin_token = secrets.token_hex(32)
        admin_sessions[admin_token] = user.id
        
        # Update last login
        user.last_login = _utcnow()
        db.commit()
        
        logger.info(f"Admin logged in: {user.email} (ID: {user.id})")
        
        return AdminLoginResponse(
            success=True,
            message="Admin login successful",
            is_admin=True,
            admin_token=admin_token,
            user_id=user.id,
            name=user.name
        )
    except Exception as e:
        logger.error(f"Admin login error: {e}", exc_info=True)
        return AdminLoginResponse(success=False, message="Login failed", is_admin=False)


@app.post("/api/admin/logout")
async def admin_logout(
    admin_token: Optional[str] = Depends(get_admin_token_from_request_optional),
):
    """Admin logout"""
    if admin_token and admin_token in admin_sessions:
        del admin_sessions[admin_token]
    return {"success": True, "message": "Logged out"}


@app.get("/api/admin/users", response_model=List[AdminUserResponse])
async def admin_list_users(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """List all users (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(User)
    
    # Search by email or name
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | 
            (User.name.ilike(f"%{search}%")) |
            (User.phone.ilike(f"%{search}%"))
        )
    
    users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    
    result = []
    for user in users:
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        result.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
            wallet_balance=float(wallet.balance) if wallet else 0.0,
            wallet_points=wallet.points if wallet else 0
        ))
    
    return result


@app.get("/api/admin/users/{user_id}", response_model=AdminUserResponse)
async def admin_get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Get single user details (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        name=user.name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login,
        wallet_balance=float(wallet.balance) if wallet else 0.0,
        wallet_points=wallet.points if wallet else 0
    )


@app.post("/api/admin/users", response_model=AdminUserResponse)
async def admin_create_user(
    request: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Create new user (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if email exists
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if phone exists
    if request.phone and db.query(User).filter(User.phone == request.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    try:
        user = User(
            email=request.email,
            name=request.name,
            phone=request.phone,
            is_admin=request.is_admin,
            is_verified=True  # Admin-created users are auto-verified
        )
        user.set_password(request.password)
        
        db.add(user)
        db.flush()
        
        # Create wallet
        wallet = Wallet(user_id=user.id, balance=0.0, points=0)
        db.add(wallet)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Admin created user: {user.email} (ID: {user.id}) by admin {admin.email}")
        
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
            wallet_balance=float(wallet.balance),
            wallet_points=wallet.points
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Admin create user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/admin/users/{user_id}", response_model=AdminUserResponse)
async def admin_update_user(
    user_id: int,
    request: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Update user (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Update user fields
        if request.name is not None:
            user.name = request.name
        if request.phone is not None:
            # Check if phone is used by another user
            existing = db.query(User).filter(User.phone == request.phone, User.id != user_id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Phone already in use")
            user.phone = request.phone
        if request.is_active is not None:
            user.is_active = request.is_active
        if request.is_verified is not None:
            user.is_verified = request.is_verified
        if request.is_admin is not None:
            # Prevent removing own admin status
            if user.id == admin.id and not request.is_admin:
                raise HTTPException(status_code=400, detail="Cannot remove your own admin status")
            user.is_admin = request.is_admin
        if request.new_password:
            user.set_password(request.new_password)
        
        # Update wallet if needed
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        if wallet:
            if request.wallet_balance is not None:
                wallet.balance = request.wallet_balance
            if request.wallet_points is not None:
                wallet.points = request.wallet_points
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"Admin updated user: {user.email} (ID: {user.id}) by admin {admin.email}")
        
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            name=user.name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
            wallet_balance=float(wallet.balance) if wallet else 0.0,
            wallet_points=wallet.points if wallet else 0
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Admin update user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Delete user (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Prevent self-deletion
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Delete related data
        db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id).delete()
        db.query(Wallet).filter(Wallet.user_id == user_id).delete()
        db.query(Vehicle).filter(Vehicle.user_id == user_id).delete()
        
        # Delete user
        db.delete(user)
        db.commit()
        
        logger.info(f"Admin deleted user: {user.email} (ID: {user.id}) by admin {admin.email}")
        
        return {"success": True, "message": f"User {user.email} deleted"}
    except Exception as e:
        db.rollback()
        logger.error(f"Admin delete user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/admin/stats")
async def admin_get_stats(
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Get dashboard statistics (admin only)"""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.is_admin == True).count()
    
    total_balance = float(db.query(func.sum(Wallet.balance)).scalar() or 0)
    
    # Recent registrations (last 7 days)
    week_ago = _utcnow() - timedelta(days=7)
    recent_registrations = db.query(User).filter(User.created_at >= week_ago).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "total_wallet_balance": round(total_balance, 2),
        "recent_registrations": recent_registrations
    }


@app.get("/api/admin/reports/users")
async def admin_user_report(
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Detailed user analytics report."""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    total = db.query(User).count()
    active = db.query(User).filter(User.is_active == True).count()
    verified = db.query(User).filter(User.is_verified == True).count()
    admins = db.query(User).filter(User.is_admin == True).count()
    inactive = total - active
    unverified = total - verified

    # Registration trend (last 30 days, grouped by day)
    now = _utcnow()
    trend = []
    for i in range(29, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(User).filter(User.created_at >= day_start, User.created_at < day_end).count()
        trend.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})

    # Recent logins (last 7 days)
    week_ago = now - timedelta(days=7)
    recent_logins = db.query(User).filter(User.last_login >= week_ago).count()
    never_logged_in = db.query(User).filter(User.last_login == None).count()

    # Top 10 newest users
    newest = db.query(User).order_by(desc(User.created_at)).limit(10).all()
    newest_list = [{"id": u.id, "name": u.name or "N/A", "email": u.email, "created_at": u.created_at.isoformat() if u.created_at else None} for u in newest]

    return {
        "totals": {"total": total, "active": active, "inactive": inactive, "verified": verified, "unverified": unverified, "admins": admins},
        "registration_trend": trend,
        "login_stats": {"recent_logins_7d": recent_logins, "never_logged_in": never_logged_in},
        "newest_users": newest_list,
    }


@app.get("/api/admin/reports/wallet")
async def admin_wallet_report(
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Detailed wallet/financial report."""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    total_balance = float(db.query(func.sum(Wallet.balance)).scalar() or 0)
    total_points = int(db.query(func.sum(Wallet.points)).scalar() or 0)
    wallet_count = db.query(Wallet).count()
    avg_balance = round(float(total_balance) / max(wallet_count, 1), 2)

    # Top 10 wallet holders
    top_wallets = db.query(User, Wallet).join(Wallet, Wallet.user_id == User.id).order_by(desc(Wallet.balance)).limit(10).all()
    top_list = [{"name": u.name or u.email, "email": u.email, "balance": float(round(w.balance, 2)), "points": w.points} for u, w in top_wallets]

    # Recent transactions (last 20)
    from database import WalletTransaction
    recent_txns = db.query(WalletTransaction).order_by(desc(WalletTransaction.created_at)).limit(20).all()
    txn_list = []
    for t in recent_txns:
        user = db.query(User).filter(User.id == t.user_id).first()
        txn_list.append({
            "id": t.id,
            "user": user.name or user.email if user else "Unknown",
            "type": t.transaction_type,
            "amount": float(round(t.amount, 2)),
            "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    # Balance distribution
    zero = db.query(Wallet).filter(Wallet.balance == 0).count()
    low = db.query(Wallet).filter(Wallet.balance > 0, Wallet.balance <= 10).count()
    mid = db.query(Wallet).filter(Wallet.balance > 10, Wallet.balance <= 50).count()
    high = db.query(Wallet).filter(Wallet.balance > 50, Wallet.balance <= 100).count()
    premium = db.query(Wallet).filter(Wallet.balance > 100).count()

    return {
        "summary": {"total_balance": round(total_balance, 2), "total_points": total_points, "wallet_count": wallet_count, "avg_balance": avg_balance},
        "top_wallets": top_list,
        "recent_transactions": txn_list,
        "distribution": {"zero": zero, "low_1_10": low, "mid_10_50": mid, "high_50_100": high, "premium_100_plus": premium},
    }


@app.get("/api/admin/reports/activity")
async def admin_activity_report(
    db: Session = Depends(get_db),
    admin_token: str = Depends(get_admin_token_from_request),
):
    """Activity/audit log — recent system events."""
    admin = verify_admin_token(admin_token, db)
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    events = []

    # Recent registrations (last 20)
    recent_users = db.query(User).order_by(desc(User.created_at)).limit(20).all()
    for u in recent_users:
        events.append({"time": u.created_at.isoformat() if u.created_at else None, "type": "registration", "icon": "👤", "desc": f"New user registered: {u.name or u.email}", "detail": u.email})

    # Recent logins (last 20)
    recent_logins = db.query(User).filter(User.last_login != None).order_by(desc(User.last_login)).limit(20).all()
    for u in recent_logins:
        events.append({"time": u.last_login.isoformat() if u.last_login else None, "type": "login", "icon": "🔑", "desc": f"User logged in: {u.name or u.email}", "detail": u.email})

    # Recent charging sessions (last 20)
    recent_sessions = db.query(ChargingSession).order_by(desc(ChargingSession.start_time)).limit(20).all()
    for s in recent_sessions:
        charger = db.query(Charger).filter(Charger.id == s.charger_id).first()
        cp_id = charger.charge_point_id if charger else "Unknown"
        events.append({"time": s.start_time.isoformat() if s.start_time else None, "type": "session", "icon": "⚡", "desc": f"Charging session on {cp_id}", "detail": f"Status: {s.status}, Energy: {round(s.energy_consumed or 0, 2)} kWh"})

    # Recent tickets (last 20)
    recent_tickets = db.query(SupportTicket).order_by(desc(SupportTicket.created_at)).limit(20).all()
    for t in recent_tickets:
        events.append({"time": t.created_at.isoformat() if t.created_at else None, "type": "ticket", "icon": "🎫", "desc": f"Ticket {t.ticket_number}: {t.subject}", "detail": f"By {t.user_email} — {t.status}"})

    # Recent maintenance (last 20)
    recent_maint = db.query(MaintenanceRecord).order_by(desc(MaintenanceRecord.date_reported)).limit(20).all()
    for m in recent_maint:
        charger = db.query(Charger).filter(Charger.id == m.charger_id).first()
        cp_id = charger.charge_point_id if charger else "Unknown"
        events.append({"time": m.date_reported.isoformat() if m.date_reported else None, "type": "maintenance", "icon": "🔧", "desc": f"Maintenance on {cp_id}: {m.issue_description[:60] if m.issue_description else 'N/A'}", "detail": f"Status: {m.status}, Cost: RM {float(round(m.cost or 0, 2)):.2f}"})

    # Recent staff logins
    staff_list = db.query(SupportStaff).filter(SupportStaff.last_login != None).order_by(desc(SupportStaff.last_login)).limit(10).all()
    for s in staff_list:
        events.append({"time": s.last_login.isoformat() if s.last_login else None, "type": "staff_login", "icon": "🏢", "desc": f"Staff login: {s.name}", "detail": f"{s.department} — {s.role}"})

    # Sort all events by time (descending)
    events.sort(key=lambda e: e["time"] or "", reverse=True)

    return {"events": events[:100]}


# Serve admin page
@app.get("/admin")
async def admin_page():
    """Serve the admin dashboard"""
    try:
        file_path = Path("templates/admin.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Admin template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading admin page: {str(e)}")


# ==================== MAINTENANCE API ====================

@app.get("/maintenance")
async def maintenance_page():
    """Serve the maintenance page"""
    try:
        file_path = Path("templates/maintenance.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Maintenance template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading maintenance page: {str(e)}")


@app.get("/api/maintenance", response_model=List[MaintenanceResponse])
async def get_all_maintenance(
    charger_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _auth: dict = Depends(require_admin_or_staff_admin),
):
    """Get all maintenance records, optionally filtered by charger or status"""
    query = db.query(MaintenanceRecord)
    
    if charger_id:
        charger = db.query(Charger).filter(Charger.charge_point_id == charger_id).first()
        if charger:
            query = query.filter(MaintenanceRecord.charger_id == charger.id)
    
    if status:
        query = query.filter(MaintenanceRecord.status == status)
    
    records = query.order_by(desc(MaintenanceRecord.date_reported)).all()
    
    result = []
    for record in records:
        charger = db.query(Charger).filter(Charger.id == record.charger_id).first()
        result.append(MaintenanceResponse(
            id=record.id,
            charger_id=record.charger_id,
            charge_point_id=charger.charge_point_id if charger else "Unknown",
            maintenance_type=record.maintenance_type,
            issue_description=record.issue_description,
            work_performed=record.work_performed,
            parts_replaced=record.parts_replaced,
            cost=record.cost,
            technician_name=record.technician_name,
            status=record.status,
            date_reported=record.date_reported,
            date_scheduled=record.date_scheduled,
            date_completed=record.date_completed,
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at
        ))
    
    return result


@app.get("/api/maintenance/{record_id}", response_model=MaintenanceResponse)
async def get_maintenance_record(record_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Get a specific maintenance record"""
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    charger = db.query(Charger).filter(Charger.id == record.charger_id).first()
    
    return MaintenanceResponse(
        id=record.id,
        charger_id=record.charger_id,
        charge_point_id=charger.charge_point_id if charger else "Unknown",
        maintenance_type=record.maintenance_type,
        issue_description=record.issue_description,
        work_performed=record.work_performed,
        parts_replaced=record.parts_replaced,
        cost=record.cost,
        technician_name=record.technician_name,
        status=record.status,
        date_reported=record.date_reported,
        date_scheduled=record.date_scheduled,
        date_completed=record.date_completed,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at
    )


@app.post("/api/maintenance", response_model=MaintenanceResponse)
async def create_maintenance_record(data: MaintenanceCreate, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Create a new maintenance record"""
    # Find charger by charge_point_id
    charger = db.query(Charger).filter(Charger.charge_point_id == data.charger_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {data.charger_id} not found")
    
    record = MaintenanceRecord(
        charger_id=charger.id,
        maintenance_type=data.maintenance_type,
        issue_description=data.issue_description,
        work_performed=data.work_performed,
        parts_replaced=data.parts_replaced,
        cost=data.cost,
        technician_name=data.technician_name,
        status=data.status,
        date_scheduled=data.date_scheduled,
        date_completed=data.date_completed or (_utcnow() if data.status == "completed" else None),
        notes=data.notes
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return MaintenanceResponse(
        id=record.id,
        charger_id=record.charger_id,
        charge_point_id=charger.charge_point_id,
        maintenance_type=record.maintenance_type,
        issue_description=record.issue_description,
        work_performed=record.work_performed,
        parts_replaced=record.parts_replaced,
        cost=record.cost,
        technician_name=record.technician_name,
        status=record.status,
        date_reported=record.date_reported,
        date_scheduled=record.date_scheduled,
        date_completed=record.date_completed,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at
    )


@app.put("/api/maintenance/{record_id}", response_model=MaintenanceResponse)
async def update_maintenance_record(record_id: int, data: MaintenanceUpdate, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Update a maintenance record"""
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    # Update fields if provided
    if data.maintenance_type is not None:
        record.maintenance_type = data.maintenance_type
    if data.issue_description is not None:
        record.issue_description = data.issue_description
    if data.work_performed is not None:
        record.work_performed = data.work_performed
    if data.parts_replaced is not None:
        record.parts_replaced = data.parts_replaced
    if data.cost is not None:
        record.cost = data.cost
    if data.technician_name is not None:
        record.technician_name = data.technician_name
    if data.status is not None:
        record.status = data.status
        # Auto-set date_completed when status changes to completed
        if data.status == "completed" and not record.date_completed:
            record.date_completed = _utcnow()
    if data.date_scheduled is not None:
        record.date_scheduled = data.date_scheduled
    if data.date_completed is not None:
        record.date_completed = data.date_completed
    if data.notes is not None:
        record.notes = data.notes
    
    db.commit()
    db.refresh(record)
    
    charger = db.query(Charger).filter(Charger.id == record.charger_id).first()
    
    return MaintenanceResponse(
        id=record.id,
        charger_id=record.charger_id,
        charge_point_id=charger.charge_point_id if charger else "Unknown",
        maintenance_type=record.maintenance_type,
        issue_description=record.issue_description,
        work_performed=record.work_performed,
        parts_replaced=record.parts_replaced,
        cost=record.cost,
        technician_name=record.technician_name,
        status=record.status,
        date_reported=record.date_reported,
        date_scheduled=record.date_scheduled,
        date_completed=record.date_completed,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at
    )


@app.delete("/api/maintenance/{record_id}")
async def delete_maintenance_record(record_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Delete a maintenance record"""
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    db.delete(record)
    db.commit()
    
    return {"success": True, "message": "Maintenance record deleted"}


# ==================== INVOICE / REPORT API ====================

@app.get("/invoice")
async def invoice_page():
    """Serve the invoice/report page"""
    try:
        file_path = Path("templates/invoice.html")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Invoice template not found")
        return FileResponse(file_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading invoice page: {str(e)}")


@app.get("/api/invoice/summary")
async def get_invoice_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    charger_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_or_staff_admin),
):
    """Get invoice summary with totals (admin/staff only)"""
    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    # Build query
    query = db.query(ChargingSession)
    
    if charger_id:
        charger = db.query(Charger).filter(Charger.charge_point_id == charger_id).first()
        if charger:
            query = query.filter(ChargingSession.charger_id == charger.id)
    
    if start_dt:
        query = query.filter(ChargingSession.start_time >= start_dt)
    if end_dt:
        query = query.filter(ChargingSession.start_time <= end_dt)
    
    sessions = query.all()
    
    # Calculate totals
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s.status == 'completed'])
    active_sessions = len([s for s in sessions if s.status == 'active'])
    total_energy = float(sum(s.energy_consumed or 0 for s in sessions))
    
    # Get pricing (use default if not set)
    pricing = db.query(Pricing).filter(Pricing.is_active == True).first()
    price_per_kwh = float(pricing.price_per_kwh) if pricing else 0.50  # Default RM 0.50/kWh
    
    total_revenue = total_energy * price_per_kwh
    
    # Calculate total duration
    total_duration_minutes = 0
    for s in sessions:
        if s.start_time and s.stop_time:
            duration = (s.stop_time - s.start_time).total_seconds() / 60
            total_duration_minutes += duration
    
    # Get charger breakdown
    charger_breakdown = {}
    for s in sessions:
        charger = db.query(Charger).filter(Charger.id == s.charger_id).first()
        if charger:
            cp_id = charger.charge_point_id
            if cp_id not in charger_breakdown:
                charger_breakdown[cp_id] = {
                    "sessions": 0,
                    "energy_kwh": 0,
                    "revenue": 0,
                    "duration_minutes": 0
                }
            charger_breakdown[cp_id]["sessions"] += 1
            charger_breakdown[cp_id]["energy_kwh"] += s.energy_consumed or 0
            charger_breakdown[cp_id]["revenue"] += (s.energy_consumed or 0) * price_per_kwh
            if s.start_time and s.stop_time:
                charger_breakdown[cp_id]["duration_minutes"] += (s.stop_time - s.start_time).total_seconds() / 60
    
    # Round values and ensure float (not Decimal)
    for cp_id in charger_breakdown:
        charger_breakdown[cp_id]["energy_kwh"] = float(round(charger_breakdown[cp_id]["energy_kwh"], 2))
        charger_breakdown[cp_id]["revenue"] = float(round(charger_breakdown[cp_id]["revenue"], 2))
        charger_breakdown[cp_id]["duration_minutes"] = float(round(charger_breakdown[cp_id]["duration_minutes"], 1))
    
    # Get maintenance costs in period
    maintenance_query = db.query(MaintenanceRecord)
    if start_dt:
        maintenance_query = maintenance_query.filter(MaintenanceRecord.date_reported >= start_dt)
    if end_dt:
        maintenance_query = maintenance_query.filter(MaintenanceRecord.date_reported <= end_dt)
    
    maintenance_records = maintenance_query.all()
    total_maintenance_cost = float(sum(float(m.cost or 0) for m in maintenance_records))
    
    return {
        "period": {
            "start": start_date or "All time",
            "end": end_date or "Present"
        },
        "sessions": {
            "total": total_sessions,
            "completed": completed_sessions,
            "active": active_sessions
        },
        "energy": {
            "total_kwh": float(round(total_energy, 2)),
            "price_per_kwh": float(price_per_kwh)
        },
        "revenue": {
            "total": float(round(total_revenue, 2)),
            "currency": "MYR"
        },
        "duration": {
            "total_minutes": round(total_duration_minutes, 1),
            "total_hours": round(total_duration_minutes / 60, 2)
        },
        "maintenance": {
            "total_records": len(maintenance_records),
            "total_cost": float(round(total_maintenance_cost, 2))
        },
        "net_profit": float(round(total_revenue - total_maintenance_cost, 2)),
        "charger_breakdown": charger_breakdown
    }


@app.get("/api/invoice/sessions")
async def get_invoice_sessions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    charger_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_or_staff_admin),
):
    """Get detailed session list for invoice (admin/staff only)"""
    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    # Build query
    query = db.query(ChargingSession)
    
    if charger_id:
        charger = db.query(Charger).filter(Charger.charge_point_id == charger_id).first()
        if charger:
            query = query.filter(ChargingSession.charger_id == charger.id)
    
    if start_dt:
        query = query.filter(ChargingSession.start_time >= start_dt)
    if end_dt:
        query = query.filter(ChargingSession.start_time <= end_dt)
    
    sessions = query.order_by(desc(ChargingSession.start_time)).all()
    
    # Get pricing
    pricing = db.query(Pricing).filter(Pricing.is_active == True).first()
    price_per_kwh = float(pricing.price_per_kwh) if pricing else 0.50
    
    result = []
    for s in sessions:
        charger = db.query(Charger).filter(Charger.id == s.charger_id).first()
        
        duration_minutes = 0
        if s.start_time and s.stop_time:
            duration_minutes = (s.stop_time - s.start_time).total_seconds() / 60
        
        amount = float(s.energy_consumed or 0) * price_per_kwh
        
        result.append({
            "id": s.id,
            "transaction_id": s.transaction_id,
            "charge_point_id": charger.charge_point_id if charger else "Unknown",
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "stop_time": s.stop_time.isoformat() if s.stop_time else None,
            "duration_minutes": round(duration_minutes, 1),
            "energy_kwh": float(round(s.energy_consumed or 0, 2)),
            "price_per_kwh": float(price_per_kwh),
            "amount": float(round(amount, 2)),
            "status": s.status,
            "user_id": s.user_id
        })
    
    return result


# ============================================================
#  SUPPORT TICKET  APIs
# ============================================================

class CreateTicketRequest(BaseModel):
    user_email: str
    user_name: Optional[str] = None
    user_id: Optional[int] = None
    category: str
    subject: str
    description: str
    priority: str = "medium"
    source: str = "chatbot"


class TicketMessageRequest(BaseModel):
    sender_type: str  # "user" | "admin" | "system"
    sender_name: Optional[str] = None
    message: str


class UpdateTicketRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    resolution_notes: Optional[str] = None


def _auto_assign_staff(db: Session, category: str, priority: str) -> Optional[SupportStaff]:
    """Auto-assign ticket to least-loaded active staff in the matching department."""
    department = CATEGORY_DEPARTMENT_MAP.get(category, "Customer Service")

    # Get active staff in the matching department only (don't assign to admins — they oversee)
    candidates = (
        db.query(SupportStaff)
        .filter(
            SupportStaff.is_active == True,
            SupportStaff.department == department,
            SupportStaff.role.in_(["manager", "staff"]),
        )
        .all()
    )
    if not candidates:
        return None

    # For urgent/high priority → prefer managers first
    if priority in ("urgent", "high"):
        managers = [s for s in candidates if s.role == "manager"]
        if managers:
            candidates = managers

    # Pick the one with the fewest open tickets (least-loaded)
    best = None
    best_count = 999999
    for staff in candidates:
        open_count = (
            db.query(SupportTicket)
            .filter(
                SupportTicket.assigned_staff_id == staff.id,
                SupportTicket.status.in_(["open", "in_progress"]),
            )
            .count()
        )
        if open_count < staff.max_tickets and open_count < best_count:
            best = staff
            best_count = open_count

    return best


def _generate_ticket_number(db: Session) -> str:
    """Generate a unique ticket number like TKT-20260215-0001."""
    today = _utcnow().strftime("%Y%m%d")
    prefix = f"TKT-{today}-"
    last = (
        db.query(SupportTicket)
        .filter(SupportTicket.ticket_number.like(f"{prefix}%"))
        .order_by(desc(SupportTicket.id))
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.ticket_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


@app.post("/api/tickets")
async def create_ticket(req: CreateTicketRequest, db: Session = Depends(get_db)):
    """Create a new support ticket and send confirmation email."""
    ticket_number = _generate_ticket_number(db)

    # Determine department from category
    department = CATEGORY_DEPARTMENT_MAP.get(req.category, "Customer Service")

    # Calculate SLA deadline
    sla_hours = TICKET_SLA_HOURS.get(req.priority, 24)
    due_at = _utcnow() + timedelta(hours=sla_hours)

    ticket = SupportTicket(
        ticket_number=ticket_number,
        user_id=req.user_id,
        user_email=req.user_email,
        user_name=req.user_name,
        category=req.category,
        subject=req.subject,
        description=req.description,
        priority=req.priority,
        department=department,
        source=req.source,
        due_at=due_at,
    )
    db.add(ticket)
    db.flush()

    # Auto-assign to staff
    staff = _auto_assign_staff(db, req.category, req.priority)
    if staff:
        ticket.assigned_staff_id = staff.id
        ticket.assigned_to = staff.name
        logger.info(f"Ticket {ticket_number} auto-assigned to {staff.name} ({staff.department})")

    # First message = user description
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type="user",
        sender_name=req.user_name or req.user_email,
        message=req.description,
    )
    db.add(msg)

    # System message about assignment
    assign_note = f"Assigned to {staff.name} ({staff.department})" if staff else f"Routed to {department} department (no staff available)"
    sys_msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type="system",
        sender_name="System",
        message=f"Ticket created. Department: {department}, Priority: {req.priority.upper()}. {assign_note}",
    )
    db.add(sys_msg)

    db.commit()
    db.refresh(ticket)

    # Auto email confirmation
    try:
        await send_ticket_confirmation(req.user_email, ticket_number, req.subject, req.category)
    except Exception as e:
        logger.warning(f"Failed to send ticket confirmation email: {e}")

    return {
        "success": True,
        "ticket_number": ticket_number,
        "ticket_id": ticket.id,
        "department": department,
        "assigned_to": ticket.assigned_to,
        "message": f"Ticket {ticket_number} created successfully",
    }


@app.get("/api/tickets")
async def list_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    department: Optional[str] = None,
    staff_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _auth: dict = Depends(require_admin_or_staff_admin),
):
    """List support tickets. Supports filtering by staff/department for hierarchy."""
    q = db.query(SupportTicket)
    if status:
        q = q.filter(SupportTicket.status == status)
    if category:
        q = q.filter(SupportTicket.category == category)
    if priority:
        q = q.filter(SupportTicket.priority == priority)
    if department:
        q = q.filter(SupportTicket.department == department)
    if staff_id:
        q = q.filter(SupportTicket.assigned_staff_id == staff_id)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(
                SupportTicket.ticket_number.like(pattern),
                SupportTicket.user_email.like(pattern),
                SupportTicket.user_name.like(pattern),
                SupportTicket.subject.like(pattern),
            )
        )

    total = q.count()
    tickets = q.order_by(desc(SupportTicket.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "user_email": t.user_email,
                "user_name": t.user_name,
                "user_id": t.user_id,
                "category": t.category,
                "subject": t.subject,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "department": t.department,
                "assigned_to": t.assigned_to,
                "assigned_staff_id": t.assigned_staff_id,
                "source": t.source,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "escalated": t.escalated or False,
                "is_overdue": (t.due_at is not None and _utcnow() > t.due_at and t.status not in ("resolved", "closed")),
                "message_count": len(t.messages),
            }
            for t in tickets
        ],
    }


@app.get("/api/tickets/stats")
async def ticket_stats(
    db: Session = Depends(get_db),
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
):
    """Get ticket statistics for admin dashboard."""
    total = db.query(SupportTicket).count()
    open_count = db.query(SupportTicket).filter(SupportTicket.status == "open").count()
    in_progress = db.query(SupportTicket).filter(SupportTicket.status == "in_progress").count()
    resolved = db.query(SupportTicket).filter(SupportTicket.status == "resolved").count()
    closed = db.query(SupportTicket).filter(SupportTicket.status == "closed").count()

    # By category
    categories = (
        db.query(SupportTicket.category, func.count(SupportTicket.id))
        .group_by(SupportTicket.category)
        .all()
    )
    # By priority
    priorities = (
        db.query(SupportTicket.priority, func.count(SupportTicket.id))
        .group_by(SupportTicket.priority)
        .all()
    )

    # Overdue count
    now = _utcnow()
    overdue_count = db.query(SupportTicket).filter(
        SupportTicket.due_at.isnot(None),
        SupportTicket.due_at < now,
        SupportTicket.status.notin_(["resolved", "closed"]),
    ).count()

    # Warning count (due within next 2 hours)
    warning_deadline = now + timedelta(hours=2)
    warning_count = db.query(SupportTicket).filter(
        SupportTicket.due_at.isnot(None),
        SupportTicket.due_at >= now,
        SupportTicket.due_at <= warning_deadline,
        SupportTicket.status.notin_(["resolved", "closed"]),
    ).count()

    return {
        "total": total,
        "open": open_count,
        "in_progress": in_progress,
        "resolved": resolved,
        "closed": closed,
        "overdue": overdue_count,
        "warning": warning_count,
        "by_category": {c: n for c, n in categories},
        "by_priority": {p: n for p, n in priorities},
        "sla_hours": TICKET_SLA_HOURS,
    }


@app.get("/api/tickets/overdue")
async def get_overdue_tickets(db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Get all overdue and soon-due tickets for reminder dashboard."""
    now = _utcnow()
    warning_deadline = now + timedelta(hours=2)

    # Overdue tickets
    overdue = db.query(SupportTicket).filter(
        SupportTicket.due_at.isnot(None),
        SupportTicket.due_at < now,
        SupportTicket.status.notin_(["resolved", "closed"]),
    ).order_by(SupportTicket.due_at.asc()).all()

    # Warning tickets (approaching deadline)
    warning = db.query(SupportTicket).filter(
        SupportTicket.due_at.isnot(None),
        SupportTicket.due_at >= now,
        SupportTicket.due_at <= warning_deadline,
        SupportTicket.status.notin_(["resolved", "closed"]),
    ).order_by(SupportTicket.due_at.asc()).all()

    def _serialize(t):
        time_left = (t.due_at - now).total_seconds() if t.due_at else 0
        return {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "subject": t.subject,
            "priority": t.priority,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "department": t.department,
            "user_email": t.user_email,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "time_left_seconds": time_left,
            "time_left_human": _humanize_seconds(time_left),
            "escalated": t.escalated or False,
        }

    return {
        "overdue_count": len(overdue),
        "warning_count": len(warning),
        "overdue": [_serialize(t) for t in overdue],
        "warning": [_serialize(t) for t in warning],
    }


def _humanize_seconds(seconds: float) -> str:
    """Convert seconds to human-readable time string."""
    if seconds <= 0:
        abs_s = abs(seconds)
        if abs_s < 3600:
            return f"{int(abs_s // 60)}m overdue"
        elif abs_s < 86400:
            return f"{int(abs_s // 3600)}h {int((abs_s % 3600) // 60)}m overdue"
        else:
            return f"{int(abs_s // 86400)}d {int((abs_s % 86400) // 3600)}h overdue"
    else:
        if seconds < 3600:
            return f"{int(seconds // 60)}m left"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m left"
        else:
            return f"{int(seconds // 86400)}d {int((seconds % 86400) // 3600)}h left"


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Get a single ticket with its messages."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "user_email": ticket.user_email,
        "user_name": ticket.user_name,
        "user_id": ticket.user_id,
        "category": ticket.category,
        "subject": ticket.subject,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status,
        "department": ticket.department,
        "assigned_to": ticket.assigned_to,
        "assigned_staff_id": ticket.assigned_staff_id,
        "source": ticket.source,
        "resolution_notes": ticket.resolution_notes,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "due_at": ticket.due_at.isoformat() if ticket.due_at else None,
        "escalated": ticket.escalated or False,
        "is_overdue": (ticket.due_at is not None and _utcnow() > ticket.due_at and ticket.status not in ("resolved", "closed")),
        "sla_hours": TICKET_SLA_HOURS.get(ticket.priority, 24),
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "message": m.message,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in ticket.messages
        ],
    }


@app.put("/api/tickets/{ticket_id}")
async def update_ticket(ticket_id: int, req: UpdateTicketRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Update a ticket (status, priority, assignment, etc.)."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status
    if req.status is not None:
        ticket.status = req.status
        if req.status in ("resolved", "closed") and not ticket.resolved_at:
            ticket.resolved_at = _utcnow()
    if req.priority is not None:
        ticket.priority = req.priority
        # Recalculate SLA deadline based on new priority
        sla_hours = TICKET_SLA_HOURS.get(req.priority, 24)
        ticket.due_at = ticket.created_at + timedelta(hours=sla_hours) if ticket.created_at else _utcnow() + timedelta(hours=sla_hours)
    if req.assigned_staff_id is not None:
        staff = db.query(SupportStaff).filter(SupportStaff.id == req.assigned_staff_id).first()
        if staff:
            ticket.assigned_staff_id = staff.id
            ticket.assigned_to = staff.name
    elif req.assigned_to is not None:
        ticket.assigned_to = req.assigned_to
    if req.resolution_notes is not None:
        ticket.resolution_notes = req.resolution_notes

    ticket.updated_at = _utcnow()
    db.commit()

    # Email user on status change
    if req.status and req.status != old_status:
        try:
            await send_ticket_update(ticket.user_email, ticket.ticket_number, ticket.subject, req.status)
        except Exception as e:
            logger.warning(f"Failed to send ticket update email: {e}")

    return {"success": True, "message": "Ticket updated"}


@app.post("/api/tickets/{ticket_id}/messages")
async def add_ticket_message(ticket_id: int, req: TicketMessageRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Add a message to a ticket thread."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = TicketMessage(
        ticket_id=ticket_id,
        sender_type=req.sender_type,
        sender_name=req.sender_name,
        message=req.message,
    )
    db.add(msg)

    # If admin replies for the first time, record first response time
    if req.sender_type == "admin" and not ticket.first_response_at:
        ticket.first_response_at = _utcnow()
    if req.sender_type == "admin" and ticket.status == "open":
        ticket.status = "in_progress"

    ticket.updated_at = _utcnow()
    db.commit()

    # Notify user by email when admin replies
    if req.sender_type == "admin":
        try:
            await send_ticket_update(
                ticket.user_email,
                ticket.ticket_number,
                ticket.subject,
                "admin_reply",
            )
        except Exception as e:
            logger.warning(f"Failed to send admin reply notification: {e}")

    return {"success": True, "message_id": msg.id}


# ============================================================
#  STAFF MANAGEMENT APIs
# ============================================================

class CreateStaffRequest(BaseModel):
    name: str
    email: str
    password: str
    department: str
    role: str = "staff"
    max_tickets: int = 10


class UpdateStaffRequest(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    max_tickets: Optional[int] = None
    new_password: Optional[str] = None


class StaffLoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/staff/login")
async def staff_login(req: StaffLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Staff login — accepts SupportStaff accounts OR admin User accounts (is_admin=True)."""
    _enforce_rate_limit(request, "staff-login", max_requests=12, window_seconds=300)
    email = _normalize_and_validate_email(req.email)

    # 1. Try SupportStaff table first
    staff = db.query(SupportStaff).filter(SupportStaff.email == email).first()
    if staff and staff.check_password(req.password):
        if not staff.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
    else:
        # 2. Fallback: check User table for is_admin=True (unified admin login)
        admin_user = db.query(User).filter(User.email == email, User.is_admin == True).first()
        if not admin_user or not admin_user.verify_password(req.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not admin_user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        # Auto-create or sync a SupportStaff record for this admin User
        staff = db.query(SupportStaff).filter(SupportStaff.email == email).first()
        if not staff:
            staff = SupportStaff(
                name=admin_user.name or "Admin",
                email=admin_user.email,
                department="Management",
                role="admin",
                is_active=True,
            )
            staff.set_password(req.password)
            db.add(staff)
            db.flush()
        elif not staff.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

    staff.last_login = _utcnow()

    token = secrets.token_hex(32)
    expires = _utcnow() + timedelta(days=_STAFF_SESSION_TTL_DAYS)
    db.add(StaffSession(staff_id=staff.id, token=token, expires_at=expires))
    db.commit()

    staff_info = {
        "id": staff.id,
        "name": staff.name,
        "email": staff.email,
        "department": staff.department,
        "role": staff.role,
    }
    return {"success": True, "token": token, "staff": staff_info}


@app.post("/api/staff/logout")
async def staff_logout(body: dict, db: Session = Depends(get_db)):
    token = body.get("token")
    if token:
        db.query(StaffSession).filter(StaffSession.token == token).delete()
        db.commit()
    return {"success": True}


@app.get("/api/staff/me")
async def staff_me(token: str, db: Session = Depends(get_db)):
    """Get current staff info from token."""
    session = _get_staff_session_db(token, db)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"success": True, "staff": session}


@app.get("/api/staff/my-tickets")
async def staff_my_tickets(
    token: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get tickets visible to the current staff based on their role."""
    session = _get_staff_session_db(token, db)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    q = db.query(SupportTicket)

    role = session["role"]
    if role == "manager":
        # manager sees all tickets in their department (view only)
        q = q.filter(SupportTicket.department == session["department"])
    elif role != "admin":
        # staff sees only their own assigned tickets
        q = q.filter(SupportTicket.assigned_staff_id == session["id"])

    if status:
        q = q.filter(SupportTicket.status == status)
    if priority:
        q = q.filter(SupportTicket.priority == priority)

    tickets = q.order_by(desc(SupportTicket.created_at)).limit(100).all()

    return {
        "total": len(tickets),
        "role": role,
        "department": session["department"],
        "tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "user_email": t.user_email,
                "user_name": t.user_name,
                "category": t.category,
                "subject": t.subject,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "department": t.department,
                "assigned_to": t.assigned_to,
                "assigned_staff_id": t.assigned_staff_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "escalated": t.escalated or False,
                "is_overdue": (t.due_at is not None and _utcnow() > t.due_at and t.status not in ("resolved", "closed")),
                "message_count": len(t.messages),
            }
            for t in tickets
        ],
    }


# ─── Staff CRUD (admin only) ───

@app.post("/api/staff")
async def create_staff(req: CreateStaffRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Create a new support staff member."""
    if req.department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid department. Must be one of: {DEPARTMENTS}")
    if req.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {STAFF_ROLES}")

    existing = db.query(SupportStaff).filter(SupportStaff.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered as staff")

    staff = SupportStaff(
        name=req.name,
        email=req.email,
        department=req.department,
        role=req.role,
        max_tickets=req.max_tickets,
    )
    staff.set_password(req.password)
    db.add(staff)
    db.commit()
    db.refresh(staff)

    return {
        "success": True,
        "staff_id": staff.id,
        "message": f"Staff {staff.name} created in {staff.department}",
    }


@app.get("/api/staff")
async def list_staff(
    department: Optional[str] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    _auth: dict = Depends(require_admin_or_staff_admin),
):
    """List all staff members."""
    q = db.query(SupportStaff)
    if department:
        q = q.filter(SupportStaff.department == department)
    if role:
        q = q.filter(SupportStaff.role == role)

    staff_list = q.order_by(SupportStaff.department, SupportStaff.name).all()

    result = []
    for s in staff_list:
        open_tickets = (
            db.query(SupportTicket)
            .filter(
                SupportTicket.assigned_staff_id == s.id,
                SupportTicket.status.in_(["open", "in_progress"]),
            )
            .count()
        )
        result.append({
            "id": s.id,
            "name": s.name,
            "email": s.email,
            "department": s.department,
            "role": s.role,
            "is_active": s.is_active,
            "max_tickets": s.max_tickets,
            "open_tickets": open_tickets,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_login": s.last_login.isoformat() if s.last_login else None,
        })

    return {"staff": result}


@app.get("/api/staff/{staff_id}")
async def get_staff(staff_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    staff = db.query(SupportStaff).filter(SupportStaff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    return {
        "id": staff.id,
        "name": staff.name,
        "email": staff.email,
        "department": staff.department,
        "role": staff.role,
        "is_active": staff.is_active,
        "max_tickets": staff.max_tickets,
    }


@app.put("/api/staff/{staff_id}")
async def update_staff(staff_id: int, req: UpdateStaffRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    staff = db.query(SupportStaff).filter(SupportStaff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    if req.name is not None:
        staff.name = req.name
    if req.department is not None:
        staff.department = req.department
    if req.role is not None:
        staff.role = req.role
    if req.is_active is not None:
        staff.is_active = req.is_active
    if req.max_tickets is not None:
        staff.max_tickets = req.max_tickets
    if req.new_password:
        staff.set_password(req.new_password)
    db.commit()
    return {"success": True, "message": "Staff updated"}


@app.delete("/api/staff/{staff_id}")
async def delete_staff(staff_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    staff = db.query(SupportStaff).filter(SupportStaff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    # Unassign any tickets
    db.query(SupportTicket).filter(SupportTicket.assigned_staff_id == staff_id).update(
        {SupportTicket.assigned_staff_id: None, SupportTicket.assigned_to: None}
    )
    db.delete(staff)
    db.commit()
    return {"success": True, "message": "Staff deleted"}


@app.get("/api/departments")
async def list_departments():
    """List all departments and category mapping."""
    return {
        "departments": DEPARTMENTS,
        "category_map": CATEGORY_DEPARTMENT_MAP,
        "roles": STAFF_ROLES,
    }


# ╔════════════════════════════════════════════════════════════════╗
# ║              PAYMENT GATEWAY CONFIGURATION                    ║
# ╚════════════════════════════════════════════════════════════════╝

class GatewayConfigRequest(BaseModel):
    gateway_name: str
    display_name: str
    merchant_id: Optional[str] = ""
    # Deprecated for security hardening: credentials must come from env vars.
    api_key: Optional[str] = ""
    api_secret: Optional[str] = ""
    is_sandbox: bool = True
    sandbox_url: Optional[str] = ""
    production_url: Optional[str] = ""
    callback_url: Optional[str] = ""
    redirect_url: Optional[str] = ""
    supports_fpx: bool = False
    supports_card: bool = False
    supports_ewallet: bool = False
    supports_duitnow: bool = False
    extra_config: Optional[str] = "{}"
    is_active: bool = False
    is_default: bool = False


@app.get("/api/payment/gateways")
async def list_payment_gateways(db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """List all configured payment gateways."""
    gateways = db.query(PaymentGatewayConfig).order_by(PaymentGatewayConfig.created_at).all()
    result = []
    for gw in gateways:
        cred_status = _gateway_credential_status(gw)
        result.append({
            "id": gw.id,
            "gateway_name": gw.gateway_name,
            "display_name": gw.display_name,
            "merchant_id": gw.merchant_id or "",
            "api_key": cred_status["api_key"],
            "api_secret": cred_status["api_secret"],
            "credential_source": cred_status["credential_source"],
            "api_key_env": cred_status["api_key_env"],
            "api_secret_env": cred_status["api_secret_env"],
            "is_sandbox": gw.is_sandbox,
            "sandbox_url": gw.sandbox_url or "",
            "production_url": gw.production_url or "",
            "callback_url": gw.callback_url or "",
            "redirect_url": gw.redirect_url or "",
            "supports_fpx": gw.supports_fpx,
            "supports_card": gw.supports_card,
            "supports_ewallet": gw.supports_ewallet,
            "supports_duitnow": gw.supports_duitnow,
            "extra_config": gw.extra_config or "{}",
            "is_active": gw.is_active,
            "is_default": gw.is_default,
            "created_at": gw.created_at.isoformat() if gw.created_at else None,
            "updated_at": gw.updated_at.isoformat() if gw.updated_at else None,
        })
    return {"success": True, "gateways": result, "available_providers": list(GATEWAY_REGISTRY.keys())}


@app.post("/api/payment/gateways")
async def create_payment_gateway(req: GatewayConfigRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Create/configure a new payment gateway."""
    if req.api_key or req.api_secret:
        logger.warning(
            "Gateway '%s' received API credentials in request; ignored by policy. Use env vars instead.",
            req.gateway_name,
        )

    existing = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.gateway_name == req.gateway_name
    ).first()
    if existing:
        return {"success": False, "message": f"Gateway '{req.gateway_name}' already configured. Use PUT to update."}

    # If setting as default, unset other defaults
    if req.is_default:
        db.query(PaymentGatewayConfig).update({PaymentGatewayConfig.is_default: False})

    gw = PaymentGatewayConfig(
        gateway_name=req.gateway_name,
        display_name=req.display_name,
        merchant_id=req.merchant_id,
        api_key="",
        api_secret="",
        is_sandbox=req.is_sandbox,
        sandbox_url=req.sandbox_url,
        production_url=req.production_url,
        callback_url=req.callback_url,
        redirect_url=req.redirect_url,
        supports_fpx=req.supports_fpx,
        supports_card=req.supports_card,
        supports_ewallet=req.supports_ewallet,
        supports_duitnow=req.supports_duitnow,
        extra_config=req.extra_config,
        is_active=req.is_active,
        is_default=req.is_default,
    )
    db.add(gw)
    db.commit()
    db.refresh(gw)
    audit_log("admin_gateway_create", _auth.get("user_id") or _auth.get("staff_id"), f"Created payment gateway '{req.gateway_name}'")
    logger.info(f"Payment gateway configured: {req.gateway_name}")
    return {"success": True, "message": f"Gateway '{req.display_name}' configured", "id": gw.id}


@app.put("/api/payment/gateways/{gateway_id}")
async def update_payment_gateway(gateway_id: int, req: GatewayConfigRequest, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Update payment gateway configuration."""
    if req.api_key or req.api_secret:
        logger.warning(
            "Gateway '%s' received API credentials in update request; ignored by policy. Use env vars instead.",
            req.gateway_name,
        )

    gw = db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id == gateway_id).first()
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway not found")

    if req.is_default:
        db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id != gateway_id).update(
            {PaymentGatewayConfig.is_default: False}
        )

    gw.display_name = req.display_name
    gw.merchant_id = req.merchant_id
    # Purge DB-stored credentials; runtime reads from env vars.
    gw.api_key = ""
    gw.api_secret = ""
    gw.is_sandbox = req.is_sandbox
    gw.sandbox_url = req.sandbox_url
    gw.production_url = req.production_url
    gw.callback_url = req.callback_url
    gw.redirect_url = req.redirect_url
    gw.supports_fpx = req.supports_fpx
    gw.supports_card = req.supports_card
    gw.supports_ewallet = req.supports_ewallet
    gw.supports_duitnow = req.supports_duitnow
    gw.extra_config = req.extra_config
    gw.is_active = req.is_active
    gw.is_default = req.is_default
    
    db.commit()
    audit_log("admin_gateway_update", _auth.get("user_id") or _auth.get("staff_id"), f"Updated payment gateway '{gw.gateway_name}'")
    logger.info(f"Payment gateway updated: {gw.gateway_name}")
    return {"success": True, "message": f"Gateway '{gw.display_name}' updated"}


@app.delete("/api/payment/gateways/{gateway_id}")
async def delete_payment_gateway(gateway_id: int, db: Session = Depends(get_db), _auth: dict = Depends(require_admin_or_staff_admin)):
    """Delete a payment gateway configuration."""
    gw = db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id == gateway_id).first()
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway not found")
    gateway_name = gw.gateway_name
    db.delete(gw)
    db.commit()
    audit_log("admin_gateway_delete", _auth.get("user_id") or _auth.get("staff_id"), f"Deleted payment gateway '{gateway_name}'")
    return {"success": True, "message": f"Gateway '{gw.display_name}' deleted"}


# ╔════════════════════════════════════════════════════════════════╗
# ║          PAYMENT METHODS & PROCESSING (App-facing)            ║
# ╚════════════════════════════════════════════════════════════════╝

@app.get("/api/payment/methods")
async def list_payment_methods(db: Session = Depends(get_db)):
    """
    List available payment methods for the mobile app.
    Derives methods from active payment gateways.
    """
    gateways = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.is_active == True
    ).all()

    methods = []
    method_id = 1

    for gw in gateways:
        if gw.supports_fpx:
            methods.append({
                "id": method_id,
                "type": "fpx",
                "name": "FPX Online Banking",
                "details": f"via {gw.display_name}",
                "gateway": gw.gateway_name,
                "is_default": gw.is_default,
            })
            method_id += 1
        if gw.supports_card:
            methods.append({
                "id": method_id,
                "type": "card",
                "name": "Credit / Debit Card",
                "details": f"via {gw.display_name}",
                "gateway": gw.gateway_name,
                "is_default": False,
            })
            method_id += 1
        if gw.supports_ewallet:
            methods.append({
                "id": method_id,
                "type": "ewallet",
                "name": "E-Wallet",
                "details": f"via {gw.display_name}",
                "gateway": gw.gateway_name,
                "is_default": False,
            })
            method_id += 1
        if gw.supports_duitnow:
            methods.append({
                "id": method_id,
                "type": "duitnow",
                "name": "DuitNow QR",
                "details": f"via {gw.display_name}",
                "gateway": gw.gateway_name,
                "is_default": False,
            })
            method_id += 1

    # Always include manual as a fallback
    methods.append({
        "id": method_id,
        "type": "manual",
        "name": "Manual / Bank Transfer",
        "details": "Admin will verify",
        "gateway": "manual",
        "is_default": len(gateways) == 0,
    })

    return methods


class ProcessPaymentRequest(BaseModel):
    amount: float
    payment_method_id: str
    charger_id: str


@app.post("/api/payment/process")
async def process_payment(
    req: ProcessPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process a charging payment. Deducts from the user's wallet balance.
    Called by the app after a charging session to settle payment.
    """
    # Validate amount
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Get user wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        return {"success": False, "message": "Wallet not found"}

    current_balance = Decimal(str(wallet.balance))
    charge_amount = Decimal(str(req.amount))

    if current_balance < charge_amount:
        return {"success": False, "message": "Insufficient balance"}

    # Deduct from wallet
    balance_before = wallet.balance
    wallet.balance = current_balance - charge_amount

    # Record transaction
    wt = WalletTransaction(
        user_id=current_user.id,
        wallet_id=wallet.id,
        transaction_type="charge_payment",
        amount=-float(charge_amount),
        balance_before=float(balance_before),
        balance_after=float(wallet.balance),
        payment_method=req.payment_method_id,
        status="completed",
        description=f"Charging payment for charger {req.charger_id}",
    )
    db.add(wt)
    db.commit()

    logger.info(f"Payment processed: RM{req.amount:.2f} for user {current_user.id} on charger {req.charger_id}")
    return {
        "success": True,
        "message": f"Payment of RM{req.amount:.2f} processed",
        "new_balance": float(wallet.balance),
    }


# ╔════════════════════════════════════════════════════════════════╗
# ║              PAYMENT TRANSACTIONS (Top-Up Flow)               ║
# ╚════════════════════════════════════════════════════════════════╝

class TopUpRequest(BaseModel):
    user_id: int
    amount: float
    payment_method: Optional[str] = None  # fpx, card, tng, grabpay, duitnow
    gateway_name: Optional[str] = None  # specific gateway, or use default


@app.post("/api/payment/topup")
async def create_topup(
    req: TopUpRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a top-up payment request (authenticated).
    Returns a payment URL for the user to complete payment.
    """
    verify_resource_owner(current_user, req.user_id)
    client_ip = get_client_ip(request)

    # Validate user
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    # Validate amount with financial safeguards
    dec_amount = validate_topup_amount(req.amount)

    # Get gateway config
    if req.gateway_name:
        gw_config = db.query(PaymentGatewayConfig).filter(
            PaymentGatewayConfig.gateway_name == req.gateway_name,
            PaymentGatewayConfig.is_active == True,
        ).first()
    else:
        gw_config = db.query(PaymentGatewayConfig).filter(
            PaymentGatewayConfig.is_default == True,
            PaymentGatewayConfig.is_active == True,
        ).first()

    if not gw_config:
        # Fallback to manual
        gw_config_dict = {"gateway_name": "manual"}
    else:
        gw_config_dict = _resolve_gateway_runtime_config(gw_config)

    # Generate transaction reference
    txn_ref = generate_transaction_ref()

    # Create transaction record
    txn = PaymentTransaction(
        transaction_ref=txn_ref,
        user_id=user.id,
        user_email=user.email,
        amount=req.amount,
        currency="MYR",
        payment_method=req.payment_method,
        gateway_name=gw_config_dict["gateway_name"],
        status="pending",
        purpose="topup",
        expired_at=_utcnow() + timedelta(hours=1),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Call gateway to create payment
    gateway = get_gateway(gw_config_dict)
    result = await gateway.create_payment(
        transaction_ref=txn_ref,
        amount=req.amount,
        currency="MYR",
        description=f"PlagSini EV Top-Up RM{req.amount:.2f}",
        customer_email=user.email,
        customer_name=user.name or "Customer",
        payment_method=req.payment_method,
    )

    # Update transaction with gateway response
    txn.gateway_transaction_id = result.get("gateway_transaction_id")
    txn.gateway_reference = result.get("gateway_reference")
    txn.payment_url = result.get("payment_url")
    txn.gateway_response = json.dumps(result.get("raw_response", {}))

    # TNG OrderCode returns qr_code for user to scan — include in response
    qr_code = result.get("qr_code") if result.get("success") else None

    if gw_config_dict["gateway_name"] == "manual":
        # Manual gateway — admin will verify and approve
        txn.status = "pending_approval"
    elif result.get("success"):
        txn.status = "processing"
    else:
        txn.status = "failed"
        txn.gateway_status = "creation_failed"

    db.commit()

    return {
        "success": result.get("success", False) or gw_config_dict["gateway_name"] == "manual",
        "transaction_ref": txn_ref,
        "payment_url": result.get("payment_url"),
        "qr_code": qr_code,
        "gateway": gw_config_dict["gateway_name"],
        "amount": req.amount,
        "status": txn.status,
        "message": result.get("message", "Payment created"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUICK-PAY (guest QR-scan flow — no login required)
# ─────────────────────────────────────────────────────────────────────────────
class QuickPayRequest(BaseModel):
    charger_id: str
    connector_id: int = 1
    amount: float  # MYR
    email: str
    gateway_name: Optional[str] = "tng"


@app.post("/api/charging/quick-pay")
async def quick_pay(
    req: QuickPayRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Guest pay-and-start endpoint (no auth).

    Flow:
      1. User scans QR at physical charger → /pay?charger=X&connector=Y page
      2. Page collects amount + email, POSTs here
      3. We validate charger is online & available
      4. Create PaymentTransaction (purpose="charge_payment", charger_id set)
      5. Call gateway create_payment → return TNG QR / payment URL to page
      6. Page displays QR; user pays in TNG eWallet
      7. TNG → /api/payment/callback/tng → we trigger OCPP RemoteStartTransaction
      8. Email invoice on charging completion
    """
    client_ip = get_client_ip(request)

    # Basic validation
    if req.amount < 1.0 or req.amount > 500.0:
        raise HTTPException(status_code=400, detail="Amount must be between RM 1 and RM 500")
    if "@" not in req.email or len(req.email) > 255:
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Validate charger
    charger = db.query(Charger).filter(Charger.charge_point_id == req.charger_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail=f"Charger {req.charger_id} not found")
    if charger.status != "online":
        raise HTTPException(status_code=409, detail=f"Charger is offline (status: {charger.status})")
    if charger.availability not in ("available", "preparing"):
        raise HTTPException(status_code=409, detail=f"Charger not available (state: {charger.availability})")

    # Get gateway config
    gw_config = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.gateway_name == req.gateway_name,
        PaymentGatewayConfig.is_active == True,
    ).first()
    if not gw_config:
        raise HTTPException(status_code=503, detail=f"Gateway {req.gateway_name} not configured/active")

    runtime_cfg = _resolve_gateway_runtime_config(gw_config)
    gw_config_dict = {
        "gateway_name": gw_config.gateway_name,
        "merchant_id": runtime_cfg.get("merchant_id"),
        "api_key": runtime_cfg.get("api_key"),
        "api_secret": runtime_cfg.get("api_secret"),
        "extra_config": gw_config.extra_config,
        "is_sandbox": runtime_cfg.get("is_sandbox", True),
    }

    # Create txn record
    txn_ref = generate_transaction_ref()
    txn = PaymentTransaction(
        transaction_ref=txn_ref,
        user_id=0,  # guest — no user account
        user_email=req.email,
        amount=req.amount,
        currency="MYR",
        payment_method=req.gateway_name,
        gateway_name=req.gateway_name,
        status="pending",
        purpose="charge_payment",
        charger_id=req.charger_id,
        connector_id=req.connector_id,
        customer_email=req.email,
        ip_address=client_ip,
        expired_at=_utcnow() + timedelta(minutes=15),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Call gateway
    gateway = get_gateway(gw_config_dict)
    result = await gateway.create_payment(
        transaction_ref=txn_ref,
        amount=req.amount,
        currency="MYR",
        description=f"PlagSini EV Charging — {req.charger_id} (RM {req.amount:.2f})",
        customer_email=req.email,
        customer_name=req.email.split("@")[0],
        payment_method=req.gateway_name,
    )

    txn.gateway_transaction_id = result.get("gateway_transaction_id")
    txn.gateway_reference = result.get("gateway_reference")
    txn.payment_url = result.get("payment_url")
    txn.gateway_response = json.dumps(result.get("raw_response", {}))
    if result.get("success"):
        txn.status = "processing"
    else:
        txn.status = "failed"
        txn.gateway_status = "creation_failed"
    db.commit()

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=f"Gateway create_payment failed: {result.get('message', 'unknown')}",
        )

    return {
        "success": True,
        "transaction_ref": txn_ref,
        "payment_url": result.get("payment_url"),
        "qr_code": result.get("qr_code"),
        "amount": req.amount,
        "currency": "MYR",
        "gateway": req.gateway_name,
        "expires_in_seconds": 900,
        "status_check_url": f"/api/charging/quick-pay/status/{txn_ref}",
    }


@app.get("/api/charging/quick-pay/status/{transaction_ref}")
async def quick_pay_status(transaction_ref: str, db: Session = Depends(get_db)):
    """Polled by mini-pay webpage to check if payment confirmed & charging started."""
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.transaction_ref == transaction_ref
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "transaction_ref": txn.transaction_ref,
        "status": txn.status,
        "gateway_status": txn.gateway_status,
        "amount": float(txn.amount),
        "charger_id": txn.charger_id,
        "connector_id": txn.connector_id,
        "paid_at": txn.paid_at.isoformat() if txn.paid_at else None,
    }


@app.post("/api/payment/callback/{gateway_name}")
async def payment_callback(gateway_name: str, request: Request, db: Session = Depends(get_db)):
    """
    Payment gateway callback/webhook handler.
    Each gateway posts here when payment is completed.
    """
    logger.info("Payment callback received from %s", gateway_name)

    # Manual top-ups are approved via admin endpoint only, never by public callback.
    if gateway_name == "manual":
        raise HTTPException(status_code=403, detail="Manual gateway callbacks are not allowed")

    # TNG uses RSA signature in payload — skip X-Callback-Secret, verify in verify_callback
    if gateway_name.lower() != "tng":
        _require_callback_secret(request, gateway_name)
    payload = await _extract_callback_payload(request)
    if not payload:
        raise HTTPException(status_code=400, detail="Empty or unsupported callback payload")
    headers = _request_headers_to_dict(request)

    # Get gateway config
    gw_config = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.gateway_name == gateway_name
    ).first()

    if not gw_config:
        logger.error(f"Unknown gateway callback: {gateway_name}")
        raise HTTPException(status_code=400, detail="Unknown gateway")

    runtime_cfg = _resolve_gateway_runtime_config(gw_config)
    gw_config_dict = {
        "gateway_name": gw_config.gateway_name,
        "api_key": runtime_cfg.get("api_key"),
        "api_secret": runtime_cfg.get("api_secret"),
        "extra_config": gw_config.extra_config,
    }

    # Verify callback
    gateway = get_gateway(gw_config_dict)
    verification = gateway.verify_callback(payload, headers=headers)

    if not verification.get("valid"):
        logger.warning(f"Invalid callback from {gateway_name}: {verification.get('message')}")
        raise HTTPException(status_code=400, detail="Invalid callback")

    # Find transaction
    txn_ref = verification.get("transaction_ref", "")
    txn = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.transaction_ref == txn_ref)
        .with_for_update()
        .first()
    )

    if not txn:
        # Try by gateway transaction ID
        gw_txn_id = verification.get("gateway_transaction_id", "")
        txn = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.gateway_transaction_id == gw_txn_id)
            .with_for_update()
            .first()
        )

    if not txn:
        logger.error(f"Transaction not found for callback: {txn_ref}")
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Already processed or already credited?
    if is_callback_already_processed(txn):
        audit_log(
            "payment_callback_replay",
            txn.user_id,
            f"Replay callback ignored for {txn.transaction_ref} ({gateway_name})",
            amount=float(txn.amount or 0),
        )
        return {"success": True, "message": "Already processed"}

    # Update transaction
    callback_status = verification.get("status", "failed")
    txn.gateway_status = callback_status
    txn.gateway_response = json.dumps(verification.get("raw_response", {}))
    txn.payment_method = verification.get("payment_method") or txn.payment_method

    if callback_status == "success":
        txn.status = "success"
        txn.paid_at = _utcnow()

        # Branch on purpose: top-up credits wallet, charge_payment triggers OCPP RemoteStart
        if txn.purpose == "charge_payment" and txn.charger_id:
            logger.info(
                f"✅ Charge payment success {txn.transaction_ref} — triggering "
                f"RemoteStart on {txn.charger_id}/connector {txn.connector_id}"
            )
            try:
                await _trigger_remote_start_after_payment(db, txn)
            except Exception as e:  # never block callback ack on OCPP failure
                logger.error(
                    f"RemoteStart trigger failed for {txn.transaction_ref}: {e}",
                    exc_info=True,
                )
                txn.gateway_status = f"paid_but_remote_start_failed: {e}"

            # Send receipt + "charger starting" email (non-blocking on failure)
            recipient = txn.customer_email or txn.user_email
            if recipient:
                try:
                    await send_charging_receipt(
                        to_email=recipient,
                        transaction_ref=txn.transaction_ref,
                        amount=float(txn.amount or 0),
                        charger_id=txn.charger_id or "—",
                        connector_id=int(txn.connector_id or 1),
                        paid_at_str=(txn.paid_at.strftime("%Y-%m-%d %H:%M:%S UTC") if txn.paid_at else "—"),
                        gateway=(txn.gateway_name or "TNG").upper(),
                    )
                except Exception as e:
                    logger.error(f"Receipt email failed for {txn.transaction_ref}: {e}")
        else:
            # Credit user's wallet (legacy top-up flow)
            _credit_wallet(db, txn)
        logger.info(f"✅ Payment success: {txn.transaction_ref} RM{txn.amount}")
    else:
        txn.status = "failed"
        logger.warning(f"❌ Payment failed: {txn.transaction_ref}")

    audit_log(
        "payment_callback_processed",
        txn.user_id,
        f"Callback processed for {txn.transaction_ref}: status={txn.status}, gateway={gateway_name}",
        amount=float(txn.amount or 0),
    )
    db.commit()
    return {"success": True, "status": txn.status}


def _credit_wallet(db: Session, txn: PaymentTransaction):
    """Credit user's wallet after successful payment (uses Decimal)."""
    if txn.wallet_transaction_id:
        return

    existing_wt = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.gateway_reference == txn.transaction_ref,
            WalletTransaction.transaction_type == "topup",
            WalletTransaction.status == "completed",
        )
        .first()
    )
    if existing_wt:
        txn.wallet_transaction_id = existing_wt.id
        return

    try:
        wallet = get_wallet_with_lock(db, txn.user_id)
    except HTTPException:
        wallet = None
    if not wallet:
        wallet = Wallet(user_id=txn.user_id, balance=Decimal("0.00"), points=0)
        db.add(wallet)
        db.flush()

    balance_before = wallet.balance
    points_before = wallet.points

    # Credit balance (Decimal safe)
    txn_amount = Decimal(str(txn.amount))
    wallet.balance = Decimal(str(wallet.balance)) + txn_amount

    # Bonus points: 10 points per RM1 + bonus for RM50+
    points_earned = int(txn_amount) * 10
    if txn_amount >= 50:
        points_earned += 50  # Bonus

    wallet.points += points_earned

    # Create wallet transaction
    wt = WalletTransaction(
        user_id=txn.user_id,
        wallet_id=wallet.id,
        transaction_type="topup",
        amount=txn_amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        points_amount=points_earned,
        points_before=points_before,
        points_after=wallet.points,
        payment_method=txn.payment_method or txn.gateway_name,
        payment_gateway=txn.gateway_name,
        gateway_reference=txn.transaction_ref,
        status="completed",
        description=f"Top-up via {txn.gateway_name.upper()} ({txn.payment_method or 'N/A'})",
    )
    db.add(wt)
    db.flush()

    txn.wallet_transaction_id = wt.id
    audit_log("payment_credited", txn.user_id, f"Credited RM{txn_amount} via {txn.gateway_name}", amount=float(txn_amount))


async def _trigger_remote_start_after_payment(db: Session, txn: PaymentTransaction):
    """
    Quick-pay flow: after payment success, fire OCPP RemoteStartTransaction
    on the linked charger and create a pending ChargingSession that on_start_transaction
    will later upgrade with the real transaction_id.

    Raises on hard failures so the caller can record `paid_but_remote_start_failed`
    on the payment row (and we'll have to refund / retry manually). Soft cases
    (timeout, charger-will-start-locally) are logged but treated as success.
    """
    if not txn.charger_id:
        raise RuntimeError("payment has no charger_id linkage")

    connector_id = int(txn.connector_id or 1)

    # 1) Look up the charger row
    charger = (
        db.query(Charger)
        .filter(Charger.charge_point_id == txn.charger_id)
        .first()
    )
    if not charger:
        raise RuntimeError(f"charger {txn.charger_id} not found in DB")

    # 2) Get the live OCPP websocket connection
    cp = get_active_charge_point(txn.charger_id)
    if not cp:
        raise RuntimeError(
            f"charger {txn.charger_id} not connected to OCPP server"
        )

    # 3) id_tag — RFID-like identifier OCPP uses to attribute the transaction.
    #    Use a short deterministic tag derived from the payment so we can
    #    correlate the StartTransaction callback back to this txn later.
    #    Max length 20 chars per OCPP 1.6 spec.
    id_tag = f"PAY{txn.id}"[:20]

    logger.info(
        f"[quick-pay] RemoteStartTransaction → {txn.charger_id} "
        f"connector {connector_id} id_tag={id_tag} (txn {txn.transaction_ref})"
    )

    response = await cp.remote_start_transaction(
        connector_id=connector_id,
        id_tag=id_tag,
    )

    status = getattr(response, "status", None) if response else None

    if status == "Rejected":
        raise RuntimeError("charger rejected RemoteStartTransaction")
    if status == "NotSupported":
        raise RuntimeError("charger does not support RemoteStartTransaction")

    # Either Accepted, or no response (charger may still start locally).
    # Create a pending ChargingSession so the live screen / banner can pick it up.
    try:
        existing_pending = (
            db.query(ChargingSession)
            .filter(
                ChargingSession.charger_id == charger.id,
                ChargingSession.status == "pending",
            )
            .first()
        )
        if not existing_pending:
            session = ChargingSession(
                charger_id=charger.id,
                transaction_id=0,  # placeholder, replaced below
                start_time=datetime.now(MYT).replace(tzinfo=None),
                status="pending",
                user_id=0,  # guest pay — not tied to an account
            )
            db.add(session)
            db.flush()
            session.transaction_id = -session.id  # unique negative placeholder

        charger.availability = "charging"
        # Stash id_tag on the payment row's gateway_status for traceability
        txn.gateway_status = f"paid_remote_start_{(status or 'sent').lower()}"
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"[quick-pay] failed to create pending session for {txn.transaction_ref}: {e}",
            exc_info=True,
        )
        # Don't re-raise — RemoteStart already accepted; session row is best-effort.

    if status == "Accepted":
        logger.info(
            f"[quick-pay] ✅ RemoteStart Accepted for {txn.charger_id} (txn {txn.transaction_ref})"
        )
    else:
        logger.warning(
            f"[quick-pay] ⚠️ no RemoteStart response from {txn.charger_id} — "
            f"charger may start locally (txn {txn.transaction_ref})"
        )


@app.post("/api/payment/approve/{transaction_ref}")
async def approve_manual_payment(
    transaction_ref: str,
    _auth: dict = Depends(require_admin_or_staff_admin),
    db: Session = Depends(get_db),
):
    """Admin approves a manual/bank transfer top-up."""
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.transaction_ref == transaction_ref
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.status == "success":
        return {"success": False, "message": "Already approved"}
    if txn.gateway_name != "manual":
        return {"success": False, "message": "Only manual payments can be approved"}

    txn.status = "success"
    txn.paid_at = _utcnow()
    txn.gateway_status = "admin_approved"

    _credit_wallet(db, txn)
    db.commit()
    audit_log("admin_manual_payment_approve", _auth.get("user_id") or _auth.get("staff_id"), f"Approved manual payment {txn.transaction_ref}", amount=float(txn.amount or 0))

    logger.info(f"✅ Manual payment approved: {txn.transaction_ref} RM{txn.amount} for user {txn.user_id}")
    return {"success": True, "message": f"Payment approved. RM{txn.amount:.2f} credited to user."}


@app.get("/api/payment/transactions")
async def list_payment_transactions(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List payment transactions (authenticated — user sees own, admin sees all)."""
    # Non-admin users can only see their own transactions
    if not current_user.is_admin:
        user_id = current_user.id
    q = db.query(PaymentTransaction).order_by(PaymentTransaction.created_at.desc())
    if user_id:
        q = q.filter(PaymentTransaction.user_id == user_id)
    if status:
        q = q.filter(PaymentTransaction.status == status)
    txns = q.limit(limit).all()

    result = []
    for t in txns:
        result.append({
            "id": t.id,
            "transaction_ref": t.transaction_ref,
            "user_id": t.user_id,
            "user_email": t.user_email,
            "amount": float(t.amount) if t.amount else 0.0,
            "currency": t.currency,
            "payment_method": t.payment_method,
            "gateway_name": t.gateway_name,
            "status": t.status,
            "purpose": t.purpose,
            "payment_url": t.payment_url,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "paid_at": t.paid_at.isoformat() if t.paid_at else None,
        })
    return {"success": True, "transactions": result}


@app.get("/api/payment/transactions/{transaction_ref}")
async def get_payment_transaction(
    transaction_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific payment transaction (authenticated, owner or admin)."""
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.transaction_ref == transaction_ref
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Non-admin can only see own transactions
    verify_resource_owner(current_user, txn.user_id)

    return {
        "success": True,
        "transaction": {
            "transaction_ref": txn.transaction_ref,
            "user_id": txn.user_id,
            "user_email": txn.user_email,
            "amount": float(txn.amount) if txn.amount else 0.0,
            "currency": txn.currency,
            "payment_method": txn.payment_method,
            "gateway_name": txn.gateway_name,
            "gateway_transaction_id": txn.gateway_transaction_id,
            "status": txn.status,
            "purpose": txn.purpose,
            "payment_url": txn.payment_url,
            "created_at": txn.created_at.isoformat() if txn.created_at else None,
            "paid_at": txn.paid_at.isoformat() if txn.paid_at else None,
        },
    }


# ╔════════════════════════════════════════════════════════════════╗
# ║                  ANALYTICS & AI INSIGHTS                      ║
# ╚════════════════════════════════════════════════════════════════╝

@app.get("/analytics")
async def analytics_page():
    """Serve the Analytics & Insights dashboard."""
    file_path = Path("templates/analytics.html")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Analytics template not found")
    return FileResponse(file_path, media_type="text/html")


@app.get("/api/analytics/overview")
async def analytics_overview(
    db: Session = Depends(get_db),
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
):
    """
    Comprehensive analytics overview — aggregates ALL platform data.
    Returns revenue, traffic, charger utilization, user growth, and more.
    """
    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    prev_month_start = now - timedelta(days=60)
    prev_month_end = now - timedelta(days=30)

    # ── REVENUE ──
    total_revenue_all = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed")
        .scalar()
    )
    revenue_this_month = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed",
                WalletTransaction.created_at >= month_ago)
        .scalar()
    )
    revenue_prev_month = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed",
                WalletTransaction.created_at >= prev_month_start,
                WalletTransaction.created_at < prev_month_end)
        .scalar()
    )
    revenue_today = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed",
                WalletTransaction.created_at >= today_start)
        .scalar()
    )
    revenue_growth = (
        round(((revenue_this_month - revenue_prev_month) / revenue_prev_month) * 100, 1)
        if revenue_prev_month > 0 else 0.0
    )

    # ── DAILY REVENUE (last 30 days) ──
    daily_revenue = []
    for i in range(30):
        day = now - timedelta(days=29 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        amt = float(
            db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
            .filter(WalletTransaction.transaction_type == "topup",
                    WalletTransaction.status == "completed",
                    WalletTransaction.created_at >= day_start,
                    WalletTransaction.created_at < day_end)
            .scalar()
        )
        daily_revenue.append({"date": day_start.strftime("%Y-%m-%d"), "amount": round(amt, 2)})

    # ── USERS ──
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    new_users_this_month = db.query(User).filter(User.created_at >= month_ago).count()
    new_users_prev_month = db.query(User).filter(
        User.created_at >= prev_month_start, User.created_at < prev_month_end
    ).count()
    user_growth = (
        round(((new_users_this_month - new_users_prev_month) / new_users_prev_month) * 100, 1)
        if new_users_prev_month > 0 else 0.0
    )

    # Daily user registrations (last 30 days)
    daily_users = []
    for i in range(30):
        day = now - timedelta(days=29 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        cnt = db.query(User).filter(
            User.created_at >= day_start, User.created_at < day_end
        ).count()
        daily_users.append({"date": day_start.strftime("%Y-%m-%d"), "count": cnt})

    # ── CHARGING SESSIONS ──
    total_sessions = db.query(ChargingSession).count()
    sessions_this_month = db.query(ChargingSession).filter(
        ChargingSession.start_time >= month_ago
    ).count()
    sessions_today = db.query(ChargingSession).filter(
        ChargingSession.start_time >= today_start
    ).count()
    active_sessions = db.query(ChargingSession).filter(
        ChargingSession.status == "active"
    ).count()
    completed_sessions = db.query(ChargingSession).filter(
        ChargingSession.status == "completed"
    ).count()

    # Daily sessions (last 30 days)
    daily_sessions = []
    for i in range(30):
        day = now - timedelta(days=29 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        cnt = db.query(ChargingSession).filter(
            ChargingSession.start_time >= day_start,
            ChargingSession.start_time < day_end
        ).count()
        daily_sessions.append({"date": day_start.strftime("%Y-%m-%d"), "count": cnt})

    # ── ENERGY ──
    total_energy = float(
        db.query(func.coalesce(func.sum(ChargingSession.energy_consumed), 0)).scalar()
    )
    energy_this_month = float(
        db.query(func.coalesce(func.sum(ChargingSession.energy_consumed), 0))
        .filter(ChargingSession.start_time >= month_ago)
        .scalar()
    )

    # ── CHARGERS ──
    total_chargers = db.query(Charger).count()
    online_chargers = db.query(Charger).filter(Charger.status == "online").count()
    offline_chargers = db.query(Charger).filter(Charger.status == "offline").count()
    faulted_chargers = db.query(Charger).filter(Charger.availability == "faulted").count()

    # Charger utilization: sessions per charger
    charger_stats = []
    chargers = db.query(Charger).all()
    for c in chargers:
        c_sessions = db.query(ChargingSession).filter(
            ChargingSession.charger_id == c.id
        ).count()
        c_energy = float(
            db.query(func.coalesce(func.sum(ChargingSession.energy_consumed), 0))
            .filter(ChargingSession.charger_id == c.id)
            .scalar()
        )
        c_faults = db.query(Fault).filter(
            Fault.charger_id == c.id, Fault.cleared == False
        ).count()
        charger_stats.append({
            "id": c.id,
            "charge_point_id": c.charge_point_id,
            "vendor": c.vendor,
            "status": c.status,
            "availability": c.availability,
            "total_sessions": c_sessions,
            "total_energy_kwh": round(c_energy, 2),
            "active_faults": c_faults,
        })

    # ── WALLET ──
    total_wallet_balance = float(
        db.query(func.coalesce(func.sum(Wallet.balance), 0)).scalar()
    )
    total_topups = db.query(WalletTransaction).filter(
        WalletTransaction.transaction_type == "topup",
        WalletTransaction.status == "completed"
    ).count()

    # Top-up by payment method
    topup_by_method = (
        db.query(
            WalletTransaction.payment_method,
            func.count(WalletTransaction.id),
            func.coalesce(func.sum(WalletTransaction.amount), 0)
        )
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed")
        .group_by(WalletTransaction.payment_method)
        .all()
    )
    payment_methods = [
        {"method": m or "unknown", "count": c, "total": round(float(t), 2)}
        for m, c, t in topup_by_method
    ]

    # ── FAULTS ──
    total_faults = db.query(Fault).count()
    active_faults = db.query(Fault).filter(Fault.cleared == False).count()
    faults_this_month = db.query(Fault).filter(Fault.timestamp >= month_ago).count()

    # Faults by type
    fault_types = (
        db.query(Fault.fault_type, func.count(Fault.id))
        .group_by(Fault.fault_type)
        .all()
    )
    fault_breakdown = [{"type": ft, "count": c} for ft, c in fault_types]

    # ── MAINTENANCE ──
    total_maintenance = db.query(MaintenanceRecord).count()
    total_maintenance_cost = float(
        db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0)).scalar()
    )
    maintenance_this_month = db.query(MaintenanceRecord).filter(
        MaintenanceRecord.created_at >= month_ago
    ).count()

    # ── SUPPORT TICKETS ──
    total_tickets = db.query(SupportTicket).count()
    open_tickets = db.query(SupportTicket).filter(SupportTicket.status == "open").count()
    resolved_tickets = db.query(SupportTicket).filter(
        SupportTicket.status.in_(["resolved", "closed"])
    ).count()

    tickets_by_category = (
        db.query(SupportTicket.category, func.count(SupportTicket.id))
        .group_by(SupportTicket.category)
        .all()
    )
    ticket_categories = [{"category": cat, "count": cnt} for cat, cnt in tickets_by_category]

    # ── PEAK HOURS (from sessions) ──
    peak_hours = {}
    sessions_with_time = db.query(ChargingSession).filter(
        ChargingSession.start_time.isnot(None)
    ).all()
    for s in sessions_with_time:
        hour = s.start_time.hour
        peak_hours[hour] = peak_hours.get(hour, 0) + 1
    hourly_traffic = [{"hour": h, "sessions": peak_hours.get(h, 0)} for h in range(24)]

    # ── PRICING ──
    pricing = db.query(Pricing).filter(Pricing.is_active == True).first()
    price_per_kwh = float(pricing.price_per_kwh) if pricing else 0.50
    charging_revenue = round(total_energy * price_per_kwh, 2)

    return {
        "generated_at": now.isoformat(),
        "revenue": {
            "total": round(total_revenue_all, 2),
            "this_month": round(revenue_this_month, 2),
            "prev_month": round(revenue_prev_month, 2),
            "today": round(revenue_today, 2),
            "growth_pct": revenue_growth,
            "charging_revenue": charging_revenue,
            "daily": daily_revenue,
        },
        "users": {
            "total": total_users,
            "active": active_users,
            "new_this_month": new_users_this_month,
            "growth_pct": user_growth,
            "daily": daily_users,
        },
        "sessions": {
            "total": total_sessions,
            "this_month": sessions_this_month,
            "today": sessions_today,
            "active": active_sessions,
            "completed": completed_sessions,
            "daily": daily_sessions,
        },
        "energy": {
            "total_kwh": round(total_energy, 2),
            "this_month_kwh": round(energy_this_month, 2),
            "price_per_kwh": price_per_kwh,
        },
        "chargers": {
            "total": total_chargers,
            "online": online_chargers,
            "offline": offline_chargers,
            "faulted": faulted_chargers,
            "details": charger_stats,
        },
        "wallet": {
            "total_balance": round(total_wallet_balance, 2),
            "total_topups": total_topups,
            "payment_methods": payment_methods,
        },
        "faults": {
            "total": total_faults,
            "active": active_faults,
            "this_month": faults_this_month,
            "by_type": fault_breakdown,
        },
        "maintenance": {
            "total": total_maintenance,
            "total_cost": round(total_maintenance_cost, 2),
            "this_month": maintenance_this_month,
        },
        "tickets": {
            "total": total_tickets,
            "open": open_tickets,
            "resolved": resolved_tickets,
            "by_category": ticket_categories,
        },
        "traffic": {
            "peak_hours": hourly_traffic,
        },
        "financials": {
            "gross_revenue": round(total_revenue_all + charging_revenue, 2),
            "maintenance_cost": round(total_maintenance_cost, 2),
            "net_profit": round(total_revenue_all + charging_revenue - total_maintenance_cost, 2),
        },
    }


@app.get("/api/analytics/insights")
async def analytics_insights(
    db: Session = Depends(get_db),
    admin_ctx: dict = Depends(require_admin_or_staff_admin),
):
    """
    AI-powered insights and recommendations engine.
    Analyzes all platform data and generates actionable suggestions.
    """
    now = _utcnow()
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)
    prev_month_start = now - timedelta(days=60)
    prev_month_end = now - timedelta(days=30)

    insights = []  # {"type": "warning|success|info|action", "category": "...", "title": "...", "message": "...", "priority": 1-5}

    # ═══ 1. REVENUE INSIGHTS ═══
    revenue_this_month = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed",
                WalletTransaction.created_at >= month_ago)
        .scalar()
    )
    revenue_prev_month = float(
        db.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(WalletTransaction.transaction_type == "topup",
                WalletTransaction.status == "completed",
                WalletTransaction.created_at >= prev_month_start,
                WalletTransaction.created_at < prev_month_end)
        .scalar()
    )

    if revenue_prev_month > 0:
        rev_change = ((revenue_this_month - revenue_prev_month) / revenue_prev_month) * 100
        if rev_change > 20:
            insights.append({
                "type": "success", "category": "Revenue", "priority": 2,
                "title": f"Revenue up {rev_change:.0f}% this month!",
                "message": f"Revenue grew from RM {revenue_prev_month:.2f} to RM {revenue_this_month:.2f}. Great momentum — consider expanding charger network to capture more demand."
            })
        elif rev_change < -15:
            insights.append({
                "type": "warning", "category": "Revenue", "priority": 1,
                "title": f"Revenue dropped {abs(rev_change):.0f}% this month",
                "message": f"Revenue fell from RM {revenue_prev_month:.2f} to RM {revenue_this_month:.2f}. Suggested actions: run promotional campaigns, review pricing, check for charger downtime."
            })
    elif revenue_this_month == 0:
        insights.append({
            "type": "action", "category": "Revenue", "priority": 1,
            "title": "No revenue recorded yet",
            "message": "No completed top-ups found. Ensure payment gateways are active and promote the platform to EV drivers in your area."
        })

    # ═══ 2. CHARGER HEALTH INSIGHTS ═══
    total_chargers = db.query(Charger).count()
    offline_chargers = db.query(Charger).filter(Charger.status == "offline").count()
    faulted_chargers = db.query(Charger).filter(Charger.availability == "faulted").count()

    if total_chargers == 0:
        insights.append({
            "type": "action", "category": "Infrastructure", "priority": 1,
            "title": "No chargers registered",
            "message": "Register your EV chargers to start accepting charging sessions. Go to OCPP Operations to add chargers."
        })
    else:
        offline_pct = (offline_chargers / total_chargers) * 100
        if offline_pct > 50:
            insights.append({
                "type": "warning", "category": "Infrastructure", "priority": 1,
                "title": f"{offline_chargers}/{total_chargers} chargers are offline ({offline_pct:.0f}%)",
                "message": "More than half your chargers are offline. Check network connectivity, power supply, and OCPP configuration. Each offline charger is lost revenue."
            })
        elif offline_pct > 20:
            insights.append({
                "type": "warning", "category": "Infrastructure", "priority": 2,
                "title": f"{offline_chargers} chargers are offline",
                "message": f"{offline_pct:.0f}% of chargers are down. Schedule maintenance checks and verify OCPP heartbeats."
            })

        if faulted_chargers > 0:
            insights.append({
                "type": "warning", "category": "Maintenance", "priority": 1,
                "title": f"{faulted_chargers} charger(s) reporting faults",
                "message": "Faulted chargers need immediate attention. Review fault logs and schedule repairs to minimize downtime."
            })

    # ═══ 3. UTILIZATION INSIGHTS ═══
    sessions_this_month = db.query(ChargingSession).filter(
        ChargingSession.start_time >= month_ago
    ).count()

    if total_chargers > 0 and sessions_this_month > 0:
        avg_sessions_per_charger = sessions_this_month / total_chargers
        if avg_sessions_per_charger < 5:
            insights.append({
                "type": "info", "category": "Utilization", "priority": 3,
                "title": f"Low utilization: {avg_sessions_per_charger:.1f} sessions/charger this month",
                "message": "Consider marketing campaigns, partnerships with nearby businesses, or listing on EV charging apps (PlugShare, ChargePoint) to increase visibility."
            })
        elif avg_sessions_per_charger > 100:
            insights.append({
                "type": "success", "category": "Utilization", "priority": 2,
                "title": f"High utilization: {avg_sessions_per_charger:.0f} sessions/charger this month!",
                "message": "Your chargers are in high demand. Consider adding more chargers at this location or expanding to nearby areas to reduce wait times and capture unserved demand."
            })

    # Peak hour analysis
    sessions_with_time = db.query(ChargingSession).filter(
        ChargingSession.start_time.isnot(None),
        ChargingSession.start_time >= month_ago
    ).all()
    peak_hours = {}
    for s in sessions_with_time:
        h = s.start_time.hour
        peak_hours[h] = peak_hours.get(h, 0) + 1

    if peak_hours:
        peak_hour = max(peak_hours, key=peak_hours.get)
        off_peak = min(peak_hours, key=peak_hours.get) if len(peak_hours) > 1 else None
        insights.append({
            "type": "info", "category": "Traffic", "priority": 3,
            "title": f"Peak charging hour: {peak_hour}:00 - {peak_hour + 1}:00",
            "message": f"Most sessions happen around {peak_hour}:00. Consider dynamic pricing — charge premium rates during peak and offer discounts during off-peak"
            + (f" ({off_peak}:00)" if off_peak is not None else "") + " to balance load."
        })

    # ═══ 4. USER GROWTH INSIGHTS ═══
    total_users = db.query(User).count()
    new_users_month = db.query(User).filter(User.created_at >= month_ago).count()
    new_users_prev = db.query(User).filter(
        User.created_at >= prev_month_start, User.created_at < prev_month_end
    ).count()

    if total_users > 0:
        # Users with wallet but zero balance
        empty_wallets = (
            db.query(Wallet)
            .filter(Wallet.balance <= 0)
            .count()
        )
        empty_pct = (empty_wallets / total_users) * 100
        if empty_pct > 60:
            insights.append({
                "type": "action", "category": "Users", "priority": 2,
                "title": f"{empty_pct:.0f}% of users have empty wallets",
                "message": f"{empty_wallets} users have RM 0 balance. Consider offering first-time top-up bonus (e.g., top up RM 20 get RM 5 free) to encourage spending."
            })

        if new_users_month == 0 and total_users > 1:
            insights.append({
                "type": "warning", "category": "Users", "priority": 2,
                "title": "No new user registrations this month",
                "message": "User growth has stalled. Suggested: social media campaigns, referral programs, partnerships with EV dealerships, and listing on charging aggregators."
            })
        elif new_users_prev > 0:
            user_change = ((new_users_month - new_users_prev) / new_users_prev) * 100
            if user_change > 30:
                insights.append({
                    "type": "success", "category": "Users", "priority": 3,
                    "title": f"User growth up {user_change:.0f}%!",
                    "message": f"{new_users_month} new users this month vs {new_users_prev} last month. Keep the momentum going!"
                })

    # ═══ 5. MAINTENANCE & COST INSIGHTS ═══
    total_maintenance_cost = float(
        db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0)).scalar()
    )
    total_revenue = revenue_this_month
    if total_revenue > 0 and total_maintenance_cost > 0:
        cost_ratio = (total_maintenance_cost / total_revenue) * 100
        if cost_ratio > 40:
            insights.append({
                "type": "warning", "category": "Costs", "priority": 2,
                "title": f"High maintenance costs ({cost_ratio:.0f}% of revenue)",
                "message": f"Maintenance costs (RM {total_maintenance_cost:.2f}) are {cost_ratio:.0f}% of revenue. Review recurring issues, consider preventive maintenance schedules, and negotiate better rates with service providers."
            })

    # ═══ 6. SUPPORT TICKET INSIGHTS ═══
    open_tickets = db.query(SupportTicket).filter(SupportTicket.status == "open").count()
    if open_tickets > 10:
        insights.append({
            "type": "warning", "category": "Support", "priority": 2,
            "title": f"{open_tickets} unresolved support tickets",
            "message": "High volume of open tickets may indicate a systemic issue. Review common categories and consider hiring more support staff or improving self-service options."
        })

    # Top complaint category
    top_category = (
        db.query(SupportTicket.category, func.count(SupportTicket.id).label("cnt"))
        .filter(SupportTicket.status.in_(["open", "in_progress"]))
        .group_by(SupportTicket.category)
        .order_by(desc("cnt"))
        .first()
    )
    if top_category and top_category[1] > 3:
        insights.append({
            "type": "info", "category": "Support", "priority": 3,
            "title": f"Most common issue: '{top_category[0]}' ({top_category[1]} open tickets)",
            "message": f"Consider creating FAQ entries, in-app guides, or a dedicated knowledge base article about '{top_category[0]}' issues to reduce repeat tickets."
        })

    # ═══ 7. PAYMENT GATEWAY INSIGHTS ═══
    active_gateways = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.is_active == True
    ).count()
    if active_gateways == 0:
        insights.append({
            "type": "action", "category": "Payments", "priority": 1,
            "title": "No payment gateways configured",
            "message": "Users cannot top up their wallets without an active payment gateway. Set up at least one gateway (OCBC, Billplz, or Manual) in Payment Settings."
        })

    failed_payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.status == "failed",
        PaymentTransaction.created_at >= week_ago
    ).count()
    total_payments_week = db.query(PaymentTransaction).filter(
        PaymentTransaction.created_at >= week_ago
    ).count()
    if total_payments_week > 0:
        fail_rate = (failed_payments / total_payments_week) * 100
        if fail_rate > 20:
            insights.append({
                "type": "warning", "category": "Payments", "priority": 1,
                "title": f"{fail_rate:.0f}% payment failure rate this week",
                "message": f"{failed_payments}/{total_payments_week} payments failed. Check gateway configuration, API keys, and connectivity. High failure rates drive users away."
            })

    # ═══ 8. FUTURE RECOMMENDATIONS ═══
    insights.append({
        "type": "info", "category": "Strategy", "priority": 4,
        "title": "Expand to OCPP 2.0.1",
        "message": "OCPP 2.0.1 supports device management, ISO 15118 Plug & Charge, and improved security. Plan your upgrade roadmap for 2027 to stay competitive."
    })

    if total_chargers > 0 and total_chargers < 5:
        insights.append({
            "type": "info", "category": "Growth", "priority": 4,
            "title": "Scale your network",
            "message": f"You have {total_chargers} charger(s). Industry data shows networks with 10+ chargers see 3x more repeat users. Target high-traffic locations: malls, offices, highways."
        })

    total_energy = float(
        db.query(func.coalesce(func.sum(ChargingSession.energy_consumed), 0)).scalar()
    )
    if total_energy > 0:
        co2_saved = total_energy * 0.585  # kg CO2 per kWh saved vs petrol
        insights.append({
            "type": "success", "category": "Impact", "priority": 5,
            "title": f"🌿 {co2_saved:.0f} kg CO₂ emissions avoided",
            "message": f"Your platform has delivered {total_energy:.1f} kWh of clean energy, preventing approximately {co2_saved:.0f} kg of CO₂ emissions. Feature this in your marketing!"
        })

    # Sort by priority (1 = highest)
    insights.sort(key=lambda x: x["priority"])

    return {
        "generated_at": now.isoformat(),
        "total_insights": len(insights),
        "insights": insights,
    }


# ============================================================
#  TICKET SLA REMINDER — Background Scheduler
# ============================================================

REMINDER_CHECK_INTERVAL = int(os.getenv("REMINDER_CHECK_MINUTES", "15"))  # minutes
# Minimum gap between reminders to the same staff for the same ticket
REMINDER_COOLDOWN_HOURS = 2

async def _ticket_reminder_loop():
    """Background loop: check for overdue / approaching-deadline tickets and email staff."""
    logger.info(f"Ticket SLA reminder scheduler started (every {REMINDER_CHECK_INTERVAL} min)")
    while True:
        await asyncio.sleep(REMINDER_CHECK_INTERVAL * 60)
        try:
            await _check_and_send_reminders()
        except Exception as e:
            logger.error(f"Reminder scheduler error: {e}", exc_info=True)


async def _check_and_send_reminders():
    """Check all open tickets and send reminders for overdue / approaching SLA."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        now = _utcnow()
        warning_deadline = now + timedelta(hours=2)
        cooldown_cutoff = now - timedelta(hours=REMINDER_COOLDOWN_HOURS)

        # Get tickets that are overdue OR approaching deadline, still open/in_progress
        tickets = db.query(SupportTicket).filter(
            SupportTicket.due_at.isnot(None),
            SupportTicket.due_at <= warning_deadline,
            SupportTicket.status.notin_(["resolved", "closed"]),
            # Only send if no reminder was sent recently (cooldown)
            or_(
                SupportTicket.reminder_sent_at.is_(None),
                SupportTicket.reminder_sent_at < cooldown_cutoff,
            ),
        ).all()

        if not tickets:
            return

        sent_count = 0
        for ticket in tickets:
            is_overdue = now > ticket.due_at
            staff_email = None
            staff_name = ticket.assigned_to or "Team"

            # Find assigned staff email
            if ticket.assigned_staff_id:
                staff = db.query(SupportStaff).filter(SupportStaff.id == ticket.assigned_staff_id).first()
                if staff:
                    staff_email = staff.email
                    staff_name = staff.name

            if not staff_email:
                # No staff assigned — skip (or could email department lead in future)
                continue

            due_str = ticket.due_at.strftime("%d %b %Y, %H:%M UTC") if ticket.due_at else "N/A"

            try:
                await send_ticket_reminder(
                    to_email=staff_email,
                    staff_name=staff_name,
                    ticket_number=ticket.ticket_number,
                    subject=ticket.subject,
                    priority=ticket.priority,
                    due_at_str=due_str,
                    is_overdue=is_overdue,
                )
                ticket.reminder_sent_at = now
                if is_overdue and not ticket.escalated:
                    ticket.escalated = True
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send reminder for {ticket.ticket_number}: {e}")

        if sent_count > 0:
            db.commit()
            logger.info(f"Sent {sent_count} ticket SLA reminders")
    finally:
        db.close()


@app.on_event("startup")
async def _start_reminder_scheduler():
    """Start the background SLA reminder task on app startup."""
    asyncio.create_task(_ticket_reminder_loop())


@app.on_event("startup")
async def _capture_api_loop_for_ocpp_dispatch():
    """
    Publish the FastAPI event loop to ocpp_server so the scheduled
    charging worker (running inside the OCPP thread's loop) can
    dispatch ChargePoint calls here.

    Why: python-ocpp's ChargePoint binds its internal Queue/Lock to
    whichever loop first touches it. API handlers are that first
    toucher, so all subsequent calls must come from this loop too,
    otherwise we get 'Queue bound to a different event loop'.
    """
    import ocpp_server  # local import avoids circular
    ocpp_server.API_LOOP = asyncio.get_running_loop()
    logger.info("API_LOOP captured for OCPP scheduler dispatch")


@app.on_event("startup")
async def _dev_auto_init():
    """
    When running via 'uvicorn api:app --reload' (Docker dev mode),
    handle DB init, default admin/staff creation, and OCPP server
    that would normally be done by main.py.

    Triggered by DEV_AUTO_INIT=1 env var (set in docker-compose.yml).
    """
    if not os.getenv("DEV_AUTO_INIT"):
        return

    import threading

    def _is_weak_password(password: str) -> bool:
        p = (password or "").strip()
        weak_values = {"", "1", "123456", "password", "admin", "admin123"}
        return len(p) < 12 or p.lower() in weak_values

    def _ensure_legacy_schema_columns():
        """Best-effort schema patch for older databases during dev startup."""
        db_local = SessionLocal()
        try:
            missing_users = []
            failed_col = db_local.execute(
                text("SHOW COLUMNS FROM users LIKE 'failed_login_attempts'")
            ).first()
            locked_col = db_local.execute(
                text("SHOW COLUMNS FROM users LIKE 'locked_until'")
            ).first()
            if not failed_col:
                missing_users.append("ADD COLUMN failed_login_attempts INT DEFAULT 0")
            if not locked_col:
                missing_users.append("ADD COLUMN locked_until DATETIME NULL")
            if missing_users:
                db_local.execute(text(f"ALTER TABLE users {', '.join(missing_users)}"))
                db_local.commit()
                logger.info("Patched users table with missing security columns")

            # Ticket SLA/reminder fields introduced in newer versions.
            missing_tickets = []
            due_at_col = db_local.execute(
                text("SHOW COLUMNS FROM support_tickets LIKE 'due_at'")
            ).first()
            reminder_col = db_local.execute(
                text("SHOW COLUMNS FROM support_tickets LIKE 'reminder_sent_at'")
            ).first()
            escalated_col = db_local.execute(
                text("SHOW COLUMNS FROM support_tickets LIKE 'escalated'")
            ).first()
            if not due_at_col:
                missing_tickets.append("ADD COLUMN due_at DATETIME NULL")
            if not reminder_col:
                missing_tickets.append("ADD COLUMN reminder_sent_at DATETIME NULL")
            if not escalated_col:
                missing_tickets.append("ADD COLUMN escalated BOOLEAN DEFAULT FALSE")
            if missing_tickets:
                db_local.execute(text(f"ALTER TABLE support_tickets {', '.join(missing_tickets)}"))
                db_local.commit()
                logger.info("Patched support_tickets table with missing SLA columns")
        except Exception as e:
            db_local.rollback()
            logger.warning(f"Could not patch legacy schema columns automatically: {e}")
        finally:
            db_local.close()

    # Initialize database tables
    init_db()
    _ensure_legacy_schema_columns()
    logger.info("Database initialized (dev auto-init)")

    # Create default admin user
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        admin_name = os.getenv("ADMIN_NAME", "Admin")

        if not admin_email or _is_weak_password(admin_password):
            logger.warning(
                "Skipping default admin auto-init: ADMIN_EMAIL/ADMIN_PASSWORD missing or weak "
                "(password must be >=12 chars and non-default)"
            )
        else:
            existing = db.query(User).filter(User.email == admin_email).first()
            if existing:
                existing.set_password(admin_password)
                existing.is_admin = True
                db.commit()
            else:
                admin = User(
                    email=admin_email, name=admin_name,
                    is_active=True, is_verified=True, is_admin=True,
                )
                admin.set_password(admin_password)
                db.add(admin)
                db.flush()
                wallet = Wallet(user_id=admin.id, balance=0.0, points=0)
                db.add(wallet)
                db.commit()
                logger.info(f"Default admin created: {admin_email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Dev auto-init admin error: {e}")
    finally:
        db.close()

    # Create default staff
    db = SessionLocal()
    try:
        staff_email = os.getenv("STAFF_EMAIL", "").strip()
        staff_password = os.getenv("STAFF_PASSWORD", "")
        if not staff_email or _is_weak_password(staff_password):
            logger.warning(
                "Skipping default staff auto-init: STAFF_EMAIL/STAFF_PASSWORD missing or weak "
                "(password must be >=12 chars and non-default)"
            )
        else:
            existing = db.query(SupportStaff).filter(SupportStaff.email == staff_email).first()
            if not existing:
                staff = SupportStaff(
                    name=os.getenv("STAFF_NAME", "Staff Admin"),
                    email=staff_email, department="IT", role="admin", max_tickets=20,
                )
                staff.set_password(staff_password)
                db.add(staff)
                db.commit()
                logger.info(f"Default staff created: {staff_email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Dev auto-init staff error: {e}")
    finally:
        db.close()

    # Start OCPP WebSocket server in background thread
    try:
        from ocpp_server import on_connect
        try:
            from websockets.asyncio.server import serve
        except ImportError:
            from websockets.server import serve

        async def _ocpp():
            async with serve(
                on_connect, "0.0.0.0", 9000,
                subprotocols=["ocpp1.6"],
                ping_interval=None, close_timeout=10, compression=None,
            ):
                await asyncio.Future()

        threading.Thread(target=lambda: asyncio.run(_ocpp()), daemon=True).start()
        logger.info("OCPP WebSocket server started on ws://0.0.0.0:9000 (dev auto-init)")
    except Exception as e:
        logger.error(f"Dev auto-init OCPP error: {e}")

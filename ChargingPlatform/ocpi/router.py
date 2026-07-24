"""
OCPI 2.2.1 CPO (Charge Point Operator) REST API router.
Implements Sender interface - eMSP (e.g. TNG) pulls data from us.
"""
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from database import Charger, ChargingSession, MeterValue, Pricing, SessionLocal, get_db
from .models import (
    Connector,
    EVSE,
    Location,
    VersionEndpoint,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocpi", tags=["OCPI 2.2.1"])

# OCPI_BASE_URL: Base URL for OCPI endpoints (e.g. https://api.plagsini.com)
# OCPI_TOKEN: Token for Authorization header (eMSP will use when calling us)
# OCPI_PARTY_ID: Our party ID (3 chars, e.g. PLG)
# OCPI_COUNTRY_CODE: Our country code (2 chars, e.g. MY)


def _get_base_url(request: Request) -> str:
    """Build base URL for OCPI endpoints."""
    base = os.getenv("OCPI_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    scheme = request.url.scheme
    host = request.headers.get("host", "localhost:8000")
    return f"{scheme}://{host}"


def _ocpi_auth(authorization: Optional[str] = Header(None)) -> None:
    """Validate OCPI Authorization: Token {token}.

    OCPI 2.2.1 spec says the token is transmitted base64-encoded, but many
    real-world clients still send it raw. We accept BOTH forms — try the
    header value verbatim first, then try base64-decoding it. Whichever
    matches the configured token wins. Constant-time compare on both paths.

    Fail-closed: if OCPI_TOKEN is not configured, reject all requests.
    Set OCPI_ALLOW_ANON=1 explicitly to bypass for local dev.
    """
    import base64
    token = os.getenv("OCPI_TOKEN", "").strip()
    if not token:
        if os.getenv("OCPI_ALLOW_ANON", "").strip().lower() in ("1", "true", "yes"):
            return  # explicit dev opt-in
        raise HTTPException(
            status_code=503,
            detail="OCPI not configured (server missing OCPI_TOKEN). Contact the operator.",
        )
    if not authorization or not authorization.startswith("Token "):
        raise HTTPException(status_code=403, detail="Missing OCPI token")

    header_val = authorization[6:].strip()
    # 1) Raw string match (non-spec but widely used in the wild)
    if secrets.compare_digest(header_val, token):
        return
    # 2) Base64-decoded match (OCPI 2.2.1 spec-compliant)
    try:
        decoded = base64.b64decode(header_val, validate=True).decode("utf-8", "strict")
    except Exception:
        decoded = None
    if decoded and secrets.compare_digest(decoded, token):
        return
    raise HTTPException(status_code=403, detail="Invalid OCPI token")


def _to_ocpi_datetime(dt) -> str:
    """Convert datetime to OCPI ISO format."""
    if dt is None:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


# ============ Versions ============
@router.get("/versions", response_model=dict)
async def get_versions(request: Request):
    """OCPI versions endpoint - lists supported versions."""
    base = _get_base_url(request)
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": [
            {"version": "2.2.1", "url": f"{base}/ocpi/2.2.1"}
        ]
    }


@router.get("/2.2.1", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_version_details(request: Request):
    """OCPI 2.2.1 version details - lists supported modules and endpoints."""
    base = _get_base_url(request)
    endpoints = [
        VersionEndpoint(identifier="credentials", role="SENDER", url=f"{base}/ocpi/2.2.1/credentials"),
        VersionEndpoint(identifier="locations", role="SENDER", url=f"{base}/ocpi/2.2.1/locations"),
        VersionEndpoint(identifier="sessions", role="SENDER", url=f"{base}/ocpi/2.2.1/sessions"),
        VersionEndpoint(identifier="cdrs", role="SENDER", url=f"{base}/ocpi/2.2.1/cdrs"),
        VersionEndpoint(identifier="tokens", role="SENDER", url=f"{base}/ocpi/2.2.1/tokens"),
        VersionEndpoint(identifier="tariffs", role="SENDER", url=f"{base}/ocpi/2.2.1/tariffs"),
        # Receiver = eMSP pushes/calls us. Commands are remote-control requests.
        VersionEndpoint(identifier="commands", role="RECEIVER", url=f"{base}/ocpi/2.2.1/commands"),
        VersionEndpoint(identifier="tariff_groups", role="SENDER", url=f"{base}/ocpi/2.2.1/tariff_groups"),
        VersionEndpoint(identifier="taxes", role="SENDER", url=f"{base}/ocpi/2.2.1/taxes"),
        VersionEndpoint(identifier="roaming_operators", role="SENDER", url=f"{base}/ocpi/2.2.1/roaming_operators"),
    ]
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "version": "2.2.1",
            "endpoints": [e.model_dump() for e in endpoints]
        }
    }


# ============ Locations ============
@router.get("/2.2.1/locations", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_locations(
    request: Request,
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get list of charging locations (from chargers)."""
    chargers = db.query(Charger).offset(offset).limit(limit or 100).all()
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")

    locations = []
    for c in chargers:
        loc_id = f"{country}{party_id}-{c.charge_point_id}"
        now = _to_ocpi_datetime(datetime.utcnow())
        connector = Connector(
            id="1",
            standard="IEC_62196_T2",
            format="SOCKET",
            power_type="AC_1_PHASE",
            voltage=230,
            amperage=32,
            max_electric_power=7360,
            last_updated=now,
        )
        evse_status = "AVAILABLE"
        if (c.availability or "").lower() == "charging":
            evse_status = "CHARGING"
        elif (c.availability or "").lower() in ("unavailable", "faulted"):
            evse_status = "INOPERATIVE"

        evse = EVSE(
            uid=f"{loc_id}-EVSE1",
            evse_id=f"{country}*{party_id}*E*{c.charge_point_id}",
            status=evse_status,
            connectors=[connector],
            last_updated=now,
        )
        loc = Location(
            country_code=country,
            party_id=party_id,
            id=loc_id,
            publish=True,
            type="OTHER",
            name=c.charge_point_id,
            address=os.getenv("OCPI_LOCATION_ADDRESS", "Charging Station"),
            city=os.getenv("OCPI_LOCATION_CITY", "Kuala Lumpur"),
            postal_code=os.getenv("OCPI_LOCATION_POSTAL", "50000"),
            country=country,
            coordinates={
                "latitude": float(os.getenv("OCPI_LOCATION_LAT", "3.1390")),
                "longitude": float(os.getenv("OCPI_LOCATION_LON", "101.6869")),
            },
            evses=[evse],
            time_zone="Asia/Kuala_Lumpur",
            last_updated=now,
        )
        locations.append(loc.model_dump())

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": locations,
    }


@router.get("/2.2.1/locations/{location_id}", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_location(
    location_id: str,
    db: Session = Depends(get_db),
):
    """Get single location by ID."""
    # Parse location_id format: MYPLG-ESP32-CP-01 or similar
    parts = location_id.split("-", 2)
    if len(parts) >= 3:
        cp_id = parts[2]
    else:
        cp_id = location_id
    charger = db.query(Charger).filter(Charger.charge_point_id == cp_id).first()
    if not charger:
        return {
            "status_code": 2003,
            "status_message": "Unknown location",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": None,
        }

    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")
    loc_id = f"{country}{party_id}-{charger.charge_point_id}"
    now = _to_ocpi_datetime(datetime.utcnow())
    connector = Connector(
        id="1",
        standard="IEC_62196_T2",
        format="SOCKET",
        power_type="AC_1_PHASE",
        voltage=230,
        amperage=32,
        max_electric_power=7360,
        last_updated=now,
    )
    evse_status = "AVAILABLE"
    if (charger.availability or "").lower() == "charging":
        evse_status = "CHARGING"
    elif (charger.availability or "").lower() in ("unavailable", "faulted"):
        evse_status = "INOPERATIVE"

    evse = EVSE(
        uid=f"{loc_id}-EVSE1",
        evse_id=f"{country}*{party_id}*E*{charger.charge_point_id}",
        status=evse_status,
        connectors=[connector],
        last_updated=now,
    )
    loc = Location(
        country_code=country,
        party_id=party_id,
        id=loc_id,
        publish=True,
        type="OTHER",
        name=charger.charge_point_id,
        address=os.getenv("OCPI_LOCATION_ADDRESS", "Charging Station"),
        city=os.getenv("OCPI_LOCATION_CITY", "Kuala Lumpur"),
        postal_code=os.getenv("OCPI_LOCATION_POSTAL", "50000"),
        country=country,
        coordinates={
            "latitude": float(os.getenv("OCPI_LOCATION_LAT", "3.1390")),
            "longitude": float(os.getenv("OCPI_LOCATION_LON", "101.6869")),
        },
        evses=[evse],
        time_zone="Asia/Kuala_Lumpur",
        last_updated=now,
    )
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": loc.model_dump(),
    }


# ============ Sessions ============
@router.get("/2.2.1/sessions", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_sessions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get charging sessions (OCPI pull model)."""
    q = db.query(ChargingSession).filter(
        ChargingSession.status.in_(["active", "completed", "stopped"])
    )
    if date_from:
        try:
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            q = q.filter(ChargingSession.start_time >= df)
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            q = q.filter(ChargingSession.start_time < dt)
        except Exception:
            pass
    sessions = q.order_by(ChargingSession.start_time.desc()).offset(offset).limit(limit or 100).all()

    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")

    result = []
    for s in sessions:
        charger = s.charger
        if not charger:
            continue
        loc_id = f"{country}{party_id}-{charger.charge_point_id}"
        ocpi_status = "ACTIVE" if s.status == "active" else "COMPLETED"
        result.append({
            "id": str(s.transaction_id),
            "start_datetime": _to_ocpi_datetime(s.start_time),
            "end_datetime": _to_ocpi_datetime(s.stop_time) if s.stop_time else None,
            "kwh": float(s.energy_consumed or 0),
            "cdr_token": {"uid": s.user_id or "UNKNOWN", "type": "APP_USER", "contract_id": s.user_id or "UNKNOWN"},
            "auth_method": "AUTH_REQUEST",
            "location_id": loc_id,
            "evse_uid": f"{loc_id}-EVSE1",
            "connector_id": "1",
            "currency": "MYR",
            "status": ocpi_status,
            "last_updated": _to_ocpi_datetime(s.stop_time or s.start_time),
        })

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": result,
    }


# ============ CDRs ============
@router.get("/2.2.1/cdrs", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_cdrs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get Charge Detail Records (CDRs) for billing."""
    q = db.query(ChargingSession).filter(
        ChargingSession.status.in_(["completed", "stopped"]),
        ChargingSession.stop_time.isnot(None),
    )
    if date_from:
        try:
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            q = q.filter(ChargingSession.stop_time >= df)
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            q = q.filter(ChargingSession.stop_time < dt)
        except Exception:
            pass
    sessions = q.order_by(ChargingSession.stop_time.desc()).offset(offset).limit(limit or 100).all()

    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")

    result = []
    for s in sessions:
        charger = s.charger
        if not charger:
            continue
        loc_id = f"{country}{party_id}-{charger.charge_point_id}"
        energy = float(s.energy_consumed or 0)
        start_time = s.start_time or datetime.utcnow()
        stop_time = s.stop_time or datetime.utcnow()
        duration_h = (stop_time - start_time).total_seconds() / 3600 if stop_time and start_time else 0

        # Get pricing for total_cost (charger-specific first, then default)
        pricing = db.query(Pricing).filter(
            Pricing.charger_id == charger.id,
            Pricing.is_active == True
        ).first()
        if not pricing:
            pricing = db.query(Pricing).filter(
                Pricing.charger_id.is_(None),
                Pricing.is_active == True
            ).first()
        price_per_kwh = float(pricing.price_per_kwh) if pricing else 0.5
        total_cost = round(energy * price_per_kwh, 2)

        result.append({
            "id": str(s.transaction_id),
            "start_datetime": _to_ocpi_datetime(start_time),
            "end_datetime": _to_ocpi_datetime(stop_time),
            "auth_id": s.user_id or "UNKNOWN",
            "auth_method": "AUTH_REQUEST",
            "location_id": loc_id,
            "evse_uid": f"{loc_id}-EVSE1",
            "connector_id": "1",
            "currency": "MYR",
            "total_cost": total_cost,
            "total_energy": energy,
            "total_time": round(duration_h, 4),
            "cdr_token": {"uid": s.user_id or "UNKNOWN", "type": "APP_USER", "contract_id": s.user_id or "UNKNOWN"},
            "charging_periods": [{
                "start_datetime": _to_ocpi_datetime(start_time),
                "dimensions": [{"type": "ENERGY", "volume": energy}]
            }],
            "last_updated": _to_ocpi_datetime(stop_time),
        })

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": result,
    }


# ============ Tokens ============
@router.get("/2.2.1/tokens", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_tokens(
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get tokens (optional - for token whitelist). Returns empty list."""
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": [],
    }


# ============ Tariffs ============
@router.get("/2.2.1/tariffs", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_tariffs(
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get tariffs (pricing)."""
    pricings = db.query(Pricing).filter(Pricing.is_active == True).offset(offset).limit(limit or 100).all()
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    result = []
    for i, p in enumerate(pricings):
        result.append({
            "id": f"TARIFF-{p.id}",
            "currency": "MYR",
            "elements": [{
                "price_components": [{
                    "type": "ENERGY",
                    "price": float(p.price_per_kwh),
                    "step_size": 1
                }]
            }],
            "last_updated": now,
        })
    if not result:
        result.append({
            "id": "TARIFF-DEFAULT",
            "currency": "MYR",
            "elements": [{
                "price_components": [{
                    "type": "ENERGY",
                    "price": 0.5,
                    "step_size": 1
                }]
            }],
            "last_updated": now,
        })
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": result,
    }


# ============ Commands (Receiver — eMSP triggers us) ============
# OCPI Commands flow: eMSP POSTs the command body → we reply CommandResponse
# synchronously (ACCEPTED/REJECTED) → we later POST CommandResult to the
# eMSP's response_url once the physical charger replies.
COMMAND_TYPES = {"START_SESSION", "STOP_SESSION", "UNLOCK_CONNECTOR", "RESERVE_NOW", "CANCEL_RESERVATION"}


async def _post_command_result(response_url: str, result: str, message: Optional[str] = None) -> None:
    """Fire-and-forget POST of async CommandResult back to the eMSP."""
    import asyncio
    import httpx
    try:
        token = os.getenv("OCPI_OUTBOUND_TOKEN", "").strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Token {token}"
        body = {"result": result}
        if message:
            body["message"] = [{"language": "en", "text": message}]
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(response_url, json=body, headers=headers)
    except Exception as e:
        logger.warning(f"[ocpi-commands] callback POST to {response_url} failed: {e}")


@router.post("/2.2.1/commands/{command}", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def post_command(command: str, request: Request, db: Session = Depends(get_db)):
    """eMSP-initiated remote command. Returns synchronous CommandResponse; the
    final CommandResult is POSTed asynchronously to the eMSP's response_url."""
    import asyncio
    from ocpp_server import get_active_charge_point

    if command not in COMMAND_TYPES:
        return {
            "status_code": 2001,
            "status_message": f"Unknown command: {command}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {"result": "NOT_SUPPORTED", "timeout": 0},
        }

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    response_url = body.get("response_url")
    if not response_url:
        return {
            "status_code": 2002,
            "status_message": "Missing response_url",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {"result": "REJECTED", "timeout": 0},
        }

    if command == "START_SESSION":
        location_id = body.get("location_id")
        evse_uid = body.get("evse_uid") or location_id
        connector_id = int(body.get("connector_id") or 1)
        token = (body.get("token") or {}).get("uid") or "ROAMING_USER"
        charger = db.query(Charger).filter(Charger.charge_point_id == location_id).first()
        if not charger:
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "REJECTED", "timeout": 0},
            }
        cp = get_active_charge_point(location_id)
        if cp is None:
            asyncio.create_task(_post_command_result(response_url, "EVSE_INOPERATIVE", "Charger offline"))
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "ACCEPTED", "timeout": 30},
            }

        async def _dispatch_start():
            try:
                resp = await cp.remote_start_transaction(connector_id=connector_id, id_tag=token)
                accepted = bool(resp and getattr(resp, "status", "").lower() == "accepted")
                await _post_command_result(response_url, "ACCEPTED" if accepted else "REJECTED")
            except Exception as e:
                await _post_command_result(response_url, "FAILED", str(e))

        asyncio.create_task(_dispatch_start())
        return {
            "status_code": 1000, "status_message": "Success",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {"result": "ACCEPTED", "timeout": 30},
        }

    if command == "STOP_SESSION":
        session_id = body.get("session_id")
        sess = db.query(ChargingSession).filter(ChargingSession.id == session_id).first() if session_id else None
        if not sess or not sess.transaction_id:
            asyncio.create_task(_post_command_result(response_url, "UNKNOWN_SESSION"))
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "ACCEPTED", "timeout": 30},
            }
        charger = db.query(Charger).filter(Charger.id == sess.charger_id).first()
        cp = get_active_charge_point(charger.charge_point_id) if charger else None
        if cp is None:
            asyncio.create_task(_post_command_result(response_url, "EVSE_INOPERATIVE", "Charger offline"))
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "ACCEPTED", "timeout": 30},
            }

        async def _dispatch_stop():
            try:
                resp = await cp.remote_stop_transaction(transaction_id=int(sess.transaction_id))
                accepted = bool(resp and getattr(resp, "status", "").lower() == "accepted")
                await _post_command_result(response_url, "ACCEPTED" if accepted else "REJECTED")
            except Exception as e:
                await _post_command_result(response_url, "FAILED", str(e))

        asyncio.create_task(_dispatch_stop())
        return {
            "status_code": 1000, "status_message": "Success",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {"result": "ACCEPTED", "timeout": 30},
        }

    # UNLOCK_CONNECTOR / RESERVE_NOW / CANCEL_RESERVATION — surface as NOT_SUPPORTED
    # until the underlying OCPP plumbing is added. Returning a structured response
    # is required by the spec even for unsupported commands.
    asyncio.create_task(_post_command_result(response_url, "NOT_SUPPORTED"))
    return {
        "status_code": 1000, "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {"result": "ACCEPTED", "timeout": 5},
    }


# ============ Taxes ============
def _default_taxes() -> list:
    """Default tax rules for Malaysia. Override via system_settings key 'ocpi_taxes'."""
    return [
        {
            "id": "sst-my",
            "name": "SST",
            "rate": 6.0,
            "applies_to": "TOTAL",
            "country_code": "MY",
        }
    ]


@router.get("/2.2.1/taxes", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_taxes():
    """Tax rules applied on top of tariff prices. Override via OCPI_TAXES_JSON env (a JSON array)."""
    import json as _json
    raw = os.getenv("OCPI_TAXES_JSON", "").strip()
    try:
        taxes = _json.loads(raw) if raw else _default_taxes()
    except Exception:
        taxes = _default_taxes()
    now = _to_ocpi_datetime(datetime.utcnow())
    for t in taxes:
        t.setdefault("last_updated", now)
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": now,
        "data": taxes,
    }


# ============ Tariff Groups ============
@router.get("/2.2.1/tariff_groups", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_tariff_groups(db: Session = Depends(get_db)):
    """Group tariffs by AC vs DC capability so eMSPs can show simple price tiers."""
    pricings = db.query(Pricing).filter(Pricing.is_active == True).all()  # noqa: E712
    now = _to_ocpi_datetime(datetime.utcnow())
    ac_ids, dc_ids = [], []
    for p in pricings:
        # Pricing rows tied to a charger inherit its connector type; default → AC bucket.
        charger = db.query(Charger).filter(Charger.id == p.charger_id).first() if p.charger_id else None
        ctype = (charger.connector_type or "AC").upper() if charger else "AC"
        (dc_ids if "DC" in ctype or "CCS" in ctype or "CHADEMO" in ctype else ac_ids).append(str(p.id))
    groups = []
    if ac_ids:
        groups.append({"id": "ac-default", "name": "AC Charging", "description": "Slow + medium AC tariffs", "tariff_ids": ac_ids, "last_updated": now})
    if dc_ids:
        groups.append({"id": "dc-default", "name": "DC Fast Charging", "description": "DC fast-charge tariffs", "tariff_ids": dc_ids, "last_updated": now})
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": now,
        "data": groups,
    }


# ============ Roaming Operators ============
def _default_roaming_operators() -> list:
    """Bootstrap allow-list. Override via system_settings key 'ocpi_roaming_operators'."""
    return [
        {
            "party_id": "VLT",
            "country_code": "SG",
            "name": "Voltality Pte Ltd",
            "role": "HUB",
            "status": "ALLOWED",
        }
    ]


@router.get("/2.2.1/roaming_operators", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_roaming_operators():
    """Operators we accept roaming traffic from. Override via OCPI_ROAMING_OPERATORS_JSON env (a JSON array)."""
    import json as _json
    raw = os.getenv("OCPI_ROAMING_OPERATORS_JSON", "").strip()
    try:
        ops = _json.loads(raw) if raw else _default_roaming_operators()
    except Exception:
        ops = _default_roaming_operators()
    now = _to_ocpi_datetime(datetime.utcnow())
    for o in ops:
        o.setdefault("last_updated", now)
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": now,
        "data": ops,
    }


# ============ Credentials ============
@router.get("/2.2.1/credentials", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_credentials(request: Request):
    """Return our current credentials to an authenticated partner. Standard
    OCPI 2.2.1 handshake step — partner GETs this before deciding to POST
    their own credentials for registration."""
    base = _get_base_url(request)
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "token": os.getenv("OCPI_TOKEN", "").strip(),
            "url": f"{base}/ocpi/versions",
            "roles": [
                {
                    "role": "CPO",
                    "party_id": os.getenv("OCPI_PARTY_ID", "PLG"),
                    "country_code": os.getenv("OCPI_COUNTRY_CODE", "MY"),
                    "business_details": {
                        "name": "C Zero Sdn Bhd",
                        "website": "https://charger.czeros.tech",
                    },
                }
            ],
        },
    }


@router.post("/2.2.1/credentials", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def post_credentials(request: Request):
    """OCPI 2.2.1 credentials registration handshake (spec §7.1).

    Partner POSTs their {token, url, roles}. We:
      1. Store the partner's token + endpoints URL (so we can later call
         them back for asynchronous CommandResult, PATCH pushes, etc.)
      2. Optionally rotate the bootstrap token they used to reach us — for
         v1 we keep the same OCPI_TOKEN so admins can still reach the
         endpoints; per-partner tokens are on the roadmap.
      3. Return our {token, url, roles} so the partner can call us back.
    """
    base = _get_base_url(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    partner_token = (body.get("token") or "").strip()
    partner_url = (body.get("url") or "").strip()
    partner_roles = body.get("roles") or []
    if not partner_token or not partner_url:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: token, url",
        )

    # Structured audit record — a future ocpi_partners table will persist this,
    # for now the log is the source of truth.
    logger.info(
        "[ocpi-credentials] Registration from partner url=%s token_prefix=%s roles=%s",
        partner_url,
        partner_token[:8] + "..." if len(partner_token) > 8 else partner_token,
        [f"{r.get('country_code','?')}/{r.get('party_id','?')}({r.get('role','?')})" for r in partner_roles],
    )

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "token": os.getenv("OCPI_TOKEN", "").strip(),
            "url": f"{base}/ocpi/versions",
            "roles": [
                {
                    "role": "CPO",
                    "party_id": os.getenv("OCPI_PARTY_ID", "PLG"),
                    "country_code": os.getenv("OCPI_COUNTRY_CODE", "MY"),
                    "business_details": {
                        "name": "C Zero Sdn Bhd",
                        "website": "https://charger.czeros.tech",
                    },
                }
            ],
        },
    }


@router.put("/2.2.1/credentials", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def put_credentials(request: Request):
    """OCPI 2.2.1 credentials update (spec §7.1). Same shape as POST — used
    by a partner to rotate their token after the initial registration."""
    return await post_credentials(request)

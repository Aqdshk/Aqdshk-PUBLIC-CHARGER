"""
OCPI 2.2.1 CPO (Charge Point Operator) REST API router.
Implements Sender interface - eMSP (e.g. TNG) pulls data from us.
"""
import logging
import os
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
    """Validate OCPI Authorization: Token {token}."""
    token = os.getenv("OCPI_TOKEN", "").strip()
    if not token:
        return  # No token configured = allow (dev/test mode)
    if not authorization or not authorization.startswith("Token "):
        raise HTTPException(status_code=403, detail="Missing OCPI token")
    if authorization[6:].strip() != token:
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


@router.get("/2.2.1", response_model=dict)
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
            evse_id=f"{c.charge_point_id}-1",
            status=evse_status,
            connectors=[connector],
            last_updated=now,
        )
        loc = Location(
            id=loc_id,
            publish=True,
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
        evse_id=f"{charger.charge_point_id}-1",
        status=evse_status,
        connectors=[connector],
        last_updated=now,
    )
    loc = Location(
        id=loc_id,
        publish=True,
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


# ============ Credentials ============
@router.post("/2.2.1/credentials", response_model=dict)
async def post_credentials(request: Request):
    """
    OCPI registration - eMSP (TNG) sends their credentials to register with us.
    We will store and respond with our credentials.
    """
    pass  # TODO: Implement when TNG provides API docs
    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {"token": "placeholder", "url": _get_base_url(request) + "/ocpi/2.2.1"},
    }

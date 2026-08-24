"""
OCPI 2.2.1 CPO (Charge Point Operator) REST API router.
Implements Sender interface - eMSP (e.g. TNG) pulls data from us.
"""
import asyncio
import logging
import os
import secrets
from urllib.parse import quote
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from database import (
    Charger, ChargingSession, MeterValue, OcpiPartner, Pricing, SessionLocal, get_db,
)
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


# How stale a charger's heartbeat may be before we stop publishing it to
# roaming partners. Long enough that a flaky link or an overnight power cut
# does not pull a real charge point off the map, short enough that units which
# have genuinely gone away disappear. Override with OCPI_PUBLISH_MAX_AGE_DAYS.
_PUBLISH_MAX_AGE_DAYS = int(os.getenv("OCPI_PUBLISH_MAX_AGE_DAYS", "7"))


# OCPP connector state → OCPI 2.2.1 EVSE status.
#
# This lived inline in two places and both only handled charging, unavailable
# and faulted, so everything else — including "finishing" and "preparing" —
# fell through to AVAILABLE. A car that had finished charging but was still
# plugged in was therefore advertised to roaming partners as a free bay, and a
# driver sent to it would find the connector occupied.
#
# BLOCKED is the status OCPI defines for exactly that: "not accessible because
# of a physical barrier, i.e. a car". It is also the signal roaming partners
# use to detect idling.
_OCPI_EVSE_STATUS = {
    "charging":    "CHARGING",
    "preparing":   "BLOCKED",      # cable connected, not yet drawing
    "finishing":   "BLOCKED",      # charge done, car still plugged in — idling
    "reserved":    "RESERVED",
    "unavailable": "INOPERATIVE",
    "faulted":     "OUTOFORDER",
    "available":   "AVAILABLE",
}


def _ocpi_evse_status(availability: Optional[str]) -> str:
    """Map our connector state to an OCPI EVSE status.

    An unrecognised or missing state becomes UNKNOWN rather than AVAILABLE:
    claiming a bay is free when we cannot tell sends drivers to chargers that
    may not serve them.
    """
    return _OCPI_EVSE_STATUS.get((availability or "").strip().lower(), "UNKNOWN")


def _charger_id_from_location(location_id: Optional[str]) -> str:
    """Recover our charge point id from an OCPI location id.

    We publish locations as "<country><party>-<charge_point_id>", so anything a
    partner sends back carries that prefix. The single-location endpoint strips
    it; the commands endpoint did not, and matched the whole string against
    charge_point_id — so a START_SESSION quoting the location id we had just
    given out found no charger and was rejected.
    """
    if not location_id:
        return ""
    prefix = f"{os.getenv('OCPI_COUNTRY_CODE', 'MY')}{os.getenv('OCPI_PARTY_ID', 'PLG')}-"
    return location_id[len(prefix):] if location_id.startswith(prefix) else location_id


def _gun_from_evse_uid(evse_uid: Optional[str]) -> Optional[int]:
    """Which gun an EVSE uid refers to — uids end "-EVSE<n>"."""
    if not evse_uid:
        return None
    tail = str(evse_uid).rsplit("-EVSE", 1)
    if len(tail) == 2 and tail[1].isdigit():
        return int(tail[1])
    return None


def _tariff_id(charger) -> str:
    """Every charger prices independently, so every charger gets its own tariff."""
    return f"TARIFF-{charger.charge_point_id}"


def _build_tariff(charger, now: str) -> dict:
    """The OCPI tariff for one charger, from its own rate and idle settings.

    The tariffs endpoint used to read a `Pricing` table that is empty, so it
    emitted a single TARIFF-DEFAULT carrying ENERGY at a hardcoded RM0.50 —
    neither the per-charger rate the kiosk actually bills, nor the idle fee.
    Nothing referenced it either, since connectors carried no tariff_ids.

    Note the unit change: OCPI prices PARKING_TIME per hour, while we
    configure it per minute, so the rate is multiplied by 60. step_size 60
    keeps it billed in whole minutes, and the grace period becomes a
    min_duration restriction in seconds — free until it elapses, charged
    after.
    """
    energy_rate = float(charger.tariff_per_kwh) if charger.tariff_per_kwh is not None else 0.50
    elements = [
        {
            "price_components": [
                {"type": "ENERGY", "price": round(energy_rate, 4), "step_size": 1}
            ]
        }
    ]

    if getattr(charger, "idle_fee_enabled", False) and charger.idle_fee_per_min:
        per_hour = round(float(charger.idle_fee_per_min) * 60, 4)
        grace_seconds = int(charger.idle_grace_minutes or 0) * 60
        element = {
            "price_components": [
                {"type": "PARKING_TIME", "price": per_hour, "step_size": 60}
            ]
        }
        if grace_seconds:
            element["restrictions"] = {"min_duration": grace_seconds}
        elements.append(element)

    return {
        "id": _tariff_id(charger),
        "currency": "MYR",
        "country_code": os.getenv("OCPI_COUNTRY_CODE", "MY"),
        "party_id": os.getenv("OCPI_PARTY_ID", "PLG"),
        "elements": elements,
        "last_updated": now,
    }


_CONNECTOR_STANDARDS = {
    "ccs2": ("IEC_62196_T2_COMBO", "CABLE", "DC"),
    "ccs": ("IEC_62196_T2_COMBO", "CABLE", "DC"),
    "ccs1": ("IEC_62196_T1_COMBO", "CABLE", "DC"),
    "chademo": ("CHADEMO", "CABLE", "DC"),
    "gbt": ("GBT_DC", "CABLE", "DC"),
    "type 2": ("IEC_62196_T2", "SOCKET", "AC"),
    "type2": ("IEC_62196_T2", "SOCKET", "AC"),
    "iec_62196_t2": ("IEC_62196_T2", "SOCKET", "AC"),
    "type 1": ("IEC_62196_T1", "CABLE", "AC"),
    "type1": ("IEC_62196_T1", "CABLE", "AC"),
}


def _connector_spec(charger):
    """Describe a gun from what the charger record actually says.

    Every connector used to be published as a 7.36 kW single-phase Type 2
    socket regardless of the hardware, because the standard, format, power
    type, voltage and amperage were all written into the payload as
    constants. DC3001 is a 30 kW CCS2 DC unit and was advertised to roaming
    partners as slow AC with the wrong plug, so a driver filtering for CCS
    would never see it and a driver who did come would find a plug that does
    not fit their car.

    Where the record has no connector_type we keep the previous Type 2
    assumption, since that is what partners already hold and guessing DC for
    an unknown unit would be the more damaging error.
    """
    raw = (getattr(charger, "connector_type", None) or "").strip().lower()
    standard, fmt, current = _CONNECTOR_STANDARDS.get(raw, ("IEC_62196_T2", "SOCKET", "AC"))

    kw = getattr(charger, "max_power_kw", None)
    try:
        kw = float(kw) if kw else None
    except (TypeError, ValueError):
        kw = None

    if current == "DC":
        power_type = "DC"
        voltage, amperage = 400, 80
        max_w = int((kw or 50.0) * 1000)
        amperage = max(1, round(max_w / voltage))
    else:
        max_w = int((kw or 7.36) * 1000)
        # 22 kW and above on AC is three-phase in practice; below that a
        # single-phase 230 V supply is the safe description.
        if max_w >= 22000:
            power_type, voltage = "AC_3_PHASE", 400
            amperage = max(1, round(max_w / (voltage * 1.732)))
        else:
            power_type, voltage = "AC_1_PHASE", 230
            amperage = max(1, round(max_w / voltage))

    return standard, fmt, power_type, voltage, amperage, max_w


async def _attach_auth_reference(charger_id: int, auth_ref: str) -> None:
    """Record the partner's reference against the session this start creates.

    The row does not exist yet when the charger accepts, so this waits for it.
    The wait is awaited rather than slept through: this runs inside the OCPP
    connection's event loop, and a blocking sleep here would stall every other
    charger on the process for the duration.
    """
    from database import SessionLocal as _SL

    for _ in range(10):
        db = _SL()
        try:
            sess = (
                db.query(ChargingSession)
                .filter(
                    ChargingSession.charger_id == charger_id,
                    ChargingSession.status.in_(["pending", "active"]),
                    ChargingSession.authorization_reference.is_(None),
                )
                .order_by(ChargingSession.id.desc())
                .first()
            )
            if sess is not None:
                sess.authorization_reference = auth_ref[:64]
                db.commit()
                logger.info(
                    "[ocpi-commands] authorization_reference %s attached to session %s",
                    auth_ref, sess.id,
                )
                return
        except Exception as e:
            logger.warning("[ocpi-commands] could not attach authorization_reference: %s", e)
            return
        finally:
            db.close()
        await asyncio.sleep(1)

    logger.warning(
        "[ocpi-commands] no session appeared for charger %s, authorization_reference %s dropped",
        charger_id, auth_ref,
    )


def _build_evses(charger, loc_id: str, country: str, party_id: str, now: str) -> list:
    """One OCPI EVSE per gun.

    We used to publish a single EVSE per charge point carrying the charger-wide
    availability, so a two-gun unit appeared as one bay: gun 1 busy and gun 2
    free was advertised as fully occupied, and gun 2 did not exist as far as a
    roaming partner was concerned. Each gun is independently usable and needs
    its own EVSE with its own status.

    Gun 1 keeps the evse_id it has always been published under so nothing a
    partner already holds a reference to changes; further guns carry their
    connector number. The per-gun state comes from connector_status, falling
    back to the charger-wide value for a unit that has not reported per
    connector yet.
    """
    import json as _json

    conn_map = {}
    if getattr(charger, "connector_status", None):
        try:
            conn_map = _json.loads(charger.connector_status) or {}
        except Exception:
            conn_map = {}

    guns = max(int(getattr(charger, "number_of_connectors", 1) or 1), 1)
    for key in conn_map:
        if str(key).isdigit():
            guns = max(guns, int(key))

    _std, _fmt, _ptype, _volt, _amp, _maxw = _connector_spec(charger)

    # What the QR sticker on that gun actually encodes. Partners asked how a
    # scan maps to an EVSE; publishing the sticker contents lets them match a
    # scanned code to the EVSE without us agreeing a separate code list.
    sticker_base = os.getenv("QR_STICKER_BASE_URL", "https://charger.czeros.tech/pay")

    evses = []
    for n in range(1, guns + 1):
        state = conn_map.get(str(n)) or (charger.availability if guns == 1 else None)
        suffix = "" if n == 1 else f"*{n}"
        evses.append(
            EVSE(
                uid=f"{loc_id}-EVSE{n}",
                evse_id=f"{country}*{party_id}*E*{charger.charge_point_id}{suffix}",
                status=_ocpi_evse_status(state),
                physical_reference=(
                    f"{sticker_base}?charger={quote(str(charger.charge_point_id), safe='')}"
                    f"&connector={n}"
                ),
                connectors=[
                    Connector(
                        id=str(n),
                        standard=_std,
                        format=_fmt,
                        power_type=_ptype,
                        voltage=_volt,
                        amperage=_amp,
                        max_electric_power=_maxw,
                        # Without this an eMSP has no way to know what the
                        # connector costs — Voltality reported every connector
                        # arriving with no tariff attached.
                        tariff_ids=[_tariff_id(charger)],
                        last_updated=now,
                    )
                ],
                last_updated=now,
            )
        )
    return evses


def _publishable(query, cutoff: Optional[datetime] = None):
    """Restrict a Charger query to what may be published over OCPI.

    A roaming partner republishes whatever we hand them straight to drivers,
    so anything listed here has to be a charge point someone could actually
    drive to. The chargers table does not clear itself — it holds every unit
    that ever connected, including hundreds that reported once months ago —
    so publication is opt-out by staleness, with explicit operator overrides:

        is_public = True   → always published, even while offline
        is_public = False  → never published
        is_public = NULL   → published only if seen within the age window
    """
    if cutoff is None:
        cutoff = datetime.utcnow() - timedelta(days=_PUBLISH_MAX_AGE_DAYS)
    return query.filter(
        (Charger.is_public.is_(True))
        | (
            Charger.is_public.is_(None)
            & Charger.last_heartbeat.isnot(None)
            & (Charger.last_heartbeat >= cutoff)
        )
    )


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
def _ocpi_now() -> str:
    return _to_ocpi_datetime(datetime.utcnow())


def _build_location_dict(charger) -> dict:
    """One OCPI Location for a charger.

    Shared by the pull endpoints and by push, so a partner sees the same shape
    whichever way the data reaches it. Two builders would drift.
    """
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")
    loc_id = f"{country}{party_id}-{charger.charge_point_id}"
    now = _ocpi_now()
    return Location(
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
        evses=_build_evses(charger, loc_id, country, party_id, now),
        time_zone="Asia/Kuala_Lumpur",
        last_updated=now,
    ).model_dump()


@router.get("/2.2.1/locations", response_model=dict, dependencies=[Depends(_ocpi_auth)])
async def get_locations(
    request: Request,
    offset: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get list of charging locations (from chargers)."""
    chargers = (
        _publishable(db.query(Charger))
        .order_by(Charger.id)
        .offset(offset)
        .limit(limit or 100)
        .all()
    )
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")

    locations = [_build_location_dict(c) for c in chargers]

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
    # Location ids are built as "{country}{party}-{charge_point_id}" — one
    # dash, whatever the charge point id contains. The previous parse split on
    # dashes and took the third field, which only lined up when the charge
    # point id happened to contain a dash itself: "MYPLG-DC3001" has two
    # fields, so it fell through to matching the whole string against
    # charge_point_id and never found anything. Strip the known prefix instead.
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")
    prefix = f"{country}{party_id}-"
    cp_id = location_id[len(prefix):] if location_id.startswith(prefix) else location_id
    # Same publication rule as the list endpoint. A charger we deliberately do
    # not list must not be reachable by guessing its id either, or a partner
    # could cache it and keep showing a charge point we withdrew.
    charger = (
        _publishable(db.query(Charger))
        .filter(Charger.charge_point_id == cp_id)
        .first()
    )
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
    evses = _build_evses(charger, loc_id, country, party_id, now)
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
        evses=evses,
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
def _build_session_dict(sess) -> Optional[dict]:
    """One OCPI Session. Shared by the pull endpoint and by push."""
    charger = sess.charger
    if not charger:
        return None
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")
    loc_id = f"{country}{party_id}-{charger.charge_point_id}"
    gun = sess.evse_id or sess.connector_id or 1
    return {
        "id": str(sess.transaction_id),
        "start_datetime": _to_ocpi_datetime(sess.start_time),
        "end_datetime": _to_ocpi_datetime(sess.stop_time) if sess.stop_time else None,
        "kwh": float(sess.energy_consumed or 0),
        "cdr_token": {
            "uid": sess.user_id or "UNKNOWN",
            "type": "APP_USER",
            "contract_id": sess.user_id or "UNKNOWN",
        },
        "auth_method": "AUTH_REQUEST",
        "location_id": loc_id,
        "evse_uid": f"{loc_id}-EVSE{gun}",
        "connector_id": str(gun),
        "currency": "MYR",
        "status": "ACTIVE" if sess.status == "active" else "COMPLETED",
        "authorization_reference": sess.authorization_reference,
        "last_updated": _to_ocpi_datetime(sess.stop_time or sess.start_time),
    }


def _build_cdr_dict(sess) -> Optional[dict]:
    """One OCPI CDR. Shared by the pull endpoint and by push."""
    charger = sess.charger
    if not charger or not sess.stop_time:
        return None
    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party_id = os.getenv("OCPI_PARTY_ID", "PLG")
    loc_id = f"{country}{party_id}-{charger.charge_point_id}"

    energy = float(sess.energy_consumed or 0)
    start_time = sess.start_time or datetime.utcnow()
    stop_time = sess.stop_time or datetime.utcnow()
    duration_h = (stop_time - start_time).total_seconds() / 3600

    price_per_kwh = float(charger.tariff_per_kwh) if charger.tariff_per_kwh is not None else 0.50
    energy_cost = round(energy * price_per_kwh, 2)

    idle_minutes = int(sess.idle_minutes or 0)
    idle_cost = 0.0
    if idle_minutes and charger.idle_fee_enabled and charger.idle_fee_per_min:
        idle_cost = round(idle_minutes * float(charger.idle_fee_per_min), 2)
    total_cost = round(energy_cost + idle_cost, 2)

    # Prefer evse_id: on 2.0.1 every gun reports connector 1, so connector_id
    # alone puts a gun 2 charge on gun 1.
    gun = int(sess.evse_id or sess.connector_id or 1)

    periods = [{
        "start_datetime": _to_ocpi_datetime(start_time),
        "dimensions": [{"type": "ENERGY", "volume": energy}],
    }]
    if idle_minutes:
        periods.append({
            "start_datetime": _to_ocpi_datetime(sess.idle_started_at or stop_time),
            "dimensions": [{"type": "PARKING_TIME", "volume": round(idle_minutes / 60, 4)}],
        })

    return {
        "id": str(sess.transaction_id),
        "start_datetime": _to_ocpi_datetime(start_time),
        "end_datetime": _to_ocpi_datetime(stop_time),
        "auth_id": sess.user_id or "UNKNOWN",
        "auth_method": "AUTH_REQUEST",
        "location_id": loc_id,
        "evse_uid": f"{loc_id}-EVSE{gun}",
        "connector_id": str(gun),
        "currency": "MYR",
        "tariff_id": _tariff_id(charger),
        "total_cost": total_cost,
        "total_energy": energy,
        "total_time": round(duration_h, 4),
        "total_parking_time": round(idle_minutes / 60, 4) if idle_minutes else 0,
        "cdr_token": {
            "uid": sess.user_id or "UNKNOWN",
            "type": "APP_USER",
            "contract_id": sess.user_id or "UNKNOWN",
        },
        "authorization_reference": sess.authorization_reference,
        "charging_periods": periods,
        "last_updated": _to_ocpi_datetime(stop_time),
    }


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

    result = [d for d in (_build_session_dict(s) for s in sessions) if d]

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

    result = [d for d in (_build_cdr_dict(s) for s in sessions) if d]

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
    """Get tariffs — one per published charger, matching what it actually bills.

    Previously this read the `Pricing` table, which is empty, so every partner
    received a single TARIFF-DEFAULT at a hardcoded RM0.50 with only an ENERGY
    component. That was neither the rate the kiosk charges nor did it carry the
    idle fee, and no connector referenced it.
    """
    chargers = (
        _publishable(db.query(Charger))
        .order_by(Charger.id)
        .offset(offset)
        .limit(limit or 100)
        .all()
    )
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    result = [_build_tariff(c, now) for c in chargers]
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
        cp_id = _charger_id_from_location(location_id)
        evse_uid = body.get("evse_uid")
        # Prefer an explicit connector_id; otherwise take the gun from the EVSE
        # uid, so a start aimed at gun 2 does not silently begin on gun 1.
        connector_id = int(body.get("connector_id") or _gun_from_evse_uid(evse_uid) or 1)
        token = (body.get("token") or {}).get("uid") or "ROAMING_USER"
        charger = db.query(Charger).filter(Charger.charge_point_id == cp_id).first()
        if not charger:
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "REJECTED", "timeout": 0},
            }
        cp = get_active_charge_point(cp_id)
        if cp is None:
            asyncio.create_task(_post_command_result(response_url, "EVSE_INOPERATIVE", "Charger offline"))
            return {
                "status_code": 1000, "status_message": "Success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {"result": "ACCEPTED", "timeout": 30},
            }

        # The partner's own reference for this start. Keeping it lets us echo
        # it back on the session, which is the only way the partner can tie the
        # session it asked for to the session we report.
        auth_ref = body.get("authorization_reference")

        async def _dispatch_start():
            try:
                resp = await cp.remote_start_transaction(connector_id=connector_id, id_tag=token)
                accepted = bool(resp and getattr(resp, "status", "").lower() == "accepted")
                if accepted and auth_ref:
                    await _attach_auth_reference(charger.id, auth_ref)
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
def _save_partner(url: str, token: str, roles: list) -> None:
    """Persist a partner's credentials from the registration handshake.

    Without this we could receive a partner's traffic but never initiate any of
    our own: the handshake carries the token we must present when calling them,
    and it was only ever written to the log truncated, so pushing anything back
    was impossible. Keyed on (country_code, party_id) so a repeat handshake
    rotates the token in place rather than leaving a stale row behind it.
    """
    role = (roles or [{}])[0]
    cc = (role.get("country_code") or "??")[:2]
    pid = (role.get("party_id") or "???")[:3]
    now = datetime.utcnow()

    db = SessionLocal()
    try:
        row = (
            db.query(OcpiPartner)
            .filter(OcpiPartner.country_code == cc, OcpiPartner.party_id == pid)
            .first()
        )
        if row is None:
            row = OcpiPartner(country_code=cc, party_id=pid, registered_at=now)
            db.add(row)
        row.role = (role.get("role") or "")[:16] or None
        row.business_name = ((role.get("business_details") or {}).get("name") or "")[:128] or None
        row.versions_url = url[:512]
        row.token = token[:256]
        row.last_updated = now
        db.commit()
        logger.info("[ocpi-credentials] credentials stored for %s/%s", cc, pid)
    except Exception as e:
        db.rollback()
        logger.error("[ocpi-credentials] could not store partner credentials: %s", e)
    finally:
        db.close()


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

    _save_partner(partner_url, partner_token, partner_roles)
    # A new token means the old discovery cache may point at a partner we can
    # no longer authenticate against.
    try:
        from .push import invalidate_endpoints
        invalidate_endpoints()
    except Exception:
        pass

    # The token is a credential, so only its prefix goes to the log. The value
    # itself lives in ocpi_partners.
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

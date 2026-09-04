"""OCPI push (the Receiver side of a partner's interface).

Partners were pulling every module on a short interval because we published
nothing: roughly thirteen thousand GETs every two days across locations,
tariffs, sessions and CDRs. This sends changes as they happen instead.

Two properties matter more than completeness here:

  * It must never slow the OCPP path. Call sites hand work to a queue and
    return; a single worker drains it. A partner whose endpoint is slow or
    down therefore delays nothing but its own updates.
  * It must never raise into a caller. Every failure is logged and dropped
    after its retries. Roaming data going stale is a problem; a charger losing
    its session because a partner's API timed out is a much worse one.

Endpoint discovery follows OCPI: the handshake gives us the partner's versions
URL, from which we read the 2.2.1 version detail and its module endpoints. The
result is cached, since it changes about as often as the partnership does.
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_QUEUE: "Optional[asyncio.Queue]" = None
_WORKER: "Optional[asyncio.Task]" = None

# Discovered module URLs per partner id, cleared when a handshake rotates them.
_ENDPOINTS: Dict[int, Dict[str, str]] = {}

_MAX_ATTEMPTS = 3
_TIMEOUT = 15.0


# ── plumbing ──────────────────────────────────────────────────────────────

def enqueue(kind: str, ref: Any) -> None:
    """Ask for something to be pushed. Safe to call from anywhere, never blocks.

    Silently does nothing if the worker is not running, which is the case in
    tests and in any process that is not the API. A dropped push is not worth
    an exception on the OCPP path.
    """
    q = _QUEUE
    if q is None:
        return
    try:
        q.put_nowait((kind, ref))
    except Exception:  # queue full — drop rather than block a charger
        logger.warning("[ocpi-push] queue full, dropped %s %s", kind, ref)


async def start_worker() -> None:
    global _QUEUE, _WORKER
    if _WORKER is not None:
        return
    _QUEUE = asyncio.Queue(maxsize=2000)
    _WORKER = asyncio.create_task(_run())
    logger.info("[ocpi-push] worker started")


async def _run() -> None:
    while True:
        try:
            kind, ref = await _QUEUE.get()
        except asyncio.CancelledError:
            return
        try:
            await _dispatch(kind, ref)
        except Exception as e:
            logger.error("[ocpi-push] %s %s failed: %s", kind, ref, e, exc_info=True)
        finally:
            _QUEUE.task_done()


# ── partner discovery ─────────────────────────────────────────────────────

def _partners() -> list:
    from database import OcpiPartner, SessionLocal

    db = SessionLocal()
    try:
        return db.query(OcpiPartner).all()
    except Exception as e:
        logger.error("[ocpi-push] cannot read partners: %s", e)
        return []
    finally:
        db.close()


async def _endpoints_for(partner) -> Dict[str, str]:
    """Module URL per identifier for one partner, discovered once and cached."""
    cached = _ENDPOINTS.get(partner.id)
    if cached:
        return cached

    import httpx

    headers = {"Authorization": f"Token {partner.token}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(partner.versions_url, headers=headers)
            r.raise_for_status()
            versions = (r.json() or {}).get("data") or []
            detail_url = next(
                (v.get("url") for v in versions if str(v.get("version", "")).startswith("2.2")),
                None,
            )
            if not detail_url:
                logger.warning("[ocpi-push] %s/%s exposes no 2.2.x version",
                               partner.country_code, partner.party_id)
                return {}

            r = await client.get(detail_url, headers=headers)
            r.raise_for_status()
            eps = ((r.json() or {}).get("data") or {}).get("endpoints") or []
    except Exception as e:
        logger.warning("[ocpi-push] discovery failed for %s/%s: %s",
                       partner.country_code, partner.party_id, e)
        return {}

    # A partner publishes both roles; we push to the one that receives.
    found = {}
    for ep in eps:
        ident = ep.get("identifier")
        role = (ep.get("role") or "RECEIVER").upper()
        if ident and role == "RECEIVER":
            found[ident] = ep.get("url")
    _ENDPOINTS[partner.id] = found
    logger.info("[ocpi-push] discovered %s endpoints for %s/%s: %s",
                len(found), partner.country_code, partner.party_id, sorted(found))
    return found


def invalidate_endpoints() -> None:
    """Forget discovered URLs, called when a handshake rotates credentials."""
    _ENDPOINTS.clear()


# ── transport ─────────────────────────────────────────────────────────────

async def _send(partner, url: str, payload: dict, method: str = "PUT") -> bool:
    import httpx

    headers = {
        "Authorization": f"Token {partner.token}",
        "Content-Type": "application/json",
        "X-Request-ID": datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "OCPI-from-country-code": os.getenv("OCPI_COUNTRY_CODE", "MY"),
        "OCPI-from-party-id": os.getenv("OCPI_PARTY_ID", "PLG"),
        "OCPI-to-country-code": partner.country_code,
        "OCPI-to-party-id": partner.party_id,
    }
    delay = 2
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.request(method, url, json=payload, headers=headers)
            if r.status_code < 300:
                return True
            # 4xx will not improve on retry; 5xx might.
            if r.status_code < 500:
                logger.warning("[ocpi-push] %s %s refused: %s %s",
                               method, url, r.status_code, r.text[:160])
                return False
            logger.warning("[ocpi-push] %s %s attempt %s: %s", method, url, attempt, r.status_code)
        except Exception as e:
            logger.warning("[ocpi-push] %s %s attempt %s: %s", method, url, attempt, e)
        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(delay)
            delay *= 3
    return False


# ── payload builders ──────────────────────────────────────────────────────
# Built from the same helpers the pull endpoints use, so a partner cannot see
# one shape when it polls and another when we push.

def _location_payload(charge_point_id: str) -> Optional[dict]:
    from database import Charger, SessionLocal
    from .router import _build_location_dict

    db = SessionLocal()
    try:
        c = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        return _build_location_dict(c) if c else None
    finally:
        db.close()


def _tariff_payload(charge_point_id: str) -> Optional[dict]:
    from database import Charger, SessionLocal
    from .router import _build_tariff, _ocpi_now

    db = SessionLocal()
    try:
        c = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
        return _build_tariff(c, _ocpi_now()) if c else None
    finally:
        db.close()


def _session_payload(session_id: int) -> Optional[dict]:
    from database import ChargingSession, SessionLocal
    from .router import _build_session_dict

    db = SessionLocal()
    try:
        s = db.query(ChargingSession).filter(ChargingSession.id == session_id).first()
        return _build_session_dict(s) if s else None
    finally:
        db.close()


def _cdr_payload(session_id: int) -> Optional[dict]:
    from database import ChargingSession, SessionLocal
    from .router import _build_cdr_dict

    db = SessionLocal()
    try:
        s = db.query(ChargingSession).filter(ChargingSession.id == session_id).first()
        return _build_cdr_dict(s) if s else None
    finally:
        db.close()


# ── dispatch ──────────────────────────────────────────────────────────────

async def _dispatch(kind: str, ref: Any) -> None:
    partners = _partners()
    if not partners:
        return  # nobody has registered; nothing to do and nothing to warn about

    country = os.getenv("OCPI_COUNTRY_CODE", "MY")
    party = os.getenv("OCPI_PARTY_ID", "PLG")

    for partner in partners:
        eps = await _endpoints_for(partner)
        if not eps:
            continue

        if kind == "location":
            base, payload = eps.get("locations"), _location_payload(ref)
            if base and payload:
                await _send(partner, f"{base.rstrip('/')}/{country}/{party}/{payload['id']}", payload)

        elif kind == "tariff":
            base, payload = eps.get("tariffs"), _tariff_payload(ref)
            if base and payload:
                await _send(partner, f"{base.rstrip('/')}/{country}/{party}/{payload['id']}", payload)

        elif kind == "session":
            base, payload = eps.get("sessions"), _session_payload(ref)
            if base and payload:
                await _send(partner, f"{base.rstrip('/')}/{country}/{party}/{payload['id']}", payload)

        elif kind == "cdr":
            # CDRs are POSTed, not PUT: they are immutable records, and the
            # receiver assigns their location.
            base, payload = eps.get("cdrs"), _cdr_payload(ref)
            if base and payload:
                await _send(partner, base.rstrip("/"), payload, method="POST")

        else:
            logger.warning("[ocpi-push] unknown kind %r", kind)

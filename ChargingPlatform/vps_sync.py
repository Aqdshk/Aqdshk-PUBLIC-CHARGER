"""
VPS Sync Module — Edge Server (Banana Pi) → VPS

Pushes charger status, session, and meter data to the VPS after local OCPP events.
Only active when LOCAL_SERVER_MODE=true in .env — no-op on the VPS itself.

Usage (from ocpp_server.py):
    from vps_sync import sync_charger, sync_session_start, sync_session_stop, sync_meter_value
    sync_charger(charge_point_id, status="online", availability="available", ...)
"""
import asyncio
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

VPS_API_URL    = os.getenv("VPS_API_URL", "").rstrip("/")
VPS_SYNC_TOKEN = os.getenv("VPS_SYNC_TOKEN", "")
LOCAL_SERVER_MODE = os.getenv("LOCAL_SERVER_MODE", "false").lower() == "true"


async def _push(endpoint: str, data: Dict[str, Any]) -> bool:
    """POST data to VPS sync endpoint. Returns True on success."""
    if not VPS_API_URL or not VPS_SYNC_TOKEN:
        logger.debug("VPS sync skipped — VPS_API_URL or VPS_SYNC_TOKEN not set")
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{VPS_API_URL}/api/edge/sync/{endpoint}",
                json=data,
                headers={"Authorization": f"Bearer {VPS_SYNC_TOKEN}"},
            )
            if resp.status_code == 200:
                logger.debug(f"VPS sync OK [{endpoint}]")
                return True
            logger.warning(f"VPS sync failed [{endpoint}]: HTTP {resp.status_code} — {resp.text[:120]}")
            return False
    except Exception as exc:
        logger.warning(f"VPS sync error [{endpoint}]: {exc}")
        return False


def _fire(endpoint: str, data: Dict[str, Any]):
    """Schedule an async push as a fire-and-forget task (safe from any context)."""
    if not LOCAL_SERVER_MODE:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_push(endpoint, data))
        else:
            logger.warning("VPS sync: no running event loop — skipping push")
    except Exception as exc:
        logger.warning(f"VPS sync schedule error: {exc}")


# ─── Public helpers ────────────────────────────────────────────────────────────

def sync_charger(charge_point_id: str, **kwargs):
    """Push charger status / metadata update to VPS."""
    _fire("charger-status", {"charge_point_id": charge_point_id, **kwargs})


def sync_session_start(charge_point_id: str, transaction_id: int, **kwargs):
    """Push new charging session to VPS."""
    _fire("session-start", {
        "charge_point_id": charge_point_id,
        "transaction_id": transaction_id,
        **kwargs,
    })


def sync_session_stop(transaction_id: int, **kwargs):
    """Push completed session to VPS."""
    _fire("session-stop", {"transaction_id": transaction_id, **kwargs})


def sync_meter_value(charge_point_id: str, **kwargs):
    """Push a meter value sample to VPS."""
    _fire("meter-value", {"charge_point_id": charge_point_id, **kwargs})

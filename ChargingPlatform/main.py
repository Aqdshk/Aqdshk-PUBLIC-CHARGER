"""
PlagSini EV — Application Entry Point

Starts:
  1. FastAPI server (port 8000) — dashboard, API, static files
  2. OCPP WebSocket server (port 9000) — charger connections
  3. Orphan session watchdog — background task to close stale sessions

Bootstrap: creates default admin & staff if env vars set and DB empty.

Usage:
    python main.py
    # Or: uvicorn api:app --host 0.0.0.0 --port 8000 (API only, no OCPP)
"""
import asyncio
import logging
import os
import threading

import uvicorn

# Reduce websockets.server log noise (bots/scanners → handshake fails). Must run before OCPP.
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)

# ─── WebSockets Compatibility ─────────────────────────────────────────────
# Support both websockets>=13 (asyncio.server) and older (server)
# OCPP 1.6 uses WebSocket subprotocol "ocpp1.6"
try:
    from websockets.asyncio.server import serve  # websockets >= 13.0
except ImportError:
    from websockets.server import serve  # websockets < 13.0

from api import app
from database import init_db, SessionLocal, User, Wallet, SupportStaff
from ocpp_server import on_connect, orphan_session_watchdog, scheduled_charging_worker

logger = logging.getLogger(__name__)


# ─── Bootstrap: Default Admin & Staff ──────────────────────────────────────

def create_default_admin() -> None:
    """
    Create default admin user only if no admin exists yet.
    Requires ADMIN_EMAIL and ADMIN_PASSWORD in env. Skips if either is empty.
    """
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
        admin_name = os.getenv("ADMIN_NAME", "Admin")

        if not admin_email or not admin_password:
            logger.warning(
                "ADMIN_EMAIL or ADMIN_PASSWORD not set in environment — skipping default admin creation. "
                "Set these in your .env file before first run."
            )
            return

        if len(admin_password) < 8:
            logger.error(
                "ADMIN_PASSWORD is too short (must be at least 8 characters) — skipping admin creation."
            )
            return

        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            logger.info(f"Admin user already exists: {existing.email} — skipping creation.")
            return

        admin = User(
            email=admin_email,
            name=admin_name,
            is_active=True,
            is_verified=True,
            is_admin=True,
        )
        admin.set_password(admin_password)
        db.add(admin)
        db.flush()

        wallet = Wallet(user_id=admin.id, balance=0.0, points=0)
        db.add(wallet)
        db.commit()

        logger.info(f"Default admin created: {admin_email}")
        logger.info("  ⚠️  Please change the default admin password after first login!")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating default admin: {e}")
    finally:
        db.close()


def create_default_staff() -> None:
    """
    Create default staff admin if support_staff table is empty.
    Requires STAFF_EMAIL and STAFF_PASSWORD in env. Skips if either is empty.
    """
    db = SessionLocal()
    try:
        staff_email = os.getenv("STAFF_EMAIL", "").strip()
        staff_password = os.getenv("STAFF_PASSWORD", "").strip()

        if not staff_email or not staff_password:
            logger.warning(
                "STAFF_EMAIL or STAFF_PASSWORD not set in environment — skipping default staff creation."
            )
            return

        if len(staff_password) < 8:
            logger.error(
                "STAFF_PASSWORD is too short (must be at least 8 characters) — skipping staff creation."
            )
            return

        staff_name = os.getenv("STAFF_NAME", "Ahmad")

        existing = db.query(SupportStaff).filter(SupportStaff.email == staff_email).first()
        if existing:
            logger.info(f"Staff admin exists: {existing.email}")
            return

        staff = SupportStaff(
            name=staff_name,
            email=staff_email,
            department="IT",
            role="admin",
            max_tickets=20,
        )
        staff.set_password(staff_password)
        db.add(staff)
        db.commit()

        logger.info(f"Default staff admin created: {staff_email}")
        logger.info("  ⚠️  Please change the default staff password after first login!")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating default staff: {e}")
    finally:
        db.close()


# ─── OCPP WebSocket Server ─────────────────────────────────────────────────

async def ocpp_server() -> None:
    """
    Start OCPP WebSocket server on ws://0.0.0.0:9000.
    Runs orphan_session_watchdog every 600s to close stale charging sessions.
    """
    logger.info("Starting OCPP WebSocket server on ws://0.0.0.0:9000")
    async with serve(
        on_connect,
        "0.0.0.0",
        9000,
        subprotocols=["ocpp1.6"],
        ping_interval=60,   # send WS ping every 60s — detects dead/powered-off chargers
        ping_timeout=30,    # if no pong within 30s, close connection
        close_timeout=10,
        compression=None,
    ):
        asyncio.create_task(orphan_session_watchdog(interval_seconds=600))
        asyncio.create_task(scheduled_charging_worker(interval_seconds=60))
        await asyncio.Future()  # run forever


# ─── Main Entry ────────────────────────────────────────────────────────────

def start_servers() -> None:
    """
    Bootstrap and start both servers:
    1. Init DB, create default admin/staff
    2. Start OCPP WebSocket in background thread
    3. Run FastAPI on port 8000
    """
    logging.basicConfig(level=logging.INFO)

    # 1. Database init & bootstrap
    init_db()
    logger.info("Database initialized")
    create_default_admin()
    create_default_staff()

    # 2. OCPP server in background (daemon thread)
    # Daemon=True so it exits when main process exits
    ocpp_thread = threading.Thread(
        target=lambda: asyncio.run(ocpp_server()), daemon=True
    )
    ocpp_thread.start()
    logger.info("OCPP server started in background thread")

    # 3. FastAPI (blocks until shutdown)
    logger.info("Starting FastAPI server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start_servers()

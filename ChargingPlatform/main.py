import asyncio
import logging
import os
import threading

import uvicorn

try:
    from websockets.asyncio.server import serve  # websockets >= 13.0
except ImportError:
    from websockets.server import serve  # websockets < 13.0

from api import app
from database import init_db, SessionLocal, User, Wallet, SupportStaff
from ocpp_server import on_connect

logger = logging.getLogger(__name__)


def create_default_admin():
    """Create default admin user if no admin exists, or update if credentials changed."""
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "1@admin.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "1")
        admin_name = os.getenv("ADMIN_NAME", "Admin")
        
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            existing.set_password(admin_password)
            existing.is_admin = True
            db.commit()
            logger.info(f"Admin user updated: {existing.email}")
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


def create_default_staff():
    """Create default staff admin if support_staff table is empty."""
    db = SessionLocal()
    try:
        staff_email = os.getenv("STAFF_EMAIL", "ahmad@plagsini.com")
        staff_password = os.getenv("STAFF_PASSWORD", "admin123")
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


async def ocpp_server():
    """Start OCPP WebSocket server."""
    logger.info("Starting OCPP WebSocket server on ws://0.0.0.0:9000")
    async with serve(
        on_connect,
        "0.0.0.0",
        9000,
        subprotocols=["ocpp1.6"],
        ping_interval=None,
        close_timeout=10,
        compression=None,
    ):
        await asyncio.Future()  # run forever


def start_servers():
    """Start both FastAPI and OCPP servers."""
    logging.basicConfig(level=logging.INFO)

    init_db()
    logger.info("Database initialized")
    
    create_default_admin()
    create_default_staff()
    
    ocpp_thread = threading.Thread(
        target=lambda: asyncio.run(ocpp_server()), daemon=True
    )
    ocpp_thread.start()
    logger.info("OCPP server started in background thread")
    
    logger.info("Starting FastAPI server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start_servers()

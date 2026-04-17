"""
PlagSini EV — Web Push Notification Service (PWA)

Uses VAPID + Web Push Protocol (RFC 8030) — no Firebase needed.

Setup:
  1. Generate VAPID keys once:
       python3 -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.private_key.private_bytes_raw().hex()); print(v.public_key.public_bytes_raw().hex())"
     Or use: python3 push_service.py --generate-keys
  2. Add to .env:
       VAPID_PRIVATE_KEY=<hex>
       VAPID_PUBLIC_KEY=<hex>
       VAPID_CLAIMS_EMAIL=mailto:admin@plagsini.com

Usage:
  from push_service import send_push, send_push_to_user
  await send_push(subscription_dict, title="Cas Selesai", body="Kereta anda dah penuh!")
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY",  "")
VAPID_EMAIL       = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@plagsini.com")


def get_vapid_public_key() -> str:
    """Return VAPID public key for frontend subscription."""
    return VAPID_PUBLIC_KEY


async def send_push(
    subscription: dict,
    title: str,
    body: str,
    icon: str = "/icons/Icon-192.png",
    url: str   = "/",
    tag: str   = "plagsini-ev",
) -> bool:
    """
    Send a Web Push notification to a single browser subscription.

    subscription: {
        "endpoint": "https://...",
        "keys": {"p256dh": "...", "auth": "..."}
    }
    """
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not set — push notification skipped")
        return False
    try:
        from pywebpush import webpush, WebPushException
        payload = json.dumps({
            "title": title,
            "body":  body,
            "icon":  icon,
            "url":   url,
            "tag":   tag,
        })
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_EMAIL},
        )
        return True
    except Exception as exc:
        logger.warning(f"Web push failed: {exc}")
        return False


async def send_push_to_user(
    user_id: int,
    title: str,
    body: str,
    db=None,
    **kwargs,
) -> int:
    """Send push to ALL browser subscriptions of a user. Returns count sent."""
    if db is None:
        return 0
    try:
        from database import PushSubscription
        subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
        sent = 0
        dead = []
        for s in subs:
            sub_dict = {
                "endpoint": s.endpoint,
                "keys": {"p256dh": s.p256dh, "auth": s.auth},
            }
            ok = await send_push(sub_dict, title, body, **kwargs)
            if ok:
                sent += 1
            else:
                dead.append(s.id)
        # Clean up dead subscriptions
        if dead:
            db.query(PushSubscription).filter(PushSubscription.id.in_(dead)).delete(synchronize_session=False)
            db.commit()
        return sent
    except Exception as exc:
        logger.error(f"send_push_to_user error: {exc}")
        return 0


# ─── CLI helper ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--generate-keys" in sys.argv:
        try:
            from py_vapid import Vapid
            v = Vapid()
            v.generate_keys()
            priv = v.private_key.private_bytes_raw().hex()
            pub  = v.public_key.public_bytes_raw().hex()
            print("Add these to your .env:")
            print(f"VAPID_PRIVATE_KEY={priv}")
            print(f"VAPID_PUBLIC_KEY={pub}")
            print(f"VAPID_CLAIMS_EMAIL=mailto:admin@plagsini.com")
        except ImportError:
            print("Run: pip install pywebpush py-vapid")

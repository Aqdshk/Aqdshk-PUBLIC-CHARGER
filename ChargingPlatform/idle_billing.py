"""Idle fee arithmetic, in one place.

The same accrual was written out three times — in ocpp_server's
StopTransaction handler, in api.py's stop fallback, and again inside the OCPI
CDR builder — and the three copies had already drifted: two of them ran to
stop_time and one gated the whole thing on hold_amount_rm, so a roaming
session never accrued anything.

The accrual window is idle_started_at to the unplug, not to stop_time. A stop
from the app or from a roaming partner closes the transaction the moment it is
requested, so measuring to stop_time charged nothing for a car that stayed in
the bay afterwards, which is the one case the fee exists to discourage.
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Tuple

_MYT_OFFSET = timedelta(hours=8)

# How long a CDR waits for a cable that may never come out. A charger that
# goes offline mid-session, or a driver who leaves the plug in overnight,
# must not hold a partner's billing record open indefinitely.
_DEFAULT_HOLD_CAP_MINUTES = 180


def now_myt() -> datetime:
    """Server clock as Malaysia wall time, naive — the session/meter convention."""
    return (datetime.now(timezone.utc) + _MYT_OFFSET).replace(tzinfo=None)


def hold_cap_minutes() -> int:
    try:
        return int(os.getenv("IDLE_CDR_HOLD_CAP_MINUTES", _DEFAULT_HOLD_CAP_MINUTES))
    except ValueError:
        return _DEFAULT_HOLD_CAP_MINUTES


def idle_end(sess, now: Optional[datetime] = None) -> Optional[datetime]:
    """The instant idle accrual stops for this session.

    The unplug when we have seen it. Otherwise the session is still blocking
    the bay, so accrual runs to now, capped so that a charger which never
    reports Available cannot bill forever.
    """
    if getattr(sess, "unplugged_at", None):
        return sess.unplugged_at
    if not sess.stop_time:
        return None
    now = now or now_myt()
    return min(now, sess.stop_time + timedelta(minutes=hold_cap_minutes()))


def compute_idle(sess, charger, now: Optional[datetime] = None) -> Tuple[int, float]:
    """Chargeable idle minutes and the fee for them, after the grace period."""
    if not charger or not charger.idle_fee_enabled:
        return 0, 0.0

    start = sess.idle_started_at
    end = idle_end(sess, now)
    if not start or not end or end <= start:
        return 0, 0.0

    elapsed = (end - start).total_seconds() / 60.0
    past_grace = max(0.0, elapsed - float(charger.idle_grace_minutes or 0))
    minutes = int(past_grace)
    fee = round(minutes * float(charger.idle_fee_per_min or 0), 2)
    return minutes, fee


def finalize_idle(sess, charger, now: Optional[datetime] = None) -> Tuple[int, float]:
    """Write the accrual onto the session. Returns what was written."""
    minutes, fee = compute_idle(sess, charger, now)
    sess.idle_minutes = minutes
    sess.idle_fee_amount = Decimal(str(fee))
    return minutes, fee


def awaiting_unplug(sess, charger, now: Optional[datetime] = None) -> bool:
    """True while the session lifecycle has not actually finished.

    Deliberately not gated on idle_fee_enabled. The question is whether the
    session is over, not whether we are charging for it: a partner tracks the
    session until the cable comes out and reconciles its own total against our
    CDR, so a CDR issued at stop is a record of a session that is still
    running whether or not any money attaches to the remaining minutes. Gating
    this on the fee also made the behaviour differ per charger, which is worse
    than either answer applied consistently.
    """
    if getattr(sess, "unplugged_at", None) or not sess.stop_time:
        return False
    now = now or now_myt()
    return now < sess.stop_time + timedelta(minutes=hold_cap_minutes())

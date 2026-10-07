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

import math
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Tuple

_MYT_OFFSET = timedelta(hours=8)

# The billing block for parking time, in seconds, and the value we publish as
# the PARKING_TIME component's step_size. OCPI bills in whole blocks and rounds
# a partial block up: "if 6 minutes were used, 10 minutes will be billed" for a
# step_size of 300. Both numbers have to come from here, because a tariff that
# advertises one block size while the CDR bills another is a dispute waiting to
# happen.
PARKING_STEP_SECONDS = 60


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
    """Billable idle minutes and the fee for them, after the grace period.

    The time past grace is billed in whole blocks of PARKING_STEP_SECONDS, with
    a partial block rounded up, which is what step_size means in OCPI. We used
    to truncate instead: Voltality's session 449 idled 540.12 seconds, 240.12 of
    them past grace, and we billed four blocks where the tariff we publish says
    five. Truncating also meant anything under a minute past grace was free, so
    a charger could be blocked repeatedly at no cost.

    The returned minutes are the billed quantity, not the measured one, so the
    CDR's parking dimension multiplied by the tariff gives exactly the cost we
    charged.
    """
    if not charger or not charger.idle_fee_enabled:
        return 0, 0.0

    start = sess.idle_started_at
    end = idle_end(sess, now)
    if not start or not end or end <= start:
        return 0, 0.0

    elapsed_s = (end - start).total_seconds()
    grace_s = float(charger.idle_grace_minutes or 0) * 60.0
    chargeable_s = max(0.0, elapsed_s - grace_s)
    if chargeable_s <= 0:
        return 0, 0.0

    blocks = math.ceil(chargeable_s / PARKING_STEP_SECONDS)
    minutes = int(blocks * PARKING_STEP_SECONDS / 60)
    fee = round(minutes * float(charger.idle_fee_per_min or 0), 2)
    return minutes, fee


def finalize_idle(sess, charger, now: Optional[datetime] = None) -> Tuple[int, float]:
    """Write the accrual onto the session. Returns what was written."""
    minutes, fee = compute_idle(sess, charger, now)
    sess.idle_minutes = minutes
    sess.idle_fee_amount = Decimal(str(fee))
    return minutes, fee


def settle_unplug(db, charger, now: Optional[datetime] = None):
    """Close out the session this charger just released the cable on.

    Called from both OCPP stacks, because "the cable came out" arrives as a
    different message on each and the billing consequence is identical.
    Returns the session that was settled, or None if nothing was waiting.
    """
    from database import ChargingSession

    sess = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.charger_id == charger.id,
            ChargingSession.status.in_(("completed", "stopped", "interrupted")),
            ChargingSession.stop_time.isnot(None),
            ChargingSession.unplugged_at.is_(None),
        )
        .order_by(ChargingSession.stop_time.desc())
        .first()
    )
    if sess is None:
        return None

    sess.unplugged_at = now or now_myt()
    # Money already moved on the kiosk flow. Re-billing here would settle
    # against a figure the customer was never shown and cannot be refunded a
    # second time, so those sessions only record when the cable came out.
    if sess.refund_status in (None, "", "not_required"):
        finalize_idle(sess, charger, now)
    return sess


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

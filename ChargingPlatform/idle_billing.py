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


def measured_idle_seconds(sess, charger=None, now: Optional[datetime] = None) -> float:
    """How long the EV sat without charging, before any grace is applied.

    This is what OCPI's total_parking_time and the PARKING_TIME dimension mean:
    the duration the EV was not charging, not the duration we billed for. We
    used to publish the billed minutes in both, which made a CDR contradict
    itself — session 528 reported 2 minutes of parking against a tariff whose
    first 5 minutes are free, so applying our own tariff to our own figure gave
    RM0.00 where we had charged RM0.40. The grace lives in the tariff's
    restrictions, so the quantity has to be the measured one for the two to
    multiply out.

    Not gated on idle_fee_enabled: the EV still sat there when we charge
    nothing for it, and a partner reconciles the duration either way.
    """
    start = getattr(sess, "idle_started_at", None)
    end = idle_end(sess, now)
    if not start or not end or end <= start:
        return 0.0
    return (end - start).total_seconds()


def free_seconds(charger) -> int:
    """Parking seconds that cost nothing, as both the biller and the tariff see it.

    The configured grace, plus one block. Voltality bill whole completed
    minutes and drop the remainder, and on 2026-10-15 Aqid chose to match
    them rather than ask them to change. Dropping a remainder is the same
    arithmetic as charging full blocks after a free window one block longer,
    so expressing it this way lets the published tariff state the rule exactly
    instead of us billing by one rule and advertising another. OCPI has no way
    to say "round down": step_size always rounds up.
    """
    grace = int(getattr(charger, "idle_grace_minutes", 0) or 0) * 60
    return grace + PARKING_STEP_SECONDS


def parking_hours(sess, charger=None, now: Optional[datetime] = None) -> float:
    """measured_idle_seconds as hours, for publication on a CDR.

    Truncated rather than rounded, and to six places. Rounding up here would
    be worth less than four milliseconds of parking and would still cost a
    block: a partner multiplies this back by 3600 and takes the ceiling of
    whatever sits past the grace, so 2400 seconds published as 0.6667 comes
    back as 2400.12 and bills 26 minutes where we billed 25. Truncation can
    only ever lose a few milliseconds, which cannot cross a block boundary.
    """
    seconds = measured_idle_seconds(sess, charger, now)
    if seconds <= 0:
        return 0.0
    return math.floor(seconds / 3600 * 1_000_000) / 1_000_000


def compute_idle(sess, charger, now: Optional[datetime] = None) -> Tuple[int, float]:
    """Billable idle minutes and the fee for them, after the grace period.

    Only whole completed minutes past the grace are charged; a remainder short
    of a full minute is dropped. That is Voltality's rule, adopted on
    2026-10-15 so the two sides agree. It is implemented as whole blocks past
    free_seconds, which is the same arithmetic and is what the tariff states.

    The returned minutes are the billed quantity, not the measured one. Do not
    publish them as a CDR's parking duration: that field is the measured time
    and the free window is expressed as a tariff restriction over it. Use
    measured_idle_seconds for anything a partner re-prices.
    """
    if not charger or not charger.idle_fee_enabled:
        return 0, 0.0

    start = sess.idle_started_at
    end = idle_end(sess, now)
    if not start or not end or end <= start:
        return 0, 0.0

    elapsed_s = (end - start).total_seconds()
    chargeable_s = max(0.0, elapsed_s - free_seconds(charger))
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

    # The caller passes the charger's own reported instant, which is more
    # accurate than ours but is also a clock we do not control. Clamp it: never
    # later than now, and never before the stop it is closing out.
    reported = now or now_myt()
    reported = min(reported, now_myt())
    if sess.stop_time and reported < sess.stop_time:
        reported = sess.stop_time
    sess.unplugged_at = reported
    # Money already moved on the kiosk flow. Re-billing here would settle
    # against a figure the customer was never shown and cannot be refunded a
    # second time, so those sessions only record when the cable came out.
    if sess.refund_status in (None, "", "not_required"):
        finalize_idle(sess, charger, reported)
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

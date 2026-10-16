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

# Parking is measured to a tenth of a minute before anything is billed from
# it, because that is the precision Voltality read at and we bill what they
# bill. Their message about session 537 shows it: "0.191666 hours, equivalent
# to approximately 11.5 minutes", and that 11.5 is the number they then round
# to whole minutes. Session 540 is where it bites. 449 seconds is 7.483
# minutes, which becomes 7.5 and then 8, where rounding once would give 7.
#
# An exhaustive sweep of 144 candidate rules against sessions 528, 535, 537
# and 540 left three that fit every figure Voltality produced, and all three
# carry this step. No rule without it fits any three of the four.
PARKING_RESOLUTION_SECONDS = 6


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


def whole_second(value: Optional[datetime]) -> Optional[datetime]:
    """Drop the fraction of a second.

    Every datetime we bill from is stored in a MySQL DATETIME, which keeps
    whole seconds only. Billing from a value that still carries microseconds
    therefore charges one figure and stores another, and the CDR, rebuilt from
    the stored value, disagrees with the money we took. Session 540 unplugged
    at 17:12:54.17: we billed 449.17 seconds as three blocks and published two.
    A charger that sends no timestamp on its StatusNotification leaves us
    reading our own clock, which always has a fraction, so this is the ordinary
    path rather than an edge case.
    """
    return value.replace(microsecond=0) if value else value


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
    start = whole_second(getattr(sess, "idle_started_at", None))
    end = whole_second(idle_end(sess, now))
    if not start or not end or end <= start:
        return 0.0
    return (end - start).total_seconds()


def free_seconds(charger) -> int:
    """Parking seconds that cost nothing, as both the biller and the tariff see it.

    The configured grace, plainly. Voltality stated their algorithm for
    session 537 and it is OCPI's own:

        "Based on the 60-second step size, the parking duration should be
         rounded up to 12 minutes. After deducting the 5-minute grace period,
         the chargeable duration should be 7 minutes."

    So: round the published parking duration up to the whole step, then deduct
    the grace. Checked against every verdict they have given us, reading the
    duration we published at the time:

        535   0.116944 h ->  7.0 min -> 7  -> 2 minutes   RM0.40   they passed
        537   0.191666 h -> 11.5 min -> 12 -> 7 minutes   RM1.40   they asked
        540   0.124722 h ->  7.5 min -> 8  -> 3 minutes   RM0.60   they asked

    Earlier versions of this function shifted the window by half a block, then
    by a whole one, to express rounding to nearest and rounding down. Both were
    fitted to the figures rather than taken from the rule, and each broke on
    the next session. Rounding up is what step_size means, so the free window
    is the grace and nothing more.
    """
    return int(getattr(charger, "idle_grace_minutes", 0) or 0) * 60


def billed_idle_seconds(sess, charger=None, now: Optional[datetime] = None) -> int:
    """The parking duration we bill from, and the one we publish.

    measured_idle_seconds snapped to the nearest PARKING_RESOLUTION_SECONDS.
    Billing from the raw measurement while a partner re-prices a duration they
    have rounded to a tenth of a minute is how session 540 ended up at RM0.40
    on our side and RM0.60 on theirs. Snapping first makes the two agree, and
    it has to be the published figure as well: publish 449 seconds and bill
    three minutes and the CDR contradicts its own tariff, which is the fault
    Voltality raised against session 528 in the first place.

    The cost of this is that a published duration can sit up to three seconds
    either side of what the clock saw.
    """
    seconds = measured_idle_seconds(sess, charger, now)
    if seconds <= 0:
        return 0
    # Half up, not Python's round, which rounds a half to the even neighbour.
    # A duration sitting exactly three seconds into a six second bucket is the
    # only place the two differ, and it is one duration in six: 447 seconds
    # snaps to 450 here and would snap to 444 under round(), which is a whole
    # minute of difference once the grace comes off.
    buckets = math.floor(seconds / PARKING_RESOLUTION_SECONDS + 0.5)
    return int(buckets * PARKING_RESOLUTION_SECONDS)


def parking_hours(sess, charger=None, now: Optional[datetime] = None) -> float:
    """measured_idle_seconds as hours, for publication on a CDR.

    Truncated rather than rounded, and to six places. Rounding up here would
    be worth less than four milliseconds of parking and would still cost a
    block: a partner multiplies this back by 3600 and takes the ceiling of
    whatever sits past the grace, so 2400 seconds published as 0.6667 comes
    back as 2400.12 and bills 26 minutes where we billed 25. Truncation can
    only ever lose a few milliseconds, which cannot cross a block boundary.
    """
    seconds = billed_idle_seconds(sess, charger, now)
    if seconds <= 0:
        return 0.0
    return math.floor(seconds / 3600 * 1_000_000) / 1_000_000


def compute_idle(sess, charger, now: Optional[datetime] = None) -> Tuple[int, float]:
    """Billable idle minutes and the fee for them, after the grace period.

    Voltality's rule, which is also OCPI's: the parking time is measured to a
    tenth of a minute, rounded up to the whole 60 second step, and the grace
    then comes off. Whole blocks past free_seconds over billed_idle_seconds is
    the same arithmetic and is what the tariff states.

    The returned minutes are the billed quantity, not the measured one. Do not
    publish them as a CDR's parking duration: that field is the measured time
    and the free window is expressed as a tariff restriction over it. Use
    measured_idle_seconds for anything a partner re-prices.
    """
    if not charger or not charger.idle_fee_enabled:
        return 0, 0.0

    elapsed_s = billed_idle_seconds(sess, charger, now)
    if elapsed_s <= 0:
        return 0, 0.0

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
    # Drop the fraction of a second before anything is billed from it. The
    # column is a DATETIME and keeps whole seconds only, so a value carrying
    # microseconds bills one figure and stores another: session 540 unplugged
    # at 17:12:54.17, billed 449.17 s as three blocks, then came back from the
    # database as 449 s and rebuilt its CDR as two. A charger that sends no
    # timestamp on StatusNotification leaves us using our own clock, which
    # always has a fraction, so this is the common path and not the edge.
    sess.unplugged_at = reported.replace(microsecond=0)
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

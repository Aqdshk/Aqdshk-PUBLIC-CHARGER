"""
PlagSini EV — App Features Router

New endpoints for:
  - Charger reviews & ratings
  - Charger booking / reservation
  - Charger issue reporting (user-facing)
  - Cost estimate before charging
  - Meter values (kW graph) for active session
  - Carbon footprint summary

Prefix: /api
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import (
    SessionLocal, get_db,
    Charger, ChargerReview, ChargerBooking, ChargingSession,
    Fault, MeterValue, Pricing, PushSubscription, User,
)
from security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["App Features"])

# Malaysia grid emission factor (kg CO₂ per kWh) — TNB 2023 figure
_CO2_KG_PER_KWH = 0.585


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _get_user_id(authorization: Optional[str]) -> Optional[int]:
    """Return user id from Bearer token, or None if anonymous/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(authorization[7:])
        return int(payload.get("sub", 0)) or None
    except Exception:
        return None


# ─── Reviews ──────────────────────────────────────────────────────────────────

class ReviewIn(BaseModel):
    rating:  int         = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ReviewOut(BaseModel):
    id:         int
    rating:     int
    comment:    Optional[str]
    user_name:  Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/chargers/{charge_point_id}/reviews", response_model=List[ReviewOut])
def get_reviews(charge_point_id: str, db: Session = Depends(get_db)):
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")
    reviews = (
        db.query(ChargerReview)
        .filter(ChargerReview.charger_id == charger.id)
        .order_by(ChargerReview.created_at.desc())
        .limit(50)
        .all()
    )
    result = []
    for r in reviews:
        user_name = None
        if r.user_id:
            u = db.query(User).filter(User.id == r.user_id).first()
            user_name = u.name if u else None
        result.append(ReviewOut(
            id=r.id,
            rating=r.rating,
            comment=r.comment,
            user_name=user_name,
            created_at=r.created_at.isoformat() if r.created_at else "",
        ))
    return result


@router.post("/chargers/{charge_point_id}/reviews", status_code=201)
def submit_review(
    charge_point_id: str,
    body: ReviewIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")
    user_id = _get_user_id(authorization)
    review = ChargerReview(
        charger_id=charger.id,
        user_id=user_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    db.commit()
    return {"status": "ok", "id": review.id}


# ─── Average rating helper (used in charger list) ─────────────────────────────

@router.get("/chargers/{charge_point_id}/rating")
def get_charger_rating(charge_point_id: str, db: Session = Depends(get_db)):
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")
    reviews = db.query(ChargerReview).filter(ChargerReview.charger_id == charger.id).all()
    if not reviews:
        return {"average": None, "count": 0}
    avg = sum(r.rating for r in reviews) / len(reviews)
    return {"average": round(avg, 1), "count": len(reviews)}


# ─── Issue Report ─────────────────────────────────────────────────────────────

class IssueReportIn(BaseModel):
    issue_type: str = Field(..., description="broken_cable | no_power | payment_failed | screen_issue | other")
    description: Optional[str] = Field(None, max_length=500)


@router.post("/chargers/{charge_point_id}/report", status_code=201)
def report_issue(
    charge_point_id: str,
    body: IssueReportIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")
    fault = Fault(
        charger_id=charger.id,
        fault_type=body.issue_type,
        message=body.description or body.issue_type,
    )
    db.add(fault)
    db.commit()
    logger.info(f"User issue report: charger={charge_point_id} type={body.issue_type}")
    return {"status": "ok", "message": "Laporan diterima. Terima kasih!"}


# ─── Cost Estimate ────────────────────────────────────────────────────────────

@router.get("/chargers/{charge_point_id}/cost-estimate")
def cost_estimate(
    charge_point_id: str,
    battery_kwh: float = Query(60.0, description="Vehicle battery capacity in kWh"),
    current_soc: float = Query(20.0, description="Current state of charge 0–100"),
    target_soc: float  = Query(80.0, description="Target state of charge 0–100"),
    db: Session = Depends(get_db),
):
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")

    # Get pricing: per-charger first, then global default
    pricing = (
        db.query(Pricing).filter(Pricing.charger_id == charger.id, Pricing.is_active == True).first()
        or db.query(Pricing).filter(Pricing.charger_id == None, Pricing.is_active == True).first()
    )
    price_kwh  = float(pricing.price_per_kwh)  if pricing else 0.50
    price_min  = float(pricing.price_per_minute) if pricing else 0.00
    min_charge = float(pricing.minimum_charge) if pricing else 0.00

    energy_needed_kwh = battery_kwh * (target_soc - current_soc) / 100.0
    if energy_needed_kwh <= 0:
        return {"energy_kwh": 0, "estimated_cost_rm": 0, "estimated_minutes": 0}

    power_kw = charger.max_power_kw or 7.4
    estimated_minutes = (energy_needed_kwh / power_kw) * 60

    cost_kwh = energy_needed_kwh * price_kwh
    cost_min = estimated_minutes * price_min
    estimated_cost = max(cost_kwh + cost_min, min_charge)

    return {
        "charge_point_id": charge_point_id,
        "energy_kwh":        round(energy_needed_kwh, 2),
        "estimated_cost_rm": round(estimated_cost, 2),
        "estimated_minutes": round(estimated_minutes),
        "price_per_kwh":     price_kwh,
        "power_kw":          power_kw,
    }


# ─── kW Graph — Meter values for active session ───────────────────────────────

@router.get("/sessions/{transaction_id}/meter-values")
def get_session_meter_values(
    transaction_id: int,
    limit: int = Query(60, description="Max number of data points"),
    db: Session = Depends(get_db),
):
    values = (
        db.query(MeterValue)
        .filter(MeterValue.transaction_id == transaction_id)
        .order_by(MeterValue.timestamp.desc())
        .limit(limit)
        .all()
    )
    values = list(reversed(values))
    return [
        {
            "timestamp": v.timestamp.isoformat() if v.timestamp else None,
            "power_kw":  round((v.power or 0) / 1000.0, 2),
            "voltage":   v.voltage,
            "current":   v.current,
            "total_kwh": v.total_kwh,
        }
        for v in values
    ]


# ─── Carbon Footprint ─────────────────────────────────────────────────────────

@router.get("/users/{user_id}/carbon-footprint")
def get_carbon_footprint(
    user_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    # All completed sessions by this user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    sessions = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.user_id.in_([user.email, str(user_id)]),
            ChargingSession.status == "completed",
        )
        .all()
    )

    total_kwh      = sum(s.energy_consumed or 0 for s in sessions)
    co2_saved_kg   = total_kwh * _CO2_KG_PER_KWH       # vs petrol equivalent
    petrol_saved_l = total_kwh / 6.5                    # ~6.5 kWh per litre petrol equiv
    trees_equiv    = co2_saved_kg / 21.77               # avg tree absorbs ~21.77 kg CO2/yr

    # This month
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sessions = [s for s in sessions if s.start_time and s.start_time >= month_start]
    month_kwh = sum(s.energy_consumed or 0 for s in month_sessions)

    return {
        "total_sessions":   len(sessions),
        "total_kwh":        round(total_kwh, 2),
        "co2_saved_kg":     round(co2_saved_kg, 2),
        "petrol_saved_l":   round(petrol_saved_l, 2),
        "trees_equivalent": round(trees_equiv, 2),
        "this_month_kwh":   round(month_kwh, 2),
        "this_month_co2_kg": round(month_kwh * _CO2_KG_PER_KWH, 2),
    }


# ─── Booking / Reservation ────────────────────────────────────────────────────

class BookingIn(BaseModel):
    start_time:   str = Field(..., description="ISO-8601 start datetime")
    duration_min: int = Field(60, ge=15, le=240, description="Booking duration in minutes")
    connector_id: int = Field(1)
    notes:        Optional[str] = None


class BookingOut(BaseModel):
    id:           int
    charge_point_id: str
    connector_id: int
    start_time:   str
    end_time:     str
    status:       str
    created_at:   str

    model_config = {"from_attributes": True}


@router.get("/chargers/{charge_point_id}/available-slots")
def get_available_slots(
    charge_point_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    """Return available 30-min slots for a given date."""
    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format — use YYYY-MM-DD")

    day_start = target_date.replace(hour=6, minute=0)
    day_end   = target_date.replace(hour=23, minute=0)

    # Get existing bookings for this charger on this day
    bookings = db.query(ChargerBooking).filter(
        ChargerBooking.charger_id == charger.id,
        ChargerBooking.start_time >= day_start,
        ChargerBooking.end_time   <= day_end + timedelta(hours=1),
        ChargerBooking.status.in_(["confirmed", "pending"]),
    ).all()

    booked_ranges = [(b.start_time, b.end_time) for b in bookings]

    # Generate 30-min slots
    slots = []
    current = day_start
    while current < day_end:
        slot_end = current + timedelta(minutes=30)
        is_booked = any(
            not (slot_end <= bs or current >= be)
            for bs, be in booked_ranges
        )
        slots.append({
            "start": current.strftime("%H:%M"),
            "end":   slot_end.strftime("%H:%M"),
            "available": not is_booked,
        })
        current = slot_end

    return {"date": date, "slots": slots}


@router.post("/chargers/{charge_point_id}/book", status_code=201)
def create_booking(
    charge_point_id: str,
    body: BookingIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Login required to book a charger")

    charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
    if not charger:
        raise HTTPException(404, "Charger not found")

    try:
        start_dt = datetime.fromisoformat(body.start_time)
    except ValueError:
        raise HTTPException(400, "Invalid start_time format")

    end_dt = start_dt + timedelta(minutes=body.duration_min)

    # Check for conflict
    conflict = db.query(ChargerBooking).filter(
        ChargerBooking.charger_id   == charger.id,
        ChargerBooking.connector_id == body.connector_id,
        ChargerBooking.status.in_(["confirmed", "pending"]),
        ChargerBooking.start_time   < end_dt,
        ChargerBooking.end_time     > start_dt,
    ).first()

    if conflict:
        raise HTTPException(409, "Slot not available — please choose another time")

    booking = ChargerBooking(
        charger_id=charger.id,
        user_id=user_id,
        connector_id=body.connector_id,
        start_time=start_dt,
        end_time=end_dt,
        status="confirmed",
        notes=body.notes,
    )
    db.add(booking)
    db.commit()

    return {
        "status": "ok",
        "booking_id": booking.id,
        "charge_point_id": charge_point_id,
        "start_time": start_dt.isoformat(),
        "end_time":   end_dt.isoformat(),
    }


@router.get("/users/{user_id}/bookings")
def get_user_bookings(
    user_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    bookings = (
        db.query(ChargerBooking)
        .filter(ChargerBooking.user_id == user_id)
        .order_by(ChargerBooking.start_time.desc())
        .limit(20)
        .all()
    )
    result = []
    for b in bookings:
        charger = db.query(Charger).filter(Charger.id == b.charger_id).first()
        result.append({
            "id":            b.id,
            "charge_point_id": charger.charge_point_id if charger else "—",
            "location":      charger.location if charger else None,
            "connector_id":  b.connector_id,
            "start_time":    b.start_time.isoformat() if b.start_time else None,
            "end_time":      b.end_time.isoformat()   if b.end_time   else None,
            "status":        b.status,
            "notes":         b.notes,
        })
    return result


@router.delete("/bookings/{booking_id}")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")

    booking = db.query(ChargerBooking).filter(ChargerBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != user_id:
        raise HTTPException(403, "Not your booking")

    booking.status = "cancelled"
    db.commit()
    return {"status": "ok", "message": "Booking cancelled"}


# ─── Web Push (PWA) ───────────────────────────────────────────────────────────

class PushSubscriptionIn(BaseModel):
    endpoint: str
    p256dh:   str
    auth:     str
    user_agent: Optional[str] = None


@router.get("/push/vapid-public-key")
def get_vapid_key():
    """Return VAPID public key for browser push subscription."""
    from push_service import get_vapid_public_key
    key = get_vapid_public_key()
    if not key:
        raise HTTPException(503, "Push notifications not configured")
    return {"public_key": key}


@router.post("/push/subscribe", status_code=201)
def subscribe_push(
    body: PushSubscriptionIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Save browser push subscription. Upserts by endpoint."""
    user_id = _get_user_id(authorization)
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if existing:
        existing.p256dh     = body.p256dh
        existing.auth       = body.auth
        existing.user_id    = user_id or existing.user_id
        existing.user_agent = body.user_agent
    else:
        sub = PushSubscription(
            user_id=user_id,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
            user_agent=body.user_agent,
        )
        db.add(sub)
    db.commit()
    return {"status": "ok"}


@router.delete("/push/unsubscribe")
def unsubscribe_push(
    endpoint: str,
    db: Session = Depends(get_db),
):
    db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).delete()
    db.commit()
    return {"status": "ok"}

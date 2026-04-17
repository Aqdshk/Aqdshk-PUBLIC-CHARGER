"""
PlagSini EV — Database Models & Session

SQLAlchemy ORM models and session factory. Configured via DATABASE_URL env.

Models:
  - User, Wallet, WalletTransaction — user accounts and wallet
  - Charger, ChargingSession, MeterValue, Fault — OCPP charger data
  - Pricing, Payment, PaymentTransaction — billing
  - SupportTicket, TicketMessage, SupportStaff, StaffSession — support
  - OTPVerification, PaymentGatewayConfig, AuditLog — auth & audit

Usage:
    from database import SessionLocal, get_db, User, Charger
    db = SessionLocal()
    user = db.query(User).filter(User.email == "x@y.com").first()
"""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def _utcnow():
    """Timezone-safe replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── User & Wallet ────────────────────────────────────────────────────────
# User: App/mobile user; SupportStaff is separate for staff portal
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile info
    name = Column(String(255), default="")
    avatar_url = Column(String(500), nullable=True)
    
    # Status & Role
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)  # Admin flag for dashboard access
    
    # Security: track failed login attempts
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    wallet_transactions = relationship("WalletTransaction", back_populates="user")
    vehicles = relationship("Vehicle", back_populates="user")
    charger_reviews    = relationship("ChargerReview",    back_populates="user")
    charger_bookings   = relationship("ChargerBooking",   back_populates="user")
    push_subscriptions = relationship("PushSubscription", back_populates="user")
    
    def set_password(self, password: str):
        """Hash and set password using PBKDF2-SHA256 with 100k iterations."""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        self.password_hash = f"{salt}${hash_obj.hex()}"
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        try:
            salt, stored_hash = self.password_hash.split('$')
            hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return hash_obj.hex() == stored_hash
        except (ValueError, AttributeError):
            return False

    def is_locked(self) -> bool:
        """Check if account is temporarily locked due to failed login attempts."""
        if self.locked_until and self.locked_until > _utcnow():
            return True
        return False

    def record_failed_login(self):
        """Increment failed login counter and lock if threshold reached."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            # Lock for 15 minutes after 5 failed attempts
            from datetime import timedelta
            self.locked_until = _utcnow() + timedelta(minutes=15)

    def reset_failed_logins(self):
        """Reset failed login counter on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None


# Wallet: One per user; balance in MYR (Numeric for precision)
class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Use Numeric(12,2) for precise currency — no floating point errors
    balance = Column(Numeric(12, 2), default=Decimal("0.00"))  # Current balance in MYR
    points = Column(Integer, default=0)   # Reward points
    currency = Column(String(10), default="MYR")
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    
    # Transaction type: topup, charge_payment, refund, points_earned, points_redeemed
    transaction_type = Column(String(50), nullable=False)
    
    # Amount details — Numeric for precision
    amount = Column(Numeric(12, 2), nullable=False)  # Positive for credit, negative for debit
    balance_before = Column(Numeric(12, 2), nullable=False)
    balance_after = Column(Numeric(12, 2), nullable=False)
    
    # Points (if applicable)
    points_amount = Column(Integer, default=0)
    points_before = Column(Integer, default=0)
    points_after = Column(Integer, default=0)
    
    # Reference to charging session (if applicable)
    session_id = Column(Integer, ForeignKey("charging_sessions.id"), nullable=True)
    
    # Idempotency key — prevents duplicate transactions
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    
    # Payment gateway info (for top-ups)
    payment_method = Column(String(50), nullable=True)  # fpx, tng, grabpay, card
    payment_gateway = Column(String(50), nullable=True)  # billplz, stripe
    gateway_reference = Column(String(255), nullable=True)
    
    # Status
    status = Column(String(50), default="completed")  # pending, completed, failed, refunded
    
    # Description
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallet_transactions")
    wallet = relationship("Wallet", back_populates="transactions")


class Vehicle(Base):
    """User's registered vehicles"""
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Vehicle info
    plate_number = Column(String(20), nullable=True)
    brand = Column(String(100), nullable=True)  # Tesla, BYD, etc.
    model = Column(String(100), nullable=True)  # Model 3, Atto 3, etc.
    year = Column(Integer, nullable=True)
    
    # EV specs
    battery_capacity_kwh = Column(Float, nullable=True)  # e.g., 60 kWh
    connector_type = Column(String(50), nullable=True)   # Type 2, CCS, CHAdeMO
    
    # Status
    is_primary = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    
    # Relationships
    user = relationship("User", back_populates="vehicles")


# ==================== OTP VERIFICATION ====================

class PushSubscription(Base):
    """Browser Web Push subscriptions for PWA notifications."""
    __tablename__ = "push_subscriptions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    endpoint   = Column(Text, nullable=False, unique=True)
    p256dh     = Column(Text, nullable=False)   # browser public key
    auth       = Column(Text, nullable=False)   # auth secret
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="push_subscriptions")


class OTPVerification(Base):
    """Store OTP codes for email verification during registration."""
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    otp_code = Column(String(6), nullable=False)
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # Track failed attempts
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    def is_expired(self) -> bool:
        return _utcnow() > self.expires_at


# ==================== CHARGER & SESSIONS ====================

class Charger(Base):
    __tablename__ = "chargers"
    
    id = Column(Integer, primary_key=True, index=True)
    charge_point_id = Column(String(255), unique=True, index=True, nullable=False)
    vendor = Column(String(255))
    model = Column(String(255))
    firmware_version = Column(String(255))
    status = Column(String(50), default="offline")  # online, offline
    availability = Column(String(50), default="unknown")  # available, charging, faulted, unavailable
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)
    
    # Configuration parameters (matching SteVe OCPP)
    number_of_connectors = Column(Integer, default=1)
    heartbeat_interval = Column(Integer, default=7200)  # 2 hours default
    meter_value_sample_interval = Column(Integer, default=10)  # 10 seconds
    transaction_message_attempts = Column(Integer, default=3)
    transaction_message_retry_interval = Column(Integer, default=120)  # 2 minutes

    # Physical / location info (set via admin API or directly in DB)
    location = Column(String(500), nullable=True)        # Human-readable address
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    connector_type = Column(String(100), nullable=True)  # e.g. "Type 2", "CCS2", "CHAdeMO"
    max_power_kw = Column(Float, nullable=True)          # e.g. 7.4, 22, 50

    # Relationships
    sessions = relationship("ChargingSession", back_populates="charger")
    meter_values = relationship("MeterValue", back_populates="charger")
    faults = relationship("Fault", back_populates="charger")
    maintenance_records = relationship("MaintenanceRecord", back_populates="charger")
    reviews  = relationship("ChargerReview",  back_populates="charger")
    bookings = relationship("ChargerBooking", back_populates="charger")


class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"))
    transaction_id = Column(Integer, unique=True, index=True, nullable=False)
    connector_id = Column(Integer, nullable=True)  # OCPP StartTransaction connector
    start_time = Column(DateTime, nullable=False)
    stop_time = Column(DateTime)
    energy_consumed = Column(Float, default=0.0)  # in kWh
    # OCPP meter readings (Wh) — authoritative for billing accuracy
    meter_start = Column(Integer, nullable=True)   # Wh at session start
    meter_stop = Column(Integer, nullable=True)    # Wh at session end (preferred over last MeterValues)
    stop_reason = Column(String(50), nullable=True)  # Local, Remote, EmergencyStop, PowerLoss, etc.
    status = Column(String(50), default="active")  # active, completed, stopped
    user_id = Column(String(255), nullable=True)  # User identifier (phone, email, etc)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    charger = relationship("Charger", back_populates="sessions")
    payment = relationship("Payment", back_populates="session")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="MYR")
    payment_method = Column(String(100))  # credit_card, e_wallet, qr_code, etc
    payment_status = Column(String(50), default="pending")  # pending, completed, failed, refunded
    payment_gateway = Column(String(100))  # stripe, paypal, etc
    gateway_transaction_id = Column(String(255))
    created_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime)
    
    session = relationship("ChargingSession", back_populates="payment")


class Pricing(Base):
    __tablename__ = "pricing"
    
    id = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=True)  # None = default pricing
    price_per_kwh = Column(Numeric(8, 4), nullable=False, default=Decimal("0.5000"))  # RM per kWh
    price_per_minute = Column(Numeric(8, 4), default=Decimal("0.0000"))  # RM per minute
    minimum_charge = Column(Numeric(8, 2), default=Decimal("0.00"))  # Minimum amount
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)


class MeterValue(Base):
    __tablename__ = "meter_values"
    
    id = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"))
    transaction_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    voltage = Column(Float)  # in V
    current = Column(Float)  # in A
    power = Column(Float)  # in W
    total_kwh = Column(Float)  # in kWh
    
    charger = relationship("Charger", back_populates="meter_values")


class Fault(Base):
    __tablename__ = "faults"
    
    id = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"))
    fault_type = Column(String(100), nullable=False)  # overcurrent, ground_fault, emergency_stop, cp_error
    message = Column(Text)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    cleared = Column(Boolean, default=False)
    cleared_at = Column(DateTime)
    
    charger = relationship("Charger", back_populates="faults")


class ChargerReview(Base):
    """User ratings and reviews for chargers"""
    __tablename__ = "charger_reviews"

    id         = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    rating     = Column(Integer, nullable=False)          # 1–5 stars
    comment    = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    charger = relationship("Charger", back_populates="reviews")
    user    = relationship("User", back_populates="charger_reviews")


class ChargerBooking(Base):
    """Charger slot reservations made by users"""
    __tablename__ = "charger_bookings"

    id           = Column(Integer, primary_key=True, index=True)
    charger_id   = Column(Integer, ForeignKey("chargers.id"), nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    connector_id = Column(Integer, default=1)
    start_time   = Column(DateTime, nullable=False)
    end_time     = Column(DateTime, nullable=False)
    # pending → confirmed → completed | cancelled
    status       = Column(String(50), default="confirmed")
    notes        = Column(String(500), nullable=True)
    created_at   = Column(DateTime, default=_utcnow)

    charger = relationship("Charger", back_populates="bookings")
    user    = relationship("User",    back_populates="charger_bookings")


class MaintenanceRecord(Base):
    """Maintenance history for chargers"""
    __tablename__ = "maintenance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    charger_id = Column(Integer, ForeignKey("chargers.id"), nullable=False)
    
    # Maintenance type: repair, part_replacement, inspection, cleaning, firmware_update, other
    maintenance_type = Column(String(50), nullable=False)
    
    # What was the issue/reason for maintenance
    issue_description = Column(Text, nullable=True)
    
    # What was done
    work_performed = Column(Text, nullable=False)
    
    # Parts replaced (if any)
    parts_replaced = Column(Text, nullable=True)
    
    # Cost of maintenance (optional)
    cost = Column(Numeric(10, 2), nullable=True)
    
    # Who performed the maintenance
    technician_name = Column(String(255), nullable=True)
    
    # Status: scheduled, in_progress, completed, cancelled
    status = Column(String(50), default="completed")
    
    # Dates
    date_reported = Column(DateTime, default=_utcnow)
    date_scheduled = Column(DateTime, nullable=True)
    date_completed = Column(DateTime, nullable=True)
    
    # Additional notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    charger = relationship("Charger", back_populates="maintenance_records")


# ==================== DEPARTMENTS & STAFF ====================

# Category → Department mapping
CATEGORY_DEPARTMENT_MAP = {
    "login_account": "IT",
    "app_issue": "IT",
    "charging": "Operations",
    "vehicle": "Operations",
    "wallet_payment": "Finance",
    "rewards": "Marketing",
    "general": "Customer Service",
}

DEPARTMENTS = ["IT", "Operations", "Finance", "Marketing", "Customer Service"]

# Staff roles hierarchy: admin > manager > staff
STAFF_ROLES = ["admin", "manager", "staff"]


class SupportStaff(Base):
    """Support staff members who handle tickets."""
    __tablename__ = "support_staff"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    department = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="staff", index=True)
    # role: admin | manager | staff

    is_active = Column(Boolean, default=True)
    max_tickets = Column(Integer, default=10)  # max concurrent open tickets

    created_at = Column(DateTime, default=_utcnow)
    last_login = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        """Hash password using PBKDF2-SHA256 (same strength as User model)."""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        self.password_hash = f"{salt}${hash_obj.hex()}"

    def check_password(self, password: str) -> bool:
        """Verify password — supports both new PBKDF2 and legacy SHA256 format."""
        if not self.password_hash:
            return False

        # New format: salt$pbkdf2_hash
        if "$" in self.password_hash:
            try:
                salt, stored_hash = self.password_hash.split("$", 1)
                hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
                return hash_obj.hex() == stored_hash
            except (ValueError, AttributeError):
                return False

        # Legacy format: salt:sha256_hash (auto-upgrade on next login)
        if ":" in self.password_hash:
            salt, stored = self.password_hash.split(":", 1)
            if hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == stored:
                # Auto-upgrade to PBKDF2 on successful legacy login
                self.set_password(password)
                return True
            return False

        return False


class StaffSession(Base):
    """Persistent staff login sessions stored in DB (survives container restarts)."""
    __tablename__ = "staff_sessions"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("support_staff.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    staff = relationship("SupportStaff", backref="sessions")


# ==================== SUPPORT TICKETS ====================

class SupportTicket(Base):
    """Customer support tickets."""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(20), unique=True, index=True, nullable=False)

    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)

    category = Column(String(50), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="medium", index=True)
    status = Column(String(20), default="open", index=True)

    assigned_to = Column(String(255), nullable=True)
    assigned_staff_id = Column(Integer, ForeignKey("support_staff.id"), nullable=True, index=True)
    department = Column(String(50), nullable=True, index=True)
    source = Column(String(30), default="manual")
    resolution_notes = Column(Text, nullable=True)
    satisfaction_rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime, nullable=True)
    first_response_at = Column(DateTime, nullable=True)

    # SLA / Reminder fields
    due_at = Column(DateTime, nullable=True, index=True)  # SLA deadline
    reminder_sent_at = Column(DateTime, nullable=True)    # last reminder email sent
    escalated = Column(Boolean, default=False)             # has been escalated due to overdue

    messages = relationship("TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at")

# SLA deadlines (hours) per priority
TICKET_SLA_HOURS = {
    "urgent": 4,
    "high": 12,
    "medium": 24,
    "low": 48,
}


class TicketMessage(Base):
    """Messages within a ticket thread."""
    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False, index=True)

    sender_type = Column(String(20), nullable=False)
    sender_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    attachment_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=_utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


# ==================== PAYMENT GATEWAY CONFIG ====================

class PaymentGatewayConfig(Base):
    """Payment gateway metadata.

    Note:
    - Runtime gateway secrets should come from environment variables.
    - api_key/api_secret columns are kept for backward compatibility/migration only.
    """
    __tablename__ = "payment_gateway_config"

    id = Column(Integer, primary_key=True, index=True)
    
    # Gateway identity
    gateway_name = Column(String(50), nullable=False, unique=True)  # ocbc, fpx, billplz, stripe, manual
    display_name = Column(String(100), nullable=False)  # "OCBC Payment Gateway"
    
    # Legacy credential fields (do not use for new deployments)
    merchant_id = Column(String(255), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_secret = Column(String(500), nullable=True)
    
    # Environment
    is_sandbox = Column(Boolean, default=True)  # True = test mode, False = live
    sandbox_url = Column(String(500), nullable=True)
    production_url = Column(String(500), nullable=True)
    
    # Callback/Webhook URL (your server endpoint)
    callback_url = Column(String(500), nullable=True)
    redirect_url = Column(String(500), nullable=True)
    
    # Supported methods
    supports_fpx = Column(Boolean, default=False)
    supports_card = Column(Boolean, default=False)
    supports_ewallet = Column(Boolean, default=False)  # TNG, GrabPay
    supports_duitnow = Column(Boolean, default=False)
    
    # Extra config (JSON string for gateway-specific fields)
    extra_config = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class PaymentTransaction(Base):
    """Track all payment gateway transactions."""
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Reference
    transaction_ref = Column(String(50), unique=True, nullable=False, index=True)  # TXN-20260216-XXXXX
    
    # User
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    
    # Amount — Numeric for precision
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="MYR")
    
    # Payment details
    payment_method = Column(String(50), nullable=True)  # fpx, card, tng, grabpay, duitnow
    gateway_name = Column(String(50), nullable=False)  # ocbc, billplz, stripe, manual
    
    # Gateway response
    gateway_transaction_id = Column(String(255), nullable=True)
    gateway_reference = Column(String(255), nullable=True)
    gateway_status = Column(String(50), nullable=True)
    gateway_response = Column(Text, nullable=True)  # Full JSON response
    
    # Status: pending, processing, success, failed, expired, refunded
    status = Column(String(20), default="pending", index=True)
    
    # Purpose: topup, charge_payment, subscription
    purpose = Column(String(50), default="topup")
    
    # Idempotency key — prevent duplicate payment creation
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    
    # Linked wallet transaction (created on success)
    wallet_transaction_id = Column(Integer, ForeignKey("wallet_transactions.id"), nullable=True)
    
    # URLs
    payment_url = Column(String(1000), nullable=True)  # URL user is redirected to
    
    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    paid_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    
    # IP and device info
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)


# ==================== AUDIT LOG ====================

class AuditLog(Base):
    """Immutable audit trail for security-sensitive and financial operations."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)

    # Who
    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    staff_id = Column(Integer, nullable=True)

    # What
    action = Column(String(100), nullable=False, index=True)
    # e.g. "login", "login_failed", "topup", "wallet_debit", "reward_redeem",
    #       "admin_update_user", "password_changed", "payment_callback"

    # Details
    resource_type = Column(String(50), nullable=True)  # user, wallet, payment, ticket
    resource_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)

    # Context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Old / new values for change tracking (JSON)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)


# ─── Database Engine & Session ─────────────────────────────────────────────
# DATABASE_URL: mysql+pymysql://user:pass@host:3306/db or sqlite:///local.db

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://charging_user:charging_password@localhost:3306/charging_platform"
)

if DATABASE_URL.startswith("mysql"):
    engine = create_engine(
        DATABASE_URL, pool_pre_ping=True, pool_recycle=3600, echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_charging_session_connector_id_column():
    """Add connector_id to existing DBs (create_all does not alter tables)."""
    try:
        from sqlalchemy import inspect, text

        insp = inspect(engine)
        if not insp.has_table("charging_sessions"):
            return
        cols = {c["name"] for c in insp.get_columns("charging_sessions")}
        if "connector_id" in cols:
            return
        dialect = engine.dialect.name
        with engine.begin() as conn:
            if dialect == "mysql":
                conn.execute(
                    text("ALTER TABLE charging_sessions ADD COLUMN connector_id INT NULL")
                )
            elif dialect == "sqlite":
                conn.execute(
                    text("ALTER TABLE charging_sessions ADD COLUMN connector_id INTEGER")
                )
            else:
                conn.execute(
                    text("ALTER TABLE charging_sessions ADD COLUMN connector_id INTEGER")
                )
    except Exception:
        pass


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    _ensure_charging_session_connector_id_column()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
PlagSini EV — Security Layer
JWT Authentication, Authorization & Financial Safeguards

Provides:
  - JWT access + refresh token creation / verification
  - get_current_user() FastAPI dependency
  - get_current_user_optional() for mixed endpoints
  - require_admin() for admin-only endpoints
  - AuditLog helper for financial operations
  - Rate-limit helpers (app-level)
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import AuditLog, User, Wallet, WalletTransaction, get_db

logger = logging.getLogger(__name__)


def _utcnow():
    """Timezone-safe replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ═══════════════════════════════════════════
#  JWT CONFIGURATION
# ═══════════════════════════════════════════

# Secret key — MUST be set via JWT_SECRET_KEY env var. No default allowed.
# Generate a strong key: python -c "import secrets; print(secrets.token_hex(32))"
_jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
if not _jwt_secret:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_SECRET_KEY = _jwt_secret
JWT_ALGORITHM = "HS256"

# Token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 min
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7 days

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=False)


# ═══════════════════════════════════════════
#  TOKEN CREATION
# ═══════════════════════════════════════════

def create_access_token(user_id: int, email: str, is_admin: bool = False) -> str:
    """Create a short-lived access token."""
    now = _utcnow()
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived refresh token (for token renewal)."""
    now = _utcnow()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_tokens(user: User) -> dict:
    """Create both access and refresh tokens for a user."""
    access = create_access_token(user.id, user.email, user.is_admin)
    refresh = create_refresh_token(user.id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
    }


# ═══════════════════════════════════════════
#  TOKEN VERIFICATION
# ═══════════════════════════════════════════

def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def verify_access_token(token: str) -> Optional[dict]:
    """Verify an access token and return its payload, or None on failure."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """Verify a refresh token and return its payload, or None on failure."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


# ═══════════════════════════════════════════
#  FASTAPI DEPENDENCIES
# ═══════════════════════════════════════════

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — extracts and verifies JWT from Authorization header.
    Returns the authenticated User or raises 401.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Like get_current_user but returns None instead of raising 401.
    Use for endpoints that work with or without auth.
    """
    if not credentials:
        return None

    payload = verify_access_token(credentials.credentials)
    if not payload:
        return None

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency — ensures the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def verify_resource_owner(current_user: User, resource_user_id: int):
    """
    Verify that the authenticated user owns the resource.
    Admins can access any resource.
    Raises 403 if not authorized.
    """
    if current_user.is_admin:
        return  # Admins can access everything
    if current_user.id != resource_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own resources",
        )


# ═══════════════════════════════════════════
#  FINANCIAL SAFEGUARDS
# ═══════════════════════════════════════════
# Top-up limits — override via env: MAX_TOPUP_PER_TXN, MAX_TOPUP_PER_DAY, MIN_TOPUP
# MAX_TOPUP_PER_TXN: max RM per single top-up; MAX_TOPUP_PER_DAY: max RM per user per day
MAX_TOPUP_PER_TRANSACTION = Decimal(os.getenv("MAX_TOPUP_PER_TXN", "500.00"))
MAX_TOPUP_PER_DAY = Decimal(os.getenv("MAX_TOPUP_PER_DAY", "2000.00"))
MIN_TOPUP_AMOUNT = Decimal(os.getenv("MIN_TOPUP", "1.00"))


def validate_topup_amount(amount: float) -> Decimal:
    """
    Validate top-up amount against per-transaction limits.
    Returns Decimal amount or raises HTTPException.
    """
    dec_amount = Decimal(str(amount)).quantize(Decimal("0.01"))

    if dec_amount < MIN_TOPUP_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum top-up amount is RM {MIN_TOPUP_AMOUNT}",
        )

    if dec_amount > MAX_TOPUP_PER_TRANSACTION:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum top-up per transaction is RM {MAX_TOPUP_PER_TRANSACTION}",
        )

    return dec_amount


def validate_topup_daily_limit(db: Session, user_id: int, amount: Decimal) -> None:
    """
    Check that the user has not exceeded MAX_TOPUP_PER_DAY for today.
    Raises HTTPException(400) if the limit would be breached.
    """
    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_total = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.user_id == user_id,
            WalletTransaction.transaction_type == "topup",
            WalletTransaction.status == "completed",
            WalletTransaction.created_at >= today_start,
        )
        .with_entities(WalletTransaction.amount)
        .all()
    )
    total_today = sum(Decimal(str(row.amount)) for row in daily_total)
    if total_today + amount > MAX_TOPUP_PER_DAY:
        remaining = MAX_TOPUP_PER_DAY - total_today
        raise HTTPException(
            status_code=400,
            detail=f"Daily top-up limit of RM {MAX_TOPUP_PER_DAY} reached. "
                   f"You can top up RM {max(remaining, Decimal('0.00')):.2f} more today.",
        )


def get_wallet_with_lock(db: Session, user_id: int) -> Wallet:
    """
    Get wallet with database-level row locking (SELECT ... FOR UPDATE).
    Prevents race conditions on concurrent wallet operations.
    Falls back to normal query for SQLite (no row locking support).
    """
    try:
        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == user_id)
            .with_for_update()
            .first()
        )
    except Exception:
        # SQLite doesn't support FOR UPDATE — fall back to normal query
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet


# ═══════════════════════════════════════════
#  AUDIT LOGGING
# ═══════════════════════════════════════════

def audit_log(
    action: str,
    user_id: int,
    details: str = "",
    ip_address: str = "",
    amount: float = 0.0,
    db: Optional[Session] = None,
):
    """
    Log financial and security-sensitive operations.
    Always writes to the application logger; also persists to the audit_logs DB table when db is provided.
    """
    logger.info(
        f"🔒 AUDIT | action={action} | user_id={user_id} | "
        f"amount=RM{amount:.2f} | ip={ip_address} | {details}"
    )
    if db is not None:
        try:
            entry = AuditLog(
                action=action,
                user_id=user_id,
                description=details,
                ip_address=ip_address,
                amount=Decimal(str(amount)) if amount else None,
            )
            db.add(entry)
            db.flush()
        except Exception as exc:
            logger.warning(f"audit_log: failed to persist to DB: {exc}")


def get_client_ip(request: Request) -> str:
    """
    Extract real client IP from request.
    Only trusts X-Forwarded-For when the direct connection comes from a known
    trusted proxy (127.0.0.1 or RFC-1918 private ranges — i.e. Nginx in Docker).
    Direct external connections use the socket IP to prevent IP spoofing.
    """
    direct_ip = request.client.host if request.client else ""

    def _is_trusted_proxy(ip: str) -> bool:
        return (
            ip == "127.0.0.1"
            or ip.startswith("10.")
            or ip.startswith("192.168.")
            or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)
        )

    if direct_ip and _is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("X-Forwarded-For", "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()

    return direct_ip or "unknown"

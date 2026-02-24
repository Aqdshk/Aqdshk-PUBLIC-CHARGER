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
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import User, Wallet, get_db

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  JWT CONFIGURATION
# ═══════════════════════════════════════════

# Secret key — MUST be set via env var in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "plagsini-ev-jwt-secret-change-me-in-production-2026")
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
    now = datetime.utcnow()
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
    now = datetime.utcnow()
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

# Top-up limits
MAX_TOPUP_PER_TRANSACTION = Decimal("500.00")  # RM 500 per transaction
MAX_TOPUP_PER_DAY = Decimal("2000.00")  # RM 2,000 per day
MIN_TOPUP_AMOUNT = Decimal("1.00")  # RM 1 minimum


def validate_topup_amount(amount: float) -> Decimal:
    """
    Validate top-up amount against limits.
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
):
    """
    Log financial and security-sensitive operations.
    In production, this should write to a dedicated audit table or external service.
    """
    logger.info(
        f"🔒 AUDIT | action={action} | user_id={user_id} | "
        f"amount=RM{amount:.2f} | ip={ip_address} | {details}"
    )


def get_client_ip(request: Request) -> str:
    """Extract real client IP from request (respects X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

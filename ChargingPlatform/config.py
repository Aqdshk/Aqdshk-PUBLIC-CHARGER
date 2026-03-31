"""
PlagSini EV — Central Configuration

Reads environment variables with sensible defaults.
All config should be accessed via this module for consistency.

Usage:
    from config import DATABASE_URL, JWT_SECRET_KEY
"""
import os
from typing import List

# ─── Database ─────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://charging_user:password@localhost:3306/charging_platform",
)

# ─── JWT & Auth ──────────────────────────────────────────────────────────
# JWT_SECRET_KEY MUST be set via environment — no default allowed.
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "").strip()
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ─── Staff Session ────────────────────────────────────────────────────────
STAFF_SESSION_TTL_DAYS: int = int(os.getenv("STAFF_SESSION_TTL_DAYS", "7"))

# ─── CORS ─────────────────────────────────────────────────────────────────
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")
APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()

# ─── App & URLs ───────────────────────────────────────────────────────────
APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

# ─── SMTP ─────────────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "PlagSini EV")

# ─── Payment ──────────────────────────────────────────────────────────────
PAYMENT_CALLBACK_SECRET: str = os.getenv("PAYMENT_CALLBACK_SECRET", "").strip()
ALLOW_DB_GATEWAY_SECRETS: bool = os.getenv("ALLOW_DB_GATEWAY_SECRETS", "0").strip().lower() in ("1", "true", "yes")

# ─── OCPP ─────────────────────────────────────────────────────────────────
OCPP_REQUIRE_AUTH: bool = os.getenv("OCPP_REQUIRE_AUTH", "1").strip().lower() in ("1", "true", "yes")
OCPP_SHARED_TOKEN: str = os.getenv("OCPP_SHARED_TOKEN", "").strip()
OCPP_CHARGER_TOKENS: str = os.getenv("OCPP_CHARGER_TOKENS", "").strip()

# ─── OCPI ──────────────────────────────────────────────────
OCPI_BASE_URL: str = os.getenv("OCPI_BASE_URL", "").strip()
OCPI_TOKEN: str = os.getenv("OCPI_TOKEN", "").strip()
OCPI_PARTY_ID: str = os.getenv("OCPI_PARTY_ID", "PLG").strip()
OCPI_COUNTRY_CODE: str = os.getenv("OCPI_COUNTRY_CODE", "MY").strip()

# ─── Bootstrap (Admin/Staff) ───────────────────────────────────────────────
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "").strip()
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "").strip()
ADMIN_NAME: str = os.getenv("ADMIN_NAME", "Admin").strip()
STAFF_EMAIL: str = os.getenv("STAFF_EMAIL", "").strip()
STAFF_PASSWORD: str = os.getenv("STAFF_PASSWORD", "").strip()
STAFF_NAME: str = os.getenv("STAFF_NAME", "Staff Admin").strip()

# ─── Top-up Limits (from security.py) ─────────────────────────────────────
MAX_TOPUP_PER_TRANSACTION: float = float(os.getenv("MAX_TOPUP_PER_TRANSACTION", "500"))
MAX_TOPUP_PER_DAY: float = float(os.getenv("MAX_TOPUP_PER_DAY", "2000"))

# ─── Ticket SLA ───────────────────────────────────────────────────────────
REMINDER_CHECK_MINUTES: int = int(os.getenv("REMINDER_CHECK_MINUTES", "60"))

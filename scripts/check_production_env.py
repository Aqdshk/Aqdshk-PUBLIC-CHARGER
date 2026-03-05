"""
Production environment validator for Google Cloud deployment.

Usage:
  python scripts/check_production_env.py
"""
from __future__ import annotations

import os
import sys


REQUIRED = [
    "APP_ENV",
    "JWT_SECRET_KEY",
    "PAYMENT_CALLBACK_SECRET",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "OCPP_REQUIRE_AUTH",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_EMAIL",
    "SMTP_PASSWORD",
]

RECOMMENDED = [
    "PAYMENT_BILLPLZ_API_KEY",
    "PAYMENT_BILLPLZ_API_SECRET",
    "PAYMENT_FIUU_API_KEY",
    "PAYMENT_FIUU_API_SECRET",
    "PAYMENT_TNG_API_KEY",
    "PAYMENT_TNG_API_SECRET",
    "PAYMENT_OCBC_API_KEY",
    "PAYMENT_OCBC_API_SECRET",
    "GEMINI_API_KEY",
]


def main() -> int:
    missing_required = [k for k in REQUIRED if not os.getenv(k, "").strip()]
    missing_recommended = [k for k in RECOMMENDED if not os.getenv(k, "").strip()]

    print("Required variables check:")
    if missing_required:
        for key in missing_required:
            print(f"  - MISSING: {key}")
    else:
        print("  - OK: all required variables are set")

    print("\nRecommended variables check:")
    if missing_recommended:
        for key in missing_recommended:
            print(f"  - MISSING: {key}")
    else:
        print("  - OK: all recommended variables are set")

    if missing_required:
        print("\nResult: FAIL (required environment variables missing)")
        return 1

    print("\nResult: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

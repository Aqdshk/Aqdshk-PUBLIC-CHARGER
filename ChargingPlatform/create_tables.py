#!/usr/bin/env python3
"""Utility script to create / verify all database tables."""

from sqlalchemy import inspect, text

from database import Base, engine

# Import all models so they are registered with Base.metadata
from database import (  # noqa: F401
    Charger, ChargingSession, Fault, MaintenanceRecord, MeterValue,
    Payment, Pricing, User, Vehicle, Wallet, WalletTransaction,
)


def main():
    print("Checking database connection...")
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT DATABASE()"))
            db_name = result.scalar()
            print(f"Connected to MySQL database: {db_name}")
        except Exception:
            print("Connected to SQLite database")

    print("\nCreating tables...")
    Base.metadata.create_all(bind=engine, checkfirst=True)

    print("\nVerifying tables...")
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())

    if tables:
        print(f"\n  {len(tables)} tables found:")
        for table in tables:
            print(f"    - {table}")
    else:
        print("\n  No tables found!")


if __name__ == "__main__":
    main()

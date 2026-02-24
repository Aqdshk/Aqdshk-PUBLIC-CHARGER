"""
Database migration script — adds missing columns to existing SQLite tables.
Run once: python migrate_db.py
"""
import sqlite3
import sys

DB_PATH = "charging_platform.db"


def get_existing_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table, column, col_type, default=None):
    existing = get_existing_columns(cursor, table)
    if column not in existing:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
        cursor.execute(sql)
        print(f"  + Added {table}.{column} ({col_type})")
        return True
    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    changes = 0

    print("Running database migration...\n")

    # --- charging_sessions ---
    print("[charging_sessions]")
    if add_column_if_missing(c, "charging_sessions", "user_id", "VARCHAR"):
        changes += 1
    if add_column_if_missing(c, "charging_sessions", "payment_id", "INTEGER"):
        changes += 1

    # --- users ---
    print("[users]")
    if add_column_if_missing(c, "users", "failed_login_attempts", "INTEGER", 0):
        changes += 1
    if add_column_if_missing(c, "users", "locked_until", "DATETIME"):
        changes += 1
    if add_column_if_missing(c, "users", "is_admin", "BOOLEAN", 0):
        changes += 1

    # --- wallets ---
    print("[wallets]")
    if add_column_if_missing(c, "wallets", "currency", "VARCHAR(10)", "'MYR'"):
        changes += 1

    # --- wallet_transactions ---
    print("[wallet_transactions]")
    if add_column_if_missing(c, "wallet_transactions", "idempotency_key", "VARCHAR(100)"):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "payment_method", "VARCHAR(50)"):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "payment_gateway", "VARCHAR(50)"):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "gateway_reference", "VARCHAR(255)"):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "points_before", "INTEGER", 0):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "points_after", "INTEGER", 0):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "balance_before", "NUMERIC(12,2)", 0):
        changes += 1
    if add_column_if_missing(c, "wallet_transactions", "balance_after", "NUMERIC(12,2)", 0):
        changes += 1

    # --- payment_transactions ---
    print("[payment_transactions]")
    if add_column_if_missing(c, "payment_transactions", "idempotency_key", "VARCHAR(100)"):
        changes += 1
    if add_column_if_missing(c, "payment_transactions", "expired_at", "DATETIME"):
        changes += 1
    if add_column_if_missing(c, "payment_transactions", "ip_address", "VARCHAR(50)"):
        changes += 1
    if add_column_if_missing(c, "payment_transactions", "user_agent", "VARCHAR(500)"):
        changes += 1

    # --- support_tickets ---
    print("[support_tickets]")
    if add_column_if_missing(c, "support_tickets", "source", "VARCHAR(30)", "'manual'"):
        changes += 1
    if add_column_if_missing(c, "support_tickets", "resolution_notes", "TEXT"):
        changes += 1
    if add_column_if_missing(c, "support_tickets", "satisfaction_rating", "INTEGER"):
        changes += 1
    if add_column_if_missing(c, "support_tickets", "first_response_at", "DATETIME"):
        changes += 1

    # --- Create audit_logs table if not exists ---
    print("[audit_logs]")
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                user_email VARCHAR(255),
                staff_id INTEGER,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50),
                resource_id INTEGER,
                description TEXT,
                amount NUMERIC(12,2),
                ip_address VARCHAR(50),
                user_agent VARCHAR(500),
                old_value TEXT,
                new_value TEXT
            )
        """)
        print("  + Created audit_logs table")
        changes += 1
    else:
        print("  (already exists)")

    conn.commit()
    conn.close()

    if changes > 0:
        print(f"\nMigration complete -- {changes} changes applied.")
    else:
        print("\nDatabase is already up to date. No changes needed.")


if __name__ == "__main__":
    main()

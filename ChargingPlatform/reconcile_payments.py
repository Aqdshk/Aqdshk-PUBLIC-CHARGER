"""
PlagSini EV — Payment Reconciliation Script

Compares payment_transactions vs wallet_transactions for a date range.
Useful for finance: verify gateway success amount matches wallet credits.

Usage examples:
  python reconcile_payments.py --from 2026-03-01 --to 2026-03-01
  python reconcile_payments.py --from 2026-03-01 --to 2026-03-07 --csv out.csv
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def run_reconciliation(start_date: datetime, end_date: datetime) -> Dict:
    database_url = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://charging_user:charging_password@localhost:3306/charging_platform",
    )
    engine = create_engine(database_url, pool_pre_ping=True)

    # Inclusive date range [start_date, end_date + 1 day)
    window_start = start_date
    window_end = end_date + timedelta(days=1)

    rows: List[Dict] = []
    totals = {
        "gateway_success_amount": Decimal("0.00"),
        "wallet_credit_amount": Decimal("0.00"),
        "matched_count": 0,
        "mismatch_count": 0,
    }

    query = text(
        """
        SELECT
            pt.transaction_ref,
            pt.user_id,
            pt.gateway_name,
            pt.status AS payment_status,
            pt.amount AS payment_amount,
            pt.paid_at,
            pt.wallet_transaction_id,
            wt.id AS wt_id,
            wt.amount AS wallet_amount,
            wt.status AS wallet_status
        FROM payment_transactions pt
        LEFT JOIN wallet_transactions wt
            ON wt.id = pt.wallet_transaction_id
        WHERE pt.created_at >= :window_start
          AND pt.created_at < :window_end
          AND pt.purpose = 'topup'
        ORDER BY pt.created_at ASC
        """
    )

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {"window_start": window_start, "window_end": window_end},
        )
        for r in result.mappings():
            payment_amount = _to_decimal(r["payment_amount"])
            wallet_amount = _to_decimal(r["wallet_amount"])
            payment_status = (r["payment_status"] or "").lower()
            wallet_status = (r["wallet_status"] or "").lower()

            is_success = payment_status == "success"
            is_wallet_credit_ok = r["wt_id"] is not None and wallet_status == "completed"
            amount_match = payment_amount == wallet_amount

            matched = is_success and is_wallet_credit_ok and amount_match

            if is_success:
                totals["gateway_success_amount"] += payment_amount
            if is_wallet_credit_ok:
                totals["wallet_credit_amount"] += wallet_amount

            if matched:
                totals["matched_count"] += 1
            else:
                totals["mismatch_count"] += 1

            rows.append(
                {
                    "transaction_ref": r["transaction_ref"],
                    "user_id": r["user_id"],
                    "gateway_name": r["gateway_name"],
                    "payment_status": payment_status,
                    "payment_amount": f"{payment_amount:.2f}",
                    "wallet_transaction_id": r["wallet_transaction_id"] or "",
                    "wallet_status": wallet_status,
                    "wallet_amount": f"{wallet_amount:.2f}",
                    "matched": "yes" if matched else "no",
                    "reason": _explain_mismatch(
                        is_success=is_success,
                        is_wallet_credit_ok=is_wallet_credit_ok,
                        amount_match=amount_match,
                    ),
                }
            )

    variance = totals["gateway_success_amount"] - totals["wallet_credit_amount"]
    return {
        "from": window_start.date().isoformat(),
        "to": end_date.date().isoformat(),
        "rows": rows,
        "totals": {
            **totals,
            "gateway_success_amount": f"{totals['gateway_success_amount']:.2f}",
            "wallet_credit_amount": f"{totals['wallet_credit_amount']:.2f}",
            "variance": f"{variance:.2f}",
        },
    }


def _load_settlement_csv(path: str, ref_col: str, amount_col: str, status_col: str) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = _to_ref_key(row.get(ref_col, ""))
            if not ref:
                continue
            data[ref] = {
                "raw_ref": row.get(ref_col, ""),
                "amount": row.get(amount_col, ""),
                "status": row.get(status_col, ""),
            }
    return data


def _to_ref_key(value: str) -> str:
    return (value or "").strip().lower()


def _settlement_ok(status_value: str) -> bool:
    status = (status_value or "").strip().lower()
    return status in {"success", "paid", "completed", "settled", "approved", "ok", "00", "1", "true"}


def merge_settlement(
    report: Dict,
    settlement_csv: str,
    ref_col: str,
    amount_col: str,
    status_col: str,
) -> Dict:
    settlement = _load_settlement_csv(settlement_csv, ref_col, amount_col, status_col)
    rows = report["rows"]

    matched_settlement = 0
    missing_in_settlement = 0
    status_mismatch = 0
    amount_mismatch = 0

    for row in rows:
        tx_ref = _to_ref_key(row.get("transaction_ref", ""))
        st = settlement.get(tx_ref)
        if not st:
            row["settlement_status"] = "missing"
            row["settlement_amount"] = ""
            row["settlement_match"] = "no"
            row["reason"] = ",".join(filter(None, [row.get("reason", ""), "missing_in_settlement"]))
            missing_in_settlement += 1
            continue

        row["settlement_status"] = st["status"]
        row["settlement_amount"] = st["amount"]

        internal_success = (row.get("payment_status") or "").lower() == "success"
        settlement_success = _settlement_ok(st["status"])
        if internal_success != settlement_success:
            row["settlement_match"] = "no"
            row["reason"] = ",".join(filter(None, [row.get("reason", ""), "settlement_status_mismatch"]))
            status_mismatch += 1
            continue

        try:
            internal_amount = _to_decimal(row.get("payment_amount", "0"))
            st_amount = _to_decimal(st.get("amount", "0"))
        except Exception:
            internal_amount = Decimal("0.00")
            st_amount = Decimal("0.00")
        if internal_amount != st_amount:
            row["settlement_match"] = "no"
            row["reason"] = ",".join(filter(None, [row.get("reason", ""), "settlement_amount_mismatch"]))
            amount_mismatch += 1
            continue

        row["settlement_match"] = "yes"
        matched_settlement += 1

    report["totals"]["settlement_matched_count"] = matched_settlement
    report["totals"]["settlement_missing_count"] = missing_in_settlement
    report["totals"]["settlement_status_mismatch_count"] = status_mismatch
    report["totals"]["settlement_amount_mismatch_count"] = amount_mismatch
    return report


def _explain_mismatch(is_success: bool, is_wallet_credit_ok: bool, amount_match: bool) -> str:
    if is_success and is_wallet_credit_ok and amount_match:
        return ""
    reasons = []
    if not is_success:
        reasons.append("payment_not_success")
    if not is_wallet_credit_ok:
        reasons.append("wallet_credit_missing_or_not_completed")
    if is_wallet_credit_ok and not amount_match:
        reasons.append("amount_mismatch")
    return ",".join(reasons)


def _write_csv(path: str, rows: List[Dict]) -> None:
    fieldnames = [
        "transaction_ref",
        "user_id",
        "gateway_name",
        "payment_status",
        "payment_amount",
        "wallet_transaction_id",
        "wallet_status",
        "wallet_amount",
        "matched",
        "reason",
        "settlement_status",
        "settlement_amount",
        "settlement_match",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile payment transactions vs wallet credits.")
    parser.add_argument("--from", dest="start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--csv", dest="csv_path", default="", help="Optional CSV output path")
    parser.add_argument("--settlement-csv", dest="settlement_csv", default="", help="Optional gateway settlement CSV")
    parser.add_argument("--settlement-ref-col", dest="settlement_ref_col", default="transaction_ref", help="Settlement reference column name")
    parser.add_argument("--settlement-amount-col", dest="settlement_amount_col", default="amount", help="Settlement amount column name")
    parser.add_argument("--settlement-status-col", dest="settlement_status_col", default="status", help="Settlement status column name")
    args = parser.parse_args()

    start_date = _parse_date(args.start)
    end_date = _parse_date(args.end)
    if end_date < start_date:
        raise SystemExit("--to date must be >= --from date")

    report = run_reconciliation(start_date, end_date)
    if args.settlement_csv:
        report = merge_settlement(
            report,
            settlement_csv=args.settlement_csv,
            ref_col=args.settlement_ref_col,
            amount_col=args.settlement_amount_col,
            status_col=args.settlement_status_col,
        )
    totals = report["totals"]

    print(f"Reconciliation window: {report['from']} -> {report['to']}")
    print(f"Matched rows: {totals['matched_count']}")
    print(f"Mismatched rows: {totals['mismatch_count']}")
    print(f"Gateway success amount: RM {totals['gateway_success_amount']}")
    print(f"Wallet credited amount: RM {totals['wallet_credit_amount']}")
    print(f"Variance: RM {totals['variance']}")
    if args.settlement_csv:
        print(f"Settlement matched: {totals.get('settlement_matched_count', 0)}")
        print(f"Settlement missing: {totals.get('settlement_missing_count', 0)}")
        print(f"Settlement status mismatches: {totals.get('settlement_status_mismatch_count', 0)}")
        print(f"Settlement amount mismatches: {totals.get('settlement_amount_mismatch_count', 0)}")

    if args.csv_path:
        _write_csv(args.csv_path, report["rows"])
        print(f"CSV written: {args.csv_path}")


if __name__ == "__main__":
    main()

"""
Staging smoke check for PUBLIC CHARGER RND.

Usage:
  python scripts/staging_smoke_check.py
"""
from __future__ import annotations

import json
import sys
from typing import List, Tuple

import requests


def check(name: str, method: str, url: str, expected: Tuple[int, ...], **kwargs) -> Tuple[bool, str]:
    try:
        resp = requests.request(method, url, timeout=12, **kwargs)
        ok = resp.status_code in expected
        detail = f"{resp.status_code} {resp.text[:180].strip()}"
        return ok, f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
    except Exception as exc:
        return False, f"[FAIL] {name}: exception {exc}"


def main() -> int:
    tests: List[Tuple[str, str, str, Tuple[int, ...], dict]] = [
        ("ChargingPlatform docs", "GET", "http://localhost:8000/docs", (200,), {}),
        ("CustomerService health", "GET", "http://localhost:8001/health", (200,), {}),
        ("AppEV web", "GET", "http://localhost:3000/", (200,), {}),
        (
            "OCPP reset unauthenticated blocked",
            "POST",
            "http://localhost:8000/api/ocpp/CHARGER_001/reset",
            (401, 403),
            {"json": {"type": "Soft"}},
        ),
        (
            "Chatbot welcome",
            "POST",
            "http://localhost:8001/api/bot/welcome",
            (200,),
            {},
        ),
        (
            "Chatbot basic chat",
            "POST",
            "http://localhost:8001/api/bot/chat",
            (200,),
            {"json": {"message": "Hi", "conversation_history": []}},
        ),
    ]

    failures = 0
    for name, method, url, expected, kwargs in tests:
        ok, line = check(name, method, url, expected, **kwargs)
        print(line.encode("ascii", errors="replace").decode("ascii"))
        if not ok:
            failures += 1

    summary = {"total": len(tests), "failed": failures, "passed": len(tests) - failures}
    print("Summary:", json.dumps(summary))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

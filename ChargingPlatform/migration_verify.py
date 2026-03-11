"""
PlagSini EV — Alembic Migration Verification

Runs a safe migration cycle on a temporary SQLite database:
1) upgrade head
2) downgrade base
3) upgrade head

Usage:
  python migration_verify.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TMP_DB = ROOT / "data" / "migration_verify.db"


def _run(cmd: list[str], env: dict) -> None:
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip())
        raise SystemExit(result.returncode)


def main() -> None:
    TMP_DB.parent.mkdir(parents=True, exist_ok=True)
    if TMP_DB.exists():
        TMP_DB.unlink()

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{TMP_DB.as_posix()}"

    print(f"Using temporary database: {TMP_DB}")
    _run([sys.executable, "-m", "alembic", "upgrade", "head"], env)
    _run([sys.executable, "-m", "alembic", "downgrade", "base"], env)
    _run([sys.executable, "-m", "alembic", "upgrade", "head"], env)
    print("Migration verification cycle passed.")


if __name__ == "__main__":
    main()

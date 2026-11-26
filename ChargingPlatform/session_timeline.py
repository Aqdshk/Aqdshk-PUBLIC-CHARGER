"""Everything that happened during one charging session, in one place.

Built after Voltality's UAT on 2026-10-09. Answering "why did this session
cost that" meant SSHing to the server, grepping container logs by hand and
cross-reading the database, which only one person could do and only while the
logs were still in the container. Operators watching a partner test had no way
to see what the charger and the partner actually exchanged.

Loki already holds the application logs, so the timeline is assembled from the
session row plus the log lines for that session's own window.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")

# Session and meter columns hold Malaysia wall time; Loki indexes in UTC.
_MYT_OFFSET = timedelta(hours=8)

# Traffic that happens whatever the session is doing. Keeping it would bury
# the handful of lines that explain the charge.
_NOISE = re.compile(
    r"Heartbeat"
    r"|GET /ocpi/"
    r"|GET /api/"
    r"|/health"
    r"|Updated last_heartbeat",
    re.I,
)

# What each line means, in the order we try to match. The label is what the
# operator reads; the kind drives the colour.
_EVENTS = [
    ("RemoteStartTransaction",   "command",  "Remote start sent to the charger"),
    ("RemoteStopTransaction",    "command",  "Remote stop sent to the charger"),
    ("commands/START_SESSION",   "partner",  "Partner asked us to start"),
    ("commands/STOP_SESSION",    "partner",  "Partner asked us to stop"),
    ('"StartTransaction"',       "charger",  "Charger started the transaction"),
    ('"StopTransaction"',        "charger",  "Charger ended the transaction"),
    ('"status":"Accepted"',      "charger",  "Charger accepted"),
    ('"status":"Rejected"',      "error",    "Charger rejected"),
    ("401 Unauthorized",         "error",    "Partner refused our callback"),
    ("[idle-fee]",               "billing",  "Idle fee"),
    ("StatusNotification",       "status",   "Connector status"),
    ("disconnected",             "error",    "Charger lost its connection"),
    ("BootNotification",         "status",   "Charger rebooted"),
    ("Orphan session",           "status",   "Session closed on reboot"),
    ("MeterValues",              "meter",    "Meter reading"),
]

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")


def _classify(line: str):
    for needle, kind, label in _EVENTS:
        if needle in line:
            return kind, label
    return "other", None


def _window(sess) -> tuple:
    """The UTC span worth reading for this session, with a little margin."""
    start = sess.start_time or datetime.utcnow()
    end = sess.unplugged_at or sess.stop_time or datetime.utcnow()
    # Stored as Malaysia wall time, so shift to the UTC Loki indexes by.
    return (start - _MYT_OFFSET - timedelta(minutes=1),
            end - _MYT_OFFSET + timedelta(minutes=3))


async def fetch_log_lines(charge_point_id: str, start_utc: datetime,
                          end_utc: datetime, limit: int = 600) -> List[str]:
    """Raw log lines mentioning this charger, oldest first.

    Returns an empty list rather than raising: a timeline without its logs is
    still worth showing, and this sits behind an operator screen.
    """
    query = '{container="plagsini-api"} |= "%s"' % charge_point_id.replace('"', '')
    params = {
        "query": query,
        "start": str(int(start_utc.timestamp() * 1_000_000_000)),
        "end": str(int(end_utc.timestamp() * 1_000_000_000)),
        "limit": str(limit),
        "direction": "forward",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
            r.raise_for_status()
            data = r.json().get("data", {}).get("result", [])
    except Exception as e:
        logger.warning("[timeline] Loki query failed: %s", e)
        return []

    rows = []
    for stream in data:
        for ts_ns, line in stream.get("values", []):
            rows.append((int(ts_ns), line))
    rows.sort(key=lambda x: x[0])
    return [line for _, line in rows]


def build_events(lines: List[str]) -> List[Dict[str, Any]]:
    """Turn raw lines into labelled events, dropping the routine traffic."""
    out = []
    for line in lines:
        if _NOISE.search(line):
            continue
        kind, label = _classify(line)
        if label is None:
            continue
        m = _TS.match(line)
        out.append({
            "at": f"{m.group(1)}.{m.group(2)}" if m else "",
            "kind": kind,
            "label": label,
            "line": line.strip(),
        })
    return out

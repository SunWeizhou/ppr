"""Pure constants and utility functions extracted from state_store.py.

These have zero SQLite dependency — safe to import from anywhere
without triggering database initialization.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── Queue / job status value tuples ──────────────────────────────────

JOB_STATUS_VALUES = ("queued", "running", "succeeded", "degraded", "failed")
QUEUE_STATUS_VALUES = ("Inbox", "Completed")


# ── Timestamp helpers ────────────────────────────────────────────────


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"


def utc_bounds_for_local_date(date_str: str) -> tuple[str, str]:
    """Return UTC timestamp bounds for a YYYY-MM-DD date in system local time."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    local_tz = datetime.now().astimezone().tzinfo
    start_local = datetime.combine(day, datetime.min.time()).replace(tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(microsecond=0)
    end_utc = end_local.astimezone(timezone.utc).replace(microsecond=0)
    return start_utc.isoformat() + "Z", end_utc.isoformat() + "Z"


def to_json(value: Optional[object], default: object) -> str:
    return json.dumps(value if value is not None else default, ensure_ascii=False)


# ── Paper ID helpers ─────────────────────────────────────────────────


def canonical_paper_id(paper_id: str) -> str:
    """Strip version suffix and normalise an arXiv paper ID."""
    value = str(paper_id or "").strip()
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", value)
    if match:
        return match.group(1)
    return re.sub(r"v\d+$", "", value)

"""
Falcon Agency — IST (Indian Standard Time) Utilities
=====================================================

ALL time operations across the agency use this module.
IST = UTC+05:30  (no daylight saving)

Usage:
    from core.ist_time import now_ist, today_ist, now_ist_str, IST

    dt   = now_ist()           # timezone-aware datetime in IST
    s    = now_ist_str()       # "2026-03-02T22:41:43+05:30"
    date = today_ist()         # "2026-03-02"
    hour = now_ist().hour      # 22  ← IST hour, always correct
"""

from datetime import datetime, timezone, timedelta

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime:
    """Return current IST datetime (timezone-aware)."""
    return datetime.now(IST)


def now_ist_str() -> str:
    """ISO-8601 IST string — e.g. '2026-03-02T22:41:43+05:30'. For JSON logs."""
    return now_ist().isoformat()


def today_ist() -> str:
    """Current IST date as YYYY-MM-DD."""
    return now_ist().strftime("%Y-%m-%d")


def month_ist() -> str:
    """Current IST year-month as YYYY-MM."""
    return now_ist().strftime("%Y-%m")


def ist_display() -> str:
    """Human-friendly IST string — e.g. '02 Mar 2026, 10:41 PM IST'."""
    return now_ist().strftime("%d %b %Y, %I:%M %p IST")


def ist_from_iso(iso_str: str) -> datetime:
    """
    Parse an ISO-8601 string → IST-aware datetime.
    Handles naive strings (assumes they were IST), UTC strings, and
    already-IST strings.
    """
    if not iso_str:
        return now_ist()
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            # Naive → assume IST (legacy timestamps from this codebase)
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        return now_ist()


def is_write_window() -> bool:
    """
    Returns True if the current IST time is in the WHM write window (2:00–4:00 AM).
    Product updates to WHM server should only run during this window.
    """
    h = now_ist().hour
    return 2 <= h < 4


def minutes_until_write_window() -> int:
    """Minutes until the next 2:00 AM IST write window opens."""
    n = now_ist()
    target_hour = 2
    if n.hour < target_hour:
        delta_min = (target_hour - n.hour) * 60 - n.minute
    elif n.hour >= 4:
        # Next day 2 AM
        delta_min = (24 - n.hour + target_hour) * 60 - n.minute
    else:
        # We're inside the window
        return 0
    return max(0, delta_min)

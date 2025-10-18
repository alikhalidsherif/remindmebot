"""Formatting helpers for user-facing messages."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M %Z"


def format_datetime(value: datetime, tz_name: str | None = None) -> str:
    """Return a formatted datetime string for display."""

    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
            value = value.astimezone(tz)
        except Exception:  # pragma: no cover - defensive, should not happen
            pass
    return value.strftime(DEFAULT_DATETIME_FORMAT)

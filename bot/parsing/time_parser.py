"""High level parsing entrypoint for time expressions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from dateparser import parse as dateparse
from zoneinfo import ZoneInfo

from .recurrence import RecurrenceContext, RecurrenceParseError, parse_recurrence
from .solar import Location, SolarParseError, parse_solar_expression, compute_next_solar_time


class TimeParseError(ValueError):
    """Raised when the time expression cannot be interpreted."""


@dataclass(slots=True)
class ParsedTime:
    """Structured result from parsing a time expression."""

    next_run_at: datetime
    local_time: datetime
    timezone: str
    is_recurring: bool
    recurrence: Optional[dict[str, Any]]
    description: str
    solar_event: Optional[str] = None
    solar_offset_seconds: Optional[int] = None


def parse_time_expression(
    expression: str,
    *,
    timezone: str,
    now: Optional[datetime] = None,
    location: Location | None = None,
) -> ParsedTime:
    """Parse a time expression into a concrete next run and recurrence info."""

    if not expression or not expression.strip():
        raise TimeParseError("Time expression cannot be empty.")

    tz = ZoneInfo(timezone)
    reference = (now or datetime.now(tz)).astimezone(tz)

    text = expression.strip()
    lowered = text.lower()

    if lowered.startswith("every"):
        context = RecurrenceContext(timezone=tz.key, now=reference, location=location)
        try:
            recurrence_result = parse_recurrence(text, context)
        except RecurrenceParseError as exc:  # pragma: no cover - simple passthrough
            raise TimeParseError(str(exc)) from exc
        next_local = recurrence_result.next_occurrence.astimezone(tz)
        next_utc = next_local.astimezone(ZoneInfo("UTC"))
        return ParsedTime(
            next_run_at=next_utc,
            local_time=next_local,
            timezone=tz.key,
            is_recurring=True,
            recurrence=recurrence_result.rule,
            description=text,
        )

    solar_expression = parse_solar_expression(lowered)
    if solar_expression is not None:
        try:
            solar_result = compute_next_solar_time(solar_expression, tz.key, reference, location=location)
        except SolarParseError as exc:  # pragma: no cover - defensive
            raise TimeParseError(str(exc)) from exc
        next_local = solar_result.when.astimezone(tz)
        next_utc = next_local.astimezone(ZoneInfo("UTC"))
        return ParsedTime(
            next_run_at=next_utc,
            local_time=next_local,
            timezone=tz.key,
            is_recurring=False,
            recurrence=None,
            description=text,
            solar_event=solar_result.event,
            solar_offset_seconds=int(solar_result.offset.total_seconds()),
        )

    parsed = dateparse(
        text,
        settings={
            "TIMEZONE": tz.key,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": reference,
        },
    )
    if parsed is None:
        raise TimeParseError("Could not parse time expression.")

    parsed_local = parsed.astimezone(tz)
    if parsed_local <= reference:
        raise TimeParseError("Time expression must refer to the future.")

    parsed_utc = parsed_local.astimezone(ZoneInfo("UTC"))
    return ParsedTime(
        next_run_at=parsed_utc,
        local_time=parsed_local,
        timezone=tz.key,
        is_recurring=False,
        recurrence=None,
        description=text,
    )

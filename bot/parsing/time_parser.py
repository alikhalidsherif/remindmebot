"""High level parsing entrypoint for time expressions.

The parser understands absolute dates, clock times, relative offsets,
parts of the day, weekday references, solar events and recurring rules.
Anything that is not recognised by the hand written layers falls back to
``dateparser`` so unusual but valid phrasings keep working.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from dateparser import parse as dateparse

from . import lexicon
from .recurrence import RecurrenceContext, RecurrenceParseError, parse_recurrence
from .solar import (
    Location,
    SolarExpression,
    SolarParseError,
    compute_next_solar_time,
    compute_solar_time_on_date,
    parse_solar_expression,
)


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


_RECURRENCE_START_RE = re.compile(
    r"^(?:every|each)\b|^(?:daily|nightly|hourly|weekly|monthly|yearly|annually)\b"
)

_DURATION_UNITS: dict[str, str] = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "wk": "weeks",
    "wks": "weeks",
    "week": "weeks",
    "weeks": "weeks",
    "mo": "months",
    "mos": "months",
    "month": "months",
    "months": "months",
    "y": "years",
    "yr": "years",
    "yrs": "years",
    "year": "years",
    "years": "years",
}

_DURATION_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?|a couple of|a couple|a few|a handful of|half|"
    r"a quarter|quarter|an?|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|fifteen|twenty|thirty|forty|fifty)\s*"
    r"(?P<unit>seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|"
    r"weeks?|wks?|w|months?|mos?|mo|years?|yrs?|y)\b",
    re.IGNORECASE,
)

_SOLAR_SEARCH_RE = re.compile(
    r"\b(?P<event>sunrise|sunset|dawn|dusk)\b"
    r"(?:\s*(?P<sign>[+-])\s*(?P<amount>\d+)\s*"
    r"(?P<unit>m|min|mins|minutes|h|hr|hrs|hour|hours))?"
)

_ISO_RE = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
    r"(?:[t ](?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?"
    r"(?P<tz>z|[+-]\d{2}:?\d{2})?$"
)

_NUMERIC_DATE_RE = re.compile(
    r"^(?P<first>\d{1,2})[/\-.](?P<second>\d{1,2})(?:[/\-.](?P<year>\d{2,4}))?"
    r"(?:[\s]+(?:at\s+)?(?P<time>.+))?$"
)

_MONTH_DAY_RE = re.compile(
    rf"^(?:"
    rf"(?P<month_name>{lexicon.MONTH_ALTERNATION})\s+(?:the\s+)?"
    rf"(?P<day_numeric>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"|(?:the\s+)?(?P<day_named>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?"
    rf"(?P<month_number>{lexicon.MONTH_ALTERNATION})"
    rf")(?:\s+(?P<year>\d{{4}}))?"
    r"(?:[\s]+(?:at\s+)?(?P<time>.+))?$"
)

_MONTH_ONLY_RE = re.compile(rf"^(?P<month>{lexicon.MONTH_ALTERNATION})$")

_ORDINAL_DAY_RE = re.compile(r"^(?:the\s+)?(?P<day>\d{1,2})(?:st|nd|rd|th)$")

_WEEKDAY_RE = re.compile(
    rf"^(?:(?P<modifier>next|this|coming|upcoming|following)\s+)?"
    rf"(?P<weekday>{lexicon.WEEKDAY_ALTERNATION})"
    r"(?:\s+(?P<week>next|this)\s+week)?$"
)


@dataclass(slots=True)
class _DayResolution:
    day: date
    explicit: bool = False
    roll_days: Optional[int] = None
    default_time: Optional[time] = None


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

    raw = expression.strip()
    text = lexicon.normalize(raw)
    if not text:
        raise TimeParseError("Time expression cannot be empty.")

    if _RECURRENCE_START_RE.match(text):
        context = RecurrenceContext(timezone=tz.key, now=reference, location=location)
        try:
            recurrence_result = parse_recurrence(text, context)
        except RecurrenceParseError as exc:
            raise TimeParseError(str(exc)) from exc
        return _build_recurring_result(recurrence_result, tz, raw)

    relative = _parse_relative(text, reference)
    if relative is not None:
        if relative <= reference:
            relative = reference + timedelta(seconds=1)
        return _build_result(relative, tz, raw)

    absolute = _parse_absolute(text, reference, tz, location)
    if absolute is not None:
        value, solar_expression = absolute
        return _build_result(value, tz, raw, solar=solar_expression)

    parsed = dateparse(
        raw,
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
    return _build_result(parsed_local, tz, raw)


def _build_result(
    local_time: datetime,
    tz: ZoneInfo,
    description: str,
    solar: Optional[SolarExpression] = None,
) -> ParsedTime:
    local = local_time.astimezone(tz)
    return ParsedTime(
        next_run_at=local.astimezone(ZoneInfo("UTC")),
        local_time=local,
        timezone=tz.key,
        is_recurring=False,
        recurrence=None,
        description=description,
        solar_event=solar.event if solar is not None else None,
        solar_offset_seconds=(
            int(solar.offset.total_seconds()) if solar is not None else None
        ),
    )


def _build_recurring_result(result, tz: ZoneInfo, description: str) -> ParsedTime:
    next_local = result.next_occurrence.astimezone(tz)
    time_spec = result.rule.get("time") if isinstance(result.rule, dict) else None
    solar_event = None
    solar_offset = None
    if isinstance(time_spec, dict) and time_spec.get("solar_event"):
        solar_event = str(time_spec["solar_event"])
        solar_offset = int(time_spec.get("offset_seconds", 0))
    return ParsedTime(
        next_run_at=next_local.astimezone(ZoneInfo("UTC")),
        local_time=next_local,
        timezone=tz.key,
        is_recurring=True,
        recurrence=result.rule,
        description=description,
        solar_event=solar_event,
        solar_offset_seconds=solar_offset,
    )


# ---------------------------------------------------------------------------
# Relative offsets
# ---------------------------------------------------------------------------


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _parse_duration_parts(text: str) -> Optional[dict[str, float]]:
    value = text.strip()
    if not value:
        return None

    value = re.sub(
        r"\b(an?|one|\d+(?:\.\d+)?)\s+(hour|day|week|month|year)s?\s+and\s+a\s+half\b",
        r"1.5 \2s",
        value,
    )
    value = re.sub(
        r"\bhalf an? (hour|day|week|month|year)\b",
        lambda match: {
            "hour": "30 minutes",
            "day": "12 hours",
            "week": "84 hours",
            "month": "15 days",
            "year": "6 months",
        }[match.group(1)],
        value,
    )
    value = re.sub(r"\b(?:a |one )?quarter (?:of )?an? hour\b", "15 minutes", value)

    parts: dict[str, float] = {}
    position = 0
    for match in _DURATION_RE.finditer(value):
        gap = value[position : match.start()].strip(" ,+&")
        if gap:
            return None
        unit = _DURATION_UNITS.get(match.group("unit").lower())
        amount = lexicon.word_number(match.group("value"))
        if unit is None or amount is None:
            return None
        parts[unit] = parts.get(unit, 0.0) + amount
        position = match.end()

    if not parts:
        return None
    if value[position:].strip(" ,+&"):
        return None
    return parts


def _apply_duration(reference: datetime, parts: dict[str, float]) -> datetime:
    result = reference
    seconds = (
        parts.get("seconds", 0)
        + 60 * parts.get("minutes", 0)
        + 3600 * parts.get("hours", 0)
    )
    if seconds:
        result += timedelta(seconds=round(seconds))
    days = parts.get("days", 0) + 7 * parts.get("weeks", 0)
    if days:
        result += timedelta(days=round(days))
    months = parts.get("months", 0) + 12 * parts.get("years", 0)
    if months:
        result = _add_months(result, int(round(months)))
    return result


def _parse_relative(text: str, reference: datetime) -> Optional[datetime]:
    if text in {"now", "right now", "immediately", "asap", "as soon as possible"}:
        return reference + timedelta(seconds=1)

    body: Optional[str] = None
    match = re.match(r"^(?:in|after|within)\s+(?P<body>.+)$", text)
    if match:
        body = match.group("body")
    else:
        match = re.match(
            r"^(?P<body>.+?)\s+(?:from now|from now on|later|from here)$", text
        )
        if match:
            body = match.group("body")
        else:
            body = text

    if body is None:
        return None
    parts = _parse_duration_parts(body)
    if parts is None:
        return None
    return _apply_duration(reference, parts)


# ---------------------------------------------------------------------------
# Absolute expressions
# ---------------------------------------------------------------------------


def _parse_absolute(
    text: str,
    reference: datetime,
    tz: ZoneInfo,
    location: Location | None,
) -> Optional[tuple[datetime, Optional[SolarExpression]]]:
    explicit = _parse_explicit_datetime(text, reference, tz)
    if explicit is not None:
        if explicit <= reference:
            raise TimeParseError("Time expression must refer to the future.")
        return explicit, None

    working = text
    clock: Optional[time] = None
    part_time: Optional[time] = None
    solar: Optional[SolarExpression] = None

    solar_match = _SOLAR_SEARCH_RE.search(working)
    if solar_match:
        expression = solar_match.group("event")
        sign = solar_match.group("sign")
        amount = solar_match.group("amount")
        unit = (solar_match.group("unit") or "").lower()
        if sign and amount and unit:
            expression += sign + amount + ("h" if unit.startswith("h") else "m")
        try:
            solar = parse_solar_expression(expression)
        except SolarParseError:
            solar = None
        if solar is not None:
            working = (working[: solar_match.start()] + " " + working[solar_match.end() :]).strip()

    if re.search(r"\btonight\b", working) and clock is None:
        part_time = time(21, 0)
        working = re.sub(r"\btonight\b", "today", working)

    at_match = re.search(r"\sat\s+(?P<time>.+)$", working)
    if at_match and clock is None:
        candidate = lexicon.parse_clock(at_match.group("time"))
        if candidate is not None:
            clock = candidate
            working = working[: at_match.start()].strip()

    clock_match = lexicon.find_clock(working)
    if clock_match:
        clock = clock_match.value
        working = (working[: clock_match.start] + " " + working[clock_match.end :]).strip()

    part_match = lexicon.find_part_of_day(working)
    if part_match:
        part_time = part_match.value
        working = (working[: part_match.start] + " " + working[part_match.end :]).strip()

    if clock is None and part_time is None and solar is None:
        whole_clock = lexicon.parse_clock(working)
        if whole_clock is not None:
            clock = whole_clock
            working = ""

    working = re.sub(r"(?:^|\s)(?:at|on|by|around|about|from)\b", " ", working)
    working = re.sub(r"\s+", " ", working).strip()

    day_text = working.strip()

    if day_text and (clock is not None or part_time is not None):
        relative_base = _parse_relative(day_text, reference)
        if relative_base is not None:
            return datetime.combine(relative_base.date(), clock or part_time, tz), None

    resolution = _resolve_day(day_text, reference)
    if resolution is None:
        if clock is not None or part_time is not None or solar is not None:
            raise TimeParseError("Could not understand the date part of the expression.")
        return None

    if solar is not None:
        if not day_text:
            return (
                compute_next_solar_time(
                    solar, tz.key, reference, location=location
                ).when.astimezone(tz),
                solar,
            )
        candidate = compute_solar_time_on_date(solar, tz.key, resolution.day, location=location)
        if candidate <= reference:
            candidate += timedelta(days=1)
        return candidate.astimezone(tz), solar

    clock_value = clock or part_time or resolution.default_time
    if clock_value is None:
        clock_value = reference.replace(second=0, microsecond=0).time()

    candidate = datetime.combine(resolution.day, clock_value, tz)
    if candidate <= reference:
        if resolution.roll_days:
            candidate += timedelta(days=resolution.roll_days)
        elif resolution.explicit:
            raise TimeParseError("Time expression must refer to the future.")
        else:
            candidate += timedelta(days=1)
    return candidate, None


def _parse_explicit_datetime(
    text: str, reference: datetime, tz: ZoneInfo
) -> Optional[datetime]:
    cleaned = re.sub(r"^(?:on|by|at|for|from|in|the)\s+", "", text).strip()
    if not cleaned:
        return None

    iso = _ISO_RE.fullmatch(cleaned)
    if iso:
        try:
            value = datetime.fromisoformat(
                cleaned.replace("t", "T").replace("z", "Z")
            )
        except ValueError:
            raise TimeParseError("Invalid date.")
        if value.tzinfo is not None:
            value = value.astimezone(tz)
        elif iso.group("hour") is None:
            value = datetime.combine(value.date(), _default_time(reference), tz)
        else:
            value = value.replace(tzinfo=tz)
        return value

    numeric = _NUMERIC_DATE_RE.fullmatch(cleaned)
    if numeric:
        first = int(numeric.group("first"))
        second = int(numeric.group("second"))
        if first > 12 and second <= 12:
            month, day = second, first
        elif second > 12:
            month, day = first, second
        else:
            month, day = first, second
        year_text = numeric.group("year")
        year = None
        if year_text:
            year = int(year_text)
            if year < 100:
                year += 2000
        clock = _parse_component_time(numeric.group("time"))
        target = _resolve_calendar_date(month, day, year, reference)
        return datetime.combine(target, clock or _default_time(reference), tz)

    month_day = _MONTH_DAY_RE.fullmatch(cleaned)
    if month_day:
        month_name = month_day.group("month_name") or month_day.group("month_number")
        month = lexicon.MONTH_INDEX[month_name]
        day = int(month_day.group("day_numeric") or month_day.group("day_named"))
        year_text = month_day.group("year")
        year = int(year_text) if year_text else None
        clock = _parse_component_time(month_day.group("time"))
        target = _resolve_calendar_date(month, day, year, reference)
        return datetime.combine(target, clock or _default_time(reference), tz)

    month_only = _MONTH_ONLY_RE.fullmatch(cleaned)
    if month_only:
        month = lexicon.MONTH_INDEX[month_only.group("month")]
        target = _resolve_calendar_date(month, 1, None, reference)
        return datetime.combine(target, _default_time(reference), tz)

    ordinal_day = _ORDINAL_DAY_RE.fullmatch(cleaned)
    if ordinal_day:
        day = int(ordinal_day.group("day"))
        if not 1 <= day <= 31:
            return None
        candidate = _resolve_day_of_month(day, reference)
        return datetime.combine(candidate, _default_time(reference), tz)

    return None


def _parse_component_time(text: Optional[str]) -> Optional[time]:
    if not text:
        return None
    return lexicon.parse_clock(text)


def _default_time(reference: datetime) -> time:
    return reference.replace(second=0, microsecond=0).time()


def _resolve_calendar_date(
    month: int, day: int, year: Optional[int], reference: datetime
) -> date:
    if year is not None:
        try:
            return date(year, month, day)
        except ValueError as exc:
            raise TimeParseError("Invalid date.") from exc

    for offset in range(0, 9):
        try:
            candidate = date(reference.year + offset, month, day)
        except ValueError:
            continue
        if candidate >= reference.date():
            return candidate
    raise TimeParseError("Invalid date.")


def _resolve_day_of_month(day: int, reference: datetime) -> date:
    for month_offset in range(0, 13):
        month_index = reference.month - 1 + month_offset
        year = reference.year + month_index // 12
        month = month_index % 12 + 1
        if day > calendar.monthrange(year, month)[1]:
            continue
        candidate = date(year, month, day)
        if candidate >= reference.date():
            return candidate
    raise TimeParseError("Invalid date.")


def _resolve_day(text: str, reference: datetime) -> Optional[_DayResolution]:
    value = text.strip()
    value = re.sub(r"^(?:on|by|in|at|for|from|the)\s+", "", value).strip()
    value = re.sub(r"\s+", " ", value)

    if not value or value in {"today", "tonight", "this day"}:
        return _DayResolution(reference.date(), roll_days=1)
    if value in {"tomorrow", "tmrw", "tmr", "tom"}:
        return _DayResolution(reference.date() + timedelta(days=1), roll_days=1)
    if value in {"day after tomorrow", "overmorrow", "day after tomorrow's"}:
        return _DayResolution(reference.date() + timedelta(days=2), roll_days=1)
    if value in {"next week", "the next week"}:
        return _DayResolution(reference.date() + timedelta(days=7), explicit=True)
    if value in {"next month", "the next month"}:
        return _DayResolution(_add_months(reference, 1).date(), explicit=True)
    if value in {"next year", "the next year"}:
        return _DayResolution(_add_months(reference, 12).date(), explicit=True)
    if value in {"end of day", "end of the day", "eod"}:
        return _DayResolution(reference.date(), default_time=time(23, 59), roll_days=1)
    if value in {"end of week", "end of the week", "eow"}:
        days_ahead = (6 - reference.weekday()) % 7
        return _DayResolution(
            reference.date() + timedelta(days=days_ahead),
            default_time=time(23, 59),
            roll_days=7,
        )
    if value in {"end of month", "end of the month", "eom"}:
        last_day = calendar.monthrange(reference.year, reference.month)[1]
        return _DayResolution(reference.date().replace(day=last_day), default_time=time(23, 59))
    if value in {"end of year", "end of the year", "eoy"}:
        return _DayResolution(date(reference.year, 12, 31), default_time=time(23, 59))
    if value in {"weekend", "this weekend", "the weekend", "next weekend"}:
        days_ahead = (5 - reference.weekday()) % 7
        if value == "next weekend":
            days_ahead = days_ahead or 7
        return _DayResolution(reference.date() + timedelta(days=days_ahead), roll_days=7)

    ordinal_day = _ORDINAL_DAY_RE.fullmatch(value)
    if ordinal_day:
        day = int(ordinal_day.group("day"))
        if 1 <= day <= 31:
            return _DayResolution(
                _resolve_day_of_month(day, reference), explicit=True
            )

    weekday_match = _WEEKDAY_RE.fullmatch(value)
    if weekday_match:
        target = lexicon.WEEKDAY_INDEX[weekday_match.group("weekday")]
        modifier = weekday_match.group("modifier")
        week_modifier = weekday_match.group("week")
        days_ahead = (target - reference.weekday()) % 7
        if week_modifier == "next":
            days_ahead += 7
        elif modifier in {"next", "coming", "upcoming", "following"} and days_ahead == 0:
            days_ahead = 7
        return _DayResolution(
            reference.date() + timedelta(days=days_ahead), roll_days=7
        )

    return None

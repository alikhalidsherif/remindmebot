"""Recurrence parsing helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from dateutil import rrule
from zoneinfo import ZoneInfo

from .solar import Location, SolarExpression, compute_next_solar_time, parse_solar_expression


class RecurrenceParseError(ValueError):
    """Raised when a recurrence string cannot be parsed."""


@dataclass(slots=True)
class RecurrenceParseResult:
    """Structured recurrence definition."""

    next_occurrence: datetime
    rule: dict[str, Any]
    description: str


_WEEKDAY_PATTERN = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
)
_ORDINAL_PATTERN = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?")
_WEEKDAY_MAP = {
    "monday": rrule.MO,
    "tuesday": rrule.TU,
    "wednesday": rrule.WE,
    "thursday": rrule.TH,
    "friday": rrule.FR,
    "saturday": rrule.SA,
    "sunday": rrule.SU,
}

_WEEKDAY_INDEX_MAP = {
    0: rrule.MO,
    1: rrule.TU,
    2: rrule.WE,
    3: rrule.TH,
    4: rrule.FR,
    5: rrule.SA,
    6: rrule.SU,
}

_FREQ_NAME = {
    rrule.DAILY: "daily",
    rrule.WEEKLY: "weekly",
    rrule.MONTHLY: "monthly",
    rrule.YEARLY: "yearly",
}
_FREQ_VALUE = {value: key for key, value in _FREQ_NAME.items()}


@dataclass(slots=True)
class RecurrenceContext:
    timezone: str
    now: datetime
    location: Location | None = None


def parse_recurrence(expression: str, context: RecurrenceContext) -> RecurrenceParseResult:
    """Parse a recurrence expression."""

    expr = expression.strip().lower()
    interval, rest = _extract_interval(expr)

    if not rest:
        raise RecurrenceParseError("Recurrence pattern is incomplete.")

    rule: dict[str, Any] = {
        "type": "rrule",
        "interval": interval,
    }

    tz = ZoneInfo(context.timezone)
    now_local = context.now.astimezone(tz)

    pattern, time_component = _split_pattern_time(rest)

    solar_expression: Optional[SolarExpression] = None

    if time_component:
        solar_expression = parse_solar_expression(time_component)
        if solar_expression is None:
            at_time = _parse_time_component(time_component, tz, now_local)
            rule["time"] = {
                "hour": at_time.hour,
                "minute": at_time.minute,
                "second": at_time.second,
            }
        else:
            rule["time"] = {
                "solar_event": solar_expression.event,
                "offset_seconds": int(solar_expression.offset.total_seconds()),
            }
    else:
        raise RecurrenceParseError("Recurrence time component missing. Use 'at <time>'.")

    freq, rrule_kwargs, json_kwargs = _parse_pattern(pattern)
    rule["freq"] = _FREQ_NAME[freq]
    if json_kwargs:
        rule.update(json_kwargs)

    if solar_expression is not None:
        if freq != rrule.DAILY:
            raise RecurrenceParseError("Solar recurrences currently support daily patterns only.")
        next_occ = _next_for_solar(solar_expression, tz, now_local, interval, context.location)
    else:
        time_spec = rule["time"]
        next_occ = _next_for_rrule(tz, now_local, freq, interval, rrule_kwargs, time_spec)

    return RecurrenceParseResult(next_occurrence=next_occ, rule=rule, description=expression.strip())


def _extract_interval(expr: str) -> tuple[int, str]:
    if expr.startswith("every-"):
        rest = expr[6:]
        number_part, _, remaining = rest.partition(" ")
        if not number_part.isdigit():
            raise RecurrenceParseError("Invalid interval in recurrence expression.")
        interval = int(number_part)
        if interval < 1:
            raise RecurrenceParseError("Interval must be positive.")
        return interval, remaining.strip()
    if expr.startswith("every other "):
        return 2, expr[len("every other ") :]
    if expr.startswith("every "):
        return 1, expr[len("every ") :]
    raise RecurrenceParseError("Recurrence must start with 'every'.")


def _split_pattern_time(rest: str) -> tuple[str, str]:
    if " at " in rest:
        pattern, time_component = rest.rsplit(" at ", 1)
        return pattern.strip(), time_component.strip()
    # Try to split by last whitespace assuming trailing time token
    tokens = rest.split()
    if len(tokens) < 2:
        raise RecurrenceParseError("Unable to find time component in recurrence expression.")
    pattern = " ".join(tokens[:-1])
    time_component = tokens[-1]
    return pattern.strip(), time_component.strip()


def _parse_time_component(component: str, tz: ZoneInfo, now_local: datetime) -> datetime:
    from dateparser import parse as dateparse

    parsed = dateparse(
        component,
        settings={
            "TIMEZONE": tz.key,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now_local,
        },
    )
    if parsed is None:
        raise RecurrenceParseError("Could not parse time component for recurrence.")
    parsed = parsed.astimezone(tz)
    return parsed


def _parse_pattern(pattern: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    pattern = pattern.strip()
    rrule_kwargs: dict[str, Any] = {}
    json_kwargs: dict[str, Any] = {}

    if not pattern:
        return rrule.DAILY, rrule_kwargs, json_kwargs

    if pattern in {"day", "days", "daily"}:
        return rrule.DAILY, rrule_kwargs, json_kwargs

    if pattern in {"week", "weeks", "weekly"}:
        return rrule.WEEKLY, rrule_kwargs, json_kwargs

    if pattern in {"month", "months", "monthly"}:
        return rrule.MONTHLY, rrule_kwargs, json_kwargs

    if pattern in {"weekday", "weekdays"}:
        weekdays = [
            rrule.MO,
            rrule.TU,
            rrule.WE,
            rrule.TH,
            rrule.FR,
        ]
        rrule_kwargs["byweekday"] = weekdays
        json_kwargs["byweekday"] = [day.weekday for day in weekdays]
        return rrule.WEEKLY, rrule_kwargs, json_kwargs

    if pattern in {"weekend", "weekends"}:
        weekdays = [rrule.SA, rrule.SU]
        rrule_kwargs["byweekday"] = weekdays
        json_kwargs["byweekday"] = [day.weekday for day in weekdays]
        return rrule.WEEKLY, rrule_kwargs, json_kwargs

    day_matches = list(_WEEKDAY_PATTERN.finditer(pattern))
    if day_matches:
        weekdays_rrule: list[rrule.weekday] = []
        weekdays_json: list[int] = []
        seen: set[int] = set()
        for match in day_matches:
            weekday_obj = _WEEKDAY_MAP[match.group(0)]
            idx = weekday_obj.weekday
            if idx in seen:
                continue
            seen.add(idx)
            weekdays_rrule.append(weekday_obj)
            weekdays_json.append(idx)
        if not weekdays_rrule:
            raise RecurrenceParseError("No valid weekdays found in recurrence pattern.")
        rrule_kwargs["byweekday"] = weekdays_rrule
        json_kwargs["byweekday"] = weekdays_json
        return rrule.WEEKLY, rrule_kwargs, json_kwargs

    if "month" in pattern and "on" in pattern:
        ordinals = _extract_ordinals(pattern)
        if not ordinals:
            raise RecurrenceParseError("No day-of-month found in recurrence pattern.")
        rrule_kwargs["bymonthday"] = ordinals
        json_kwargs["bymonthday"] = ordinals
        return rrule.MONTHLY, rrule_kwargs, json_kwargs

    raise RecurrenceParseError("Unsupported recurrence pattern.")


def _extract_ordinals(pattern: str) -> list[int]:
    ordinals: list[int] = []
    for match in _ORDINAL_PATTERN.finditer(pattern):
        value = int(match.group(1))
        if 1 <= value <= 31:
            ordinals.append(value)
    return ordinals


def _next_for_rrule(
    tz: ZoneInfo,
    now_local: datetime,
    freq: rrule.FREQ,
    interval: int,
    kwargs: dict[str, Any],
    time_component: dict[str, Any],
) -> datetime:
    hour = time_component["hour"]
    minute = time_component["minute"]
    second = time_component["second"]
    dtstart = now_local.replace(hour=hour, minute=minute, second=second, microsecond=0)
    rule = rrule.rrule(freq, interval=interval, dtstart=dtstart, **kwargs)
    next_dt = rule.after(now_local, include=False)
    return next_dt.astimezone(tz)


def _next_for_solar(
    solar_expression: SolarExpression,
    tz: ZoneInfo,
    now_local: datetime,
    interval: int,
    location: Location | None,
) -> datetime:
    result = compute_next_solar_time(solar_expression, tz.key, now_local, location=location)
    if interval == 1:
        return result.when
    # For interval > 1, add multiples of days
    delta_days = max(interval - 1, 0)
    candidate = result.when
    if delta_days:
        candidate += timedelta(days=delta_days)
    if candidate <= now_local:
        candidate += timedelta(days=interval)
    return candidate


def compute_next_occurrence_from_rule(
    rule: dict[str, Any],
    timezone: str,
    *,
    after: datetime,
    location: Location | None = None,
) -> datetime:
    """Compute the next occurrence for a stored recurrence rule."""

    if rule.get("type") != "rrule":
        raise RecurrenceParseError("Unsupported recurrence rule type.")

    freq_value = _FREQ_VALUE.get(rule.get("freq"))
    if freq_value is None:
        raise RecurrenceParseError("Recurrence frequency missing or invalid.")

    interval = int(rule.get("interval", 1))
    time_spec = rule.get("time")
    if not isinstance(time_spec, dict):
        raise RecurrenceParseError("Recurrence time specification missing.")

    tz = ZoneInfo(timezone)
    after_local = after.astimezone(tz)

    if "solar_event" in time_spec:
        solar_expression = SolarExpression(
            event=time_spec["solar_event"],
            offset=timedelta(seconds=int(time_spec.get("offset_seconds", 0))),
        )
        if freq_value != rrule.DAILY:
            raise RecurrenceParseError("Solar recurrences currently support daily patterns only.")
        return _next_for_solar(solar_expression, tz, after_local, interval, location)

    hour = int(time_spec.get("hour", 0))
    minute = int(time_spec.get("minute", 0))
    second = int(time_spec.get("second", 0))

    rrule_kwargs: dict[str, Any] = {}
    if "byweekday" in rule:
        weekday_indices = [int(x) for x in rule["byweekday"]]
        rrule_kwargs["byweekday"] = [_WEEKDAY_INDEX_MAP[idx] for idx in weekday_indices]
    if "bymonthday" in rule:
        rrule_kwargs["bymonthday"] = [int(x) for x in rule["bymonthday"]]

    time_spec = {"hour": hour, "minute": minute, "second": second}
    return _next_for_rrule(
        tz,
        after_local,
        freq_value,
        interval,
        rrule_kwargs,
        time_spec,
    )

"""Solar event parsing and computation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from astral import sun
from astral.location import LocationInfo
from zoneinfo import ZoneInfo


class SolarParseError(ValueError):
    """Raised when a solar expression cannot be parsed."""


@dataclass(slots=True)
class SolarExpression:
    """A structured representation of a solar event expression."""

    event: str
    offset: timedelta


@dataclass(slots=True)
class Location:
    """Represents a geographic location."""

    latitude: float
    longitude: float
    name: str | None = None


@dataclass(slots=True)
class SolarComputationResult:
    """Holds the computed next datetime for a solar event."""

    when: datetime
    event: str
    offset: timedelta


_SOLAR_EVENTS = {"sunrise", "sunset", "dawn", "dusk", "midday"}
_OFFSET_UNITS = {"m": "minutes", "h": "hours"}
_FALLBACK_TIMES: dict[str, time] = {
    "sunrise": time(6, 0),
    "sunset": time(18, 0),
    "dawn": time(6, 0),
    "dusk": time(18, 0),
    "midday": time(12, 0),
}


def parse_solar_expression(expression: str) -> Optional[SolarExpression]:
    """Parse a solar event expression such as ``"sunrise+15m"``."""

    expression = expression.strip().lower()
    for event in _SOLAR_EVENTS:
        if not expression.startswith(event):
            continue
        remainder = expression[len(event) :].strip()
        offset = timedelta(0)
        if remainder:
            offset = _parse_offset(remainder)
        return SolarExpression(event=event, offset=offset)
    return None


def compute_next_solar_time(
    solar: SolarExpression,
    tz_name: str,
    now: datetime,
    *,
    location: Location | None = None,
) -> SolarComputationResult:
    """Compute the next occurrence of a solar event."""

    tz = ZoneInfo(tz_name)
    reference = now.astimezone(tz)

    target_date = reference.date()

    for attempt in range(2):  # today, then tomorrow if needed
        candidate = _compute_solar_for_date(solar.event, solar.offset, target_date, tz, location)
        if candidate > reference:
            return SolarComputationResult(when=candidate, event=solar.event, offset=solar.offset)
        target_date = target_date + timedelta(days=1)

    # Fallback: return the last computed candidate (from the loop)
    candidate = _compute_solar_for_date(solar.event, solar.offset, target_date, tz, location)
    return SolarComputationResult(when=candidate, event=solar.event, offset=solar.offset)


def _compute_solar_for_date(
    event: str,
    offset: timedelta,
    target_date: date,
    tz: ZoneInfo,
    location: Location | None,
) -> datetime:
    if location is not None:
        loc = LocationInfo(
            name=location.name or "Custom",
            region="",
            timezone=tz.key,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        observer = loc.observer
        sun_times = sun.sun(observer, date=target_date, tzinfo=tz)
        key = "noon" if event == "midday" else event
        base = sun_times[key]
    else:
        fallback_time = _FALLBACK_TIMES[event]
        base = datetime.combine(target_date, fallback_time, tz)
    return base + offset


def _parse_offset(text: str) -> timedelta:
    sign = 1
    if text[0] in {"+", "-"}:
        sign = 1 if text[0] == "+" else -1
        text = text[1:]
    else:
        raise SolarParseError("Solar offset must start with '+' or '-'.")

    total = timedelta(0)
    number = ""
    unit = ""
    for char in text:
        if char.isdigit():
            if unit:
                total += _build_delta(number, unit)
                number = char
                unit = ""
            else:
                number += char
        else:
            unit += char
    if number and unit:
        total += _build_delta(number, unit)
    elif number or unit:
        raise SolarParseError("Malformed solar offset expression.")

    return total * sign


def _build_delta(number: str, unit: str) -> timedelta:
    if unit not in _OFFSET_UNITS:
        raise SolarParseError("Solar offset units must be 'm' or 'h'.")
    value = int(number)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    raise SolarParseError("Unsupported solar offset unit.")

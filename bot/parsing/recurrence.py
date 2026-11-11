"""Recurrence parsing helpers.

Recurring expressions are stored as a small JSON rule so that the next
occurrence can be recomputed after every delivery (and after a restart).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Optional
import re
from zoneinfo import ZoneInfo

from dateutil import rrule

from . import lexicon
from .solar import (
    Location,
    SolarExpression,
    SolarParseError,
    compute_next_solar_time,
    parse_solar_expression,
)


class RecurrenceParseError(ValueError):
    """Raised when a recurrence string cannot be parsed."""


@dataclass(slots=True)
class RecurrenceParseResult:
    """Structured recurrence definition."""

    next_occurrence: datetime
    rule: dict[str, Any]
    description: str


@dataclass(slots=True)
class RecurrenceContext:
    timezone: str
    now: datetime
    location: Location | None = None


_SUBDAILY_SECONDS: dict[str, int] = {
    "secondly": 1,
    "minutely": 60,
    "hourly": 3600,
}

_FREQ_NAMES = {"secondly", "minutely", "hourly", "daily", "weekly", "monthly", "yearly"}

_FREQ_WORDS: dict[str, str] = {
    "second": "secondly",
    "seconds": "secondly",
    "sec": "secondly",
    "secs": "secondly",
    "secondly": "secondly",
    "minute": "minutely",
    "minutes": "minutely",
    "min": "minutely",
    "mins": "minutely",
    "minutely": "minutely",
    "hour": "hourly",
    "hours": "hourly",
    "hr": "hourly",
    "hrs": "hourly",
    "hourly": "hourly",
    "day": "daily",
    "days": "daily",
    "daily": "daily",
    "nightly": "daily",
    "week": "weekly",
    "weeks": "weekly",
    "weekly": "weekly",
    "month": "monthly",
    "months": "monthly",
    "monthly": "monthly",
    "year": "yearly",
    "years": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
    "annually": "yearly",
}

_WEEKDAY_GROUPS: dict[str, list[int]] = {
    "weekday": [0, 1, 2, 3, 4],
    "weekdays": [0, 1, 2, 3, 4],
    "workday": [0, 1, 2, 3, 4],
    "workdays": [0, 1, 2, 3, 4],
    "businessday": [0, 1, 2, 3, 4],
    "businessdays": [0, 1, 2, 3, 4],
    "weekend": [5, 6],
    "weekends": [5, 6],
}

_NTH_WORDS: dict[str, int] = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
    "last": -1,
}

_NTH_WEEKDAY_RE = re.compile(
    rf"^(?P<nth>{'|'.join(sorted(_NTH_WORDS, key=len, reverse=True))})\s+"
    rf"(?P<weekday>{lexicon.WEEKDAY_ALTERNATION})\b(?P<rest>.*)$"
)

_ORDINAL_RE = re.compile(r"(?<![\d.])(\d{1,2})(?:st|nd|rd|th)?(?![\d])")

_PREFIX_RE = re.compile(r"^(?:every|each)\b\s*(?P<rest>.*)$")
_DIRECT_FREQ_RE = re.compile(
    r"^(?P<word>daily|nightly|hourly|weekly|monthly|yearly|annually)\b\s*(?P<rest>.*)$"
)
_INTERVAL_RE = re.compile(
    r"^(?P<modifier>other|second|single|a couple of|a couple|a few|an?|\d+|one|two|three|"
    r"four|five|six|seven|eight|nine|ten)\s+(?P<rest>.+)$"
)


def parse_recurrence(expression: str, context: RecurrenceContext) -> RecurrenceParseResult:
    """Parse a recurrence expression such as ``every other monday at 09:00``."""

    text = lexicon.normalize(expression)
    tz = ZoneInfo(context.timezone)
    now_local = context.now.astimezone(tz)

    interval, rest = _strip_recurrence_prefix(text)
    if not rest:
        raise RecurrenceParseError("Recurrence pattern is incomplete.")

    pattern, clock, default_time, solar = _split_time(rest)
    freq, rrule_kwargs, json_kwargs = _parse_pattern(pattern)

    chosen_time = clock or default_time or time(9, 0)
    rule: dict[str, Any] = {
        "type": "rrule",
        "interval": interval,
        "freq": freq,
        "time": {
            "hour": chosen_time.hour,
            "minute": chosen_time.minute,
            "second": chosen_time.second,
        },
    }

    if solar is not None:
        if freq != "daily":
            raise RecurrenceParseError(
                "Solar recurrences currently support daily patterns only."
            )
        rule["time"] = {
            "solar_event": solar.event,
            "offset_seconds": int(solar.offset.total_seconds()),
        }
        next_occurrence = _next_for_solar(solar, tz, now_local, interval, context.location)
    elif freq in _SUBDAILY_SECONDS:
        next_occurrence = now_local + timedelta(seconds=_SUBDAILY_SECONDS[freq] * interval)
        rule["anchor"] = next_occurrence.isoformat()
    else:
        next_occurrence = _next_for_rrule(
            tz, now_local, freq, interval, rrule_kwargs, rule["time"]
        )

    if json_kwargs:
        rule.update(json_kwargs)

    return RecurrenceParseResult(
        next_occurrence=next_occurrence.astimezone(tz),
        rule=rule,
        description=expression.strip(),
    )


def _strip_recurrence_prefix(text: str) -> tuple[int, str]:
    """Return ``(interval, remainder)`` for a recurrence expression."""

    match = _PREFIX_RE.match(text)
    if not match:
        direct = _DIRECT_FREQ_RE.match(text)
        if direct:
            return 1, f"{direct.group('word')} {direct.group('rest')}".strip()
        raise RecurrenceParseError(
            "Recurrence must start with 'every', 'each' or a frequency such as 'daily'."
        )

    rest = match.group("rest").strip()
    interval = 1

    interval_match = _INTERVAL_RE.match(rest)
    if interval_match:
        modifier = interval_match.group("modifier")
        remainder = interval_match.group("rest").strip()
        if modifier == "second":
            # "every second" is a frequency, "every second day" is an interval.
            if not re.match(
                r"^(?:day|week|month|year|hour|minute|second)s?\b", remainder
            ):
                interval_match = None
        if interval_match is not None:
            if modifier == "other":
                interval = 2
            else:
                number = lexicon.word_number(modifier)
                if number is None:
                    raise RecurrenceParseError("Invalid interval in recurrence expression.")
                interval = int(number)
            if interval < 1:
                raise RecurrenceParseError("Interval must be positive.")
            rest = remainder

    return interval, rest


def _split_time(
    rest: str,
) -> tuple[str, Optional[time], Optional[time], Optional[SolarExpression]]:
    """Split a recurrence body into its pattern and time component."""

    text = rest.strip()
    pattern = text
    clock: Optional[time] = None
    solar: Optional[SolarExpression] = None
    default_time: Optional[time] = None

    at_match = re.search(r"\sat\s+(?P<time>.+)$", text)
    if at_match:
        candidate_text = at_match.group("time").strip()
        candidate_solar = _parse_solar(candidate_text)
        if candidate_solar is not None:
            solar = candidate_solar
            pattern = text[: at_match.start()].strip()
        else:
            candidate_clock = lexicon.parse_clock(candidate_text)
            if candidate_clock is not None:
                clock = candidate_clock
                pattern = text[: at_match.start()].strip()

    if solar is None and clock is None:
        found_clock = lexicon.find_clock(text)
        if found_clock is not None:
            clock = found_clock.value
            pattern = (text[: found_clock.start] + " " + text[found_clock.end :]).strip()
        else:
            found_solar = _SOLAR_ONLY_RE.search(text)
            if found_solar is not None:
                solar = _parse_solar(found_solar.group(0))
                if solar is not None:
                    pattern = (
                        text[: found_solar.start()] + " " + text[found_solar.end() :]
                    ).strip()

    part_match = lexicon.find_part_of_day(pattern)
    if part_match is not None:
        default_time = part_match.value
        pattern = (pattern[: part_match.start] + " " + pattern[part_match.end :]).strip()

    pattern = re.sub(r"\s+", " ", pattern).strip()
    return pattern, clock, default_time, solar


_SOLAR_ONLY_RE = re.compile(
    r"\b(?:sunrise|sunset|dawn|dusk)\b"
    r"(?:\s*[+-]\s*\d+\s*(?:m|min|mins|minutes|h|hr|hrs|hour|hours))?"
)


def _parse_solar(text: str) -> Optional[SolarExpression]:
    candidate = text.strip().replace(" ", "")
    try:
        return parse_solar_expression(candidate)
    except SolarParseError:
        return None


def _parse_pattern(pattern: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Translate a recurrence pattern into an rrule definition."""

    text = pattern.strip()
    text = re.sub(r"^(?:on|in|for|of|at|every|each)\s+", "", text)
    text = re.sub(r"^the\s+", "", text)

    freq: Optional[str] = None
    rrule_kwargs: dict[str, Any] = {}
    json_kwargs: dict[str, Any] = {}

    word_match = re.match(r"^(?P<word>[a-z]+)\b\s*(?P<rest>.*)$", text)
    if word_match and word_match.group("word") in _FREQ_WORDS:
        freq = _FREQ_WORDS[word_match.group("word")]
        text = word_match.group("rest").strip()
    elif word_match and word_match.group("word") in _WEEKDAY_GROUPS:
        return _weekday_group_rule(word_match.group("word"), word_match.group("rest"))

    text = re.sub(r"^(?:on|in|for|of|at)\s+", "", text).strip()

    nth_match = _NTH_WEEKDAY_RE.match(text)
    if nth_match and nth_match.group("weekday") in lexicon.WEEKDAY_INDEX:
        if freq not in {None, "monthly"}:
            raise RecurrenceParseError(
                "Nth weekday patterns are only supported for monthly recurrences."
            )
        weekday_index = lexicon.WEEKDAY_INDEX[nth_match.group("weekday")]
        nth = _NTH_WORDS[nth_match.group("nth")]
        return (
            "monthly",
            {"byweekday": [rrule.weekday(weekday_index, nth)]},
            {"bynweekday": [[weekday_index, nth]]},
        )

    weekdays = lexicon.find_weekdays(text)
    if weekdays:
        if freq is None:
            freq = "weekly"
        rrule_kwargs["byweekday"] = [rrule.weekday(index) for index in weekdays]
        json_kwargs["byweekday"] = weekdays
        return freq, rrule_kwargs, json_kwargs

    months = lexicon.find_months(text)
    ordinals = _extract_ordinals(text)
    if months:
        if freq is None:
            freq = "yearly"
        if freq == "yearly":
            rrule_kwargs["bymonth"] = months
            json_kwargs["bymonth"] = months
            if ordinals:
                rrule_kwargs["bymonthday"] = ordinals
                json_kwargs["bymonthday"] = ordinals
            return freq, rrule_kwargs, json_kwargs
    if ordinals:
        if freq is None:
            freq = "monthly"
        if freq in {"monthly", "yearly"}:
            rrule_kwargs["bymonthday"] = ordinals
            json_kwargs["bymonthday"] = ordinals
            return freq, rrule_kwargs, json_kwargs

    if text and freq is None:
        raise RecurrenceParseError("Unsupported recurrence pattern.")
    if text and freq is not None:
        raise RecurrenceParseError("Unsupported recurrence pattern.")

    return freq or "daily", rrule_kwargs, json_kwargs


def _weekday_group_rule(word: str, rest: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if rest.strip():
        raise RecurrenceParseError("Unsupported recurrence pattern.")
    weekdays = _WEEKDAY_GROUPS[word]
    return (
        "weekly",
        {"byweekday": [rrule.weekday(index) for index in weekdays]},
        {"byweekday": weekdays},
    )


def _extract_ordinals(pattern: str) -> list[int]:
    ordinals: list[int] = []
    for match in _ORDINAL_RE.finditer(pattern):
        value = int(match.group(1))
        if 1 <= value <= 31 and value not in ordinals:
            ordinals.append(value)
    return ordinals


def _next_for_rrule(
    tz: ZoneInfo,
    now_local: datetime,
    freq: str,
    interval: int,
    kwargs: dict[str, Any],
    time_component: dict[str, Any],
) -> datetime:
    hour = int(time_component.get("hour", 0))
    minute = int(time_component.get("minute", 0))
    second = int(time_component.get("second", 0))
    dtstart = now_local.replace(hour=hour, minute=minute, second=second, microsecond=0)
    rule = rrule.rrule(
        _RRULE_FREQ[freq], interval=interval, dtstart=dtstart, **kwargs
    )
    # ``after`` defaults to an exclusive search; ``inc``/``include`` spellings
    # differ between dateutil releases, so rely on the default.
    next_dt = rule.after(now_local)
    return next_dt.astimezone(tz)


_RRULE_FREQ = {
    "secondly": rrule.SECONDLY,
    "minutely": rrule.MINUTELY,
    "hourly": rrule.HOURLY,
    "daily": rrule.DAILY,
    "weekly": rrule.WEEKLY,
    "monthly": rrule.MONTHLY,
    "yearly": rrule.YEARLY,
}


def _next_for_solar(
    solar: SolarExpression,
    tz: ZoneInfo,
    now_local: datetime,
    interval: int,
    location: Location | None,
) -> datetime:
    result = compute_next_solar_time(solar, tz.key, now_local, location=location)
    if interval == 1:
        return result.when
    candidate = result.when + timedelta(days=interval - 1)
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

    freq = rule.get("freq")
    if freq not in _FREQ_NAMES:
        raise RecurrenceParseError("Recurrence frequency missing or invalid.")

    interval = int(rule.get("interval", 1))
    if interval < 1:
        raise RecurrenceParseError("Recurrence interval must be positive.")

    time_spec = rule.get("time")
    if not isinstance(time_spec, dict):
        raise RecurrenceParseError("Recurrence time specification missing.")

    tz = ZoneInfo(timezone)
    after_local = after.astimezone(tz)

    if freq in _SUBDAILY_SECONDS:
        step = _SUBDAILY_SECONDS[freq] * interval
        anchor_raw = rule.get("anchor")
        anchor = after_local
        if isinstance(anchor_raw, str):
            try:
                parsed_anchor = datetime.fromisoformat(anchor_raw)
            except ValueError:
                parsed_anchor = after_local
            if parsed_anchor.tzinfo is None:
                parsed_anchor = parsed_anchor.replace(tzinfo=tz)
            anchor = parsed_anchor.astimezone(tz)
        elapsed = (after_local - anchor).total_seconds()
        steps = int(elapsed // step) + 1 if elapsed >= 0 else 0
        return anchor + timedelta(seconds=step * steps)

    if "solar_event" in time_spec:
        solar_expression = SolarExpression(
            event=str(time_spec["solar_event"]),
            offset=timedelta(seconds=int(time_spec.get("offset_seconds", 0))),
        )
        if freq != "daily":
            raise RecurrenceParseError(
                "Solar recurrences currently support daily patterns only."
            )
        return _next_for_solar(solar_expression, tz, after_local, interval, location)

    rrule_kwargs: dict[str, Any] = {}
    if "bynweekday" in rule:
        rrule_kwargs["byweekday"] = [
            rrule.weekday(int(index), int(nth)) for index, nth in rule["bynweekday"]
        ]
    elif "byweekday" in rule:
        rrule_kwargs["byweekday"] = [
            rrule.weekday(int(index)) for index in rule["byweekday"]
        ]
    if "bymonthday" in rule:
        rrule_kwargs["bymonthday"] = [int(x) for x in rule["bymonthday"]]
    if "bymonth" in rule:
        rrule_kwargs["bymonth"] = [int(x) for x in rule["bymonth"]]

    return _next_for_rrule(tz, after_local, freq, interval, rrule_kwargs, time_spec)

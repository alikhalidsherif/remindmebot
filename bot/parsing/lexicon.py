"""Shared natural-language vocabulary and primitive parsers.

Both the absolute time parser and the recurrence parser build on these
helpers so that words such as ``"monday"``, ``"half past five"`` or
``"evening"`` mean exactly the same thing everywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from typing import Optional


WEEKDAY_INDEX: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "mo": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "tu": 1,
    "wednesday": 2,
    "weds": 2,
    "wed": 2,
    "we": 2,
    "thursday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "th": 3,
    "friday": 4,
    "fri": 4,
    "fr": 4,
    "saturday": 5,
    "sat": 5,
    "sa": 5,
    "sunday": 6,
    "sun": 6,
    "su": 6,
}

#: Plural spellings are accepted as well ("mondays", "fridays").
for _name, _index in list(WEEKDAY_INDEX.items()):
    WEEKDAY_INDEX.setdefault(f"{_name}s", _index)
del _name, _index

MONTH_INDEX: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

NUMBER_WORDS: dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "a": 1,
    "an": 1,
    "single": 1,
    "half": 0.5,
    "a couple": 2,
    "a couple of": 2,
    "couple": 2,
    "couple of": 2,
    "a few": 3,
    "few": 3,
    "a handful of": 5,
}

#: Default clock times for vague parts of the day.
PART_OF_DAY_TIMES: dict[str, time] = {
    "morning": time(9, 0),
    "afternoon": time(15, 0),
    "evening": time(18, 0),
    "night": time(21, 0),
}

NAMED_TIMES: dict[str, time] = {
    "noon": time(12, 0),
    "midday": time(12, 0),
    "lunchtime": time(12, 0),
    "midnight": time(0, 0),
}

_WEEKDAY_ALTERNATION = "|".join(sorted(WEEKDAY_INDEX, key=len, reverse=True))
WEEKDAY_ALTERNATION = _WEEKDAY_ALTERNATION
MONTH_ALTERNATION = "|".join(sorted(MONTH_INDEX, key=len, reverse=True))

_PART_OF_DAY_RE = re.compile(
    r"\b(?:(?:in|during)\s+(?:the\s+)?|this\s+|the\s+)?"
    r"(?P<word>morning|afternoon|evening|night)\b"
)

_CLOCK_AMPM_RE = re.compile(
    r"(?<![\d:])(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?::(?P<second>\d{2}))?"
    r"\s*(?P<ampm>am|pm)(?!\w)"
)
_CLOCK_DOT_RE = re.compile(
    r"(?<![\d.])(?P<hour>\d{1,2})\.(?P<minute>\d{2})\s*(?P<ampm>am|pm)(?!\w)"
)
_CLOCK_COLON_RE = re.compile(
    r"(?<![\d:])(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?(?!\d)"
)
_CLOCK_OCLOCK_RE = re.compile(
    r"(?<![\d:])(?P<hour>\d{1,2})\s*oclock(?:\s*(?P<ampm>am|pm))?(?!\w)"
)
_NAMED_TIME_RE = re.compile(r"\b(noon|midday|lunchtime|midnight)\b")

_CLOCK_SEARCH_PATTERNS = (
    _CLOCK_AMPM_RE,
    _CLOCK_DOT_RE,
    _CLOCK_COLON_RE,
    _CLOCK_OCLOCK_RE,
)

_PLAIN_CLOCK_RE = re.compile(
    r"^(?P<hour>\d{1,2})(?:[:.](?P<minute>\d{2}))?(?:[:.](?P<second>\d{2}))?$"
)
_WORD_CLOCK_RE = re.compile(
    r"^(?P<first>[a-z]+)\s+(?P<relation>past|after|to|till|before)\s+(?P<second>[a-z]+)$"
)


@dataclass(slots=True)
class ClockMatch:
    """A clock time found inside a longer expression."""

    value: time
    start: int
    end: int


@dataclass(slots=True)
class PartOfDayMatch:
    """A part-of-day word found inside a longer expression."""

    value: time
    word: str
    start: int
    end: int


def normalize(text: str) -> str:
    """Lowercase and canonicalise a user supplied expression."""

    value = text.strip().lower()
    value = (
        value.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u00a0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    # Keep dots that sit between digits (``5.30pm``), drop the rest (``p.m.``).
    value = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", value)
    value = re.sub(r"\b([ap])\s+m\b", r"\1m", value)
    value = value.replace(",", " ")
    value = re.sub(r"[;!?\"'`()\[\]{}<>|]+", " ", value)
    value = re.sub(r"(?<!\d):|:(?!\d)", " ", value)
    value = value.replace("o clock", "oclock")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def word_number(text: str) -> Optional[float]:
    """Convert ``"5"``, ``"five"`` or ``"twenty one"`` into a number."""

    value = text.strip().lower()
    if not value:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)
    if value in NUMBER_WORDS:
        return NUMBER_WORDS[value]
    tokens = value.split()
    if len(tokens) == 2:
        tens = {"twenty", "thirty", "forty", "fifty"}
        units = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
        if tokens[0] in tens and tokens[1] in units:
            return float(NUMBER_WORDS[tokens[0]] + NUMBER_WORDS[tokens[1]])
    if len(tokens) == 3 and tokens[0] in {"a", "one"} and tokens[1] == "hundred":
        return 100.0
    return None


def _make_time(hour: int, minute: int, second: int, ampm: str | None) -> Optional[time]:
    if ampm is not None:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12
        if ampm == "pm":
            hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return None
    return time(hour, minute, second)


def _split_ampm(value: str) -> tuple[str, str | None]:
    if value.endswith("am") or value.endswith("pm"):
        return value[:-2].strip(), value[-2:]
    return value, None


def _strip_leading_connectors(value: str) -> str:
    previous = None
    while previous != value:
        previous = value
        value = re.sub(
            r"^(?:at|by|around|about|near|from|on|in the|in|the)\s+", "", value
        ).strip()
    return value


def parse_clock(text: str) -> Optional[time]:
    """Parse a string that is expected to *be* a clock time."""

    value = _strip_leading_connectors(normalize(text))
    value = re.sub(r"\s+(?:sharp|exactly|please|or so)$", "", value).strip()
    if not value:
        return None
    if value in NAMED_TIMES:
        return NAMED_TIMES[value]
    if value in PART_OF_DAY_TIMES:
        return PART_OF_DAY_TIMES[value]

    numeric = _parse_numeric_clock(value)
    if numeric is not None:
        return numeric
    return _parse_word_clock(value)


def _parse_numeric_clock(value: str) -> Optional[time]:
    body, ampm = _split_ampm(value)
    body = re.sub(r"\s*oclock$", "", body).strip()
    if not body:
        return None
    match = _PLAIN_CLOCK_RE.fullmatch(body)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    second = int(match.group("second") or 0)
    return _make_time(hour, minute, second, ampm)


def _parse_word_clock(value: str) -> Optional[time]:
    body, ampm = _split_ampm(value)
    body = re.sub(r"\s*oclock$", "", body).strip()
    if not body:
        return None

    match = _WORD_CLOCK_RE.fullmatch(body)
    if match:
        base = word_number(match.group("second"))
        delta = {"half": 30.0, "quarter": 15.0}.get(match.group("first"))
        if delta is None:
            delta = word_number(match.group("first"))
        if base is None or delta is None or not 0 <= base <= 12:
            return None
        total = base * 60
        if match.group("relation") in {"to", "till", "before"}:
            total -= delta
        else:
            total += delta
        total %= 24 * 60
        return _make_time(int(total // 60), int(total % 60), 0, ampm)

    tokens = body.split()
    if not tokens:
        return None
    hour_value = word_number(tokens[0])
    if hour_value is None:
        return None
    minute_value: float = 0
    if len(tokens) > 1:
        minute_value = word_number(" ".join(tokens[1:]))  # type: ignore[assignment]
        if minute_value is None:
            return None
    if not 0 <= hour_value <= 23 or not 0 <= minute_value <= 59:
        return None
    return _make_time(int(hour_value), int(minute_value), 0, ampm)


def find_clock(text: str) -> Optional[ClockMatch]:
    """Find the earliest clock time inside ``text``."""

    best: Optional[ClockMatch] = None
    for pattern in _CLOCK_SEARCH_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groupdict()
            hour = int(groups.get("hour") or 0)
            minute = int(groups.get("minute") or 0)
            second = int(groups.get("second") or 0)
            value = _make_time(hour, minute, second, groups.get("ampm"))
            if value is None:
                continue
            if best is None or match.start() < best.start:
                best = ClockMatch(value=value, start=match.start(), end=match.end())
            break

    named = _NAMED_TIME_RE.search(text)
    if named is not None:
        value = NAMED_TIMES[named.group(1)]
        if best is None or named.start() < best.start:
            best = ClockMatch(value=value, start=named.start(), end=named.end())
    return best


def find_part_of_day(text: str) -> Optional[PartOfDayMatch]:
    match = _PART_OF_DAY_RE.search(text)
    if not match:
        return None
    word = match.group("word")
    return PartOfDayMatch(
        value=PART_OF_DAY_TIMES[word],
        word=word,
        start=match.start(),
        end=match.end(),
    )


def find_weekdays(text: str) -> list[int]:
    """Return unique weekday indices mentioned in ``text`` (in order)."""

    pattern = re.compile(rf"\b({_WEEKDAY_ALTERNATION})\b")
    found: list[int] = []
    for match in pattern.finditer(text):
        index = WEEKDAY_INDEX[match.group(1)]
        if index not in found:
            found.append(index)
    return found


def find_months(text: str) -> list[int]:
    pattern = re.compile(rf"\b({MONTH_ALTERNATION})\b")
    found: list[int] = []
    for match in pattern.finditer(text):
        index = MONTH_INDEX[match.group(1)]
        if index not in found:
            found.append(index)
    return found

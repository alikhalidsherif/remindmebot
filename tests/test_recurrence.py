from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from bot.parsing.recurrence import (
    RecurrenceContext,
    RecurrenceParseError,
    compute_next_occurrence_from_rule,
    parse_recurrence,
)

CONTEXT = RecurrenceContext(
    timezone="UTC",
    now=datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("UTC")),
)


def utc(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("UTC"))


RULE_CASES = [
    ("every day at 10:00", {"freq": "daily", "interval": 1}),
    ("every day", {"freq": "daily", "interval": 1}),
    ("every other tuesday 14:00", {"freq": "weekly", "interval": 2, "byweekday": [1]}),
    ("every 2 weeks on monday at 9am", {"freq": "weekly", "interval": 2, "byweekday": [0]}),
    ("every weekday 10:00", {"freq": "weekly", "byweekday": [0, 1, 2, 3, 4]}),
    ("every weekend at 10am", {"freq": "weekly", "byweekday": [5, 6]}),
    ("every monday and thursday at 9am", {"freq": "weekly", "byweekday": [0, 3]}),
    ("every 30 minutes", {"freq": "minutely", "interval": 30}),
    ("every hour", {"freq": "hourly", "interval": 1}),
    ("every 15 seconds", {"freq": "secondly", "interval": 15}),
    ("every month on the 1st and 15th at 9am", {"freq": "monthly", "bymonthday": [1, 15]}),
    ("every first monday of the month at 9am", {"freq": "monthly", "bynweekday": [[0, 1]]}),
    ("every last friday of the month at 18:00", {"freq": "monthly", "bynweekday": [[4, -1]]}),
    ("every year on december 25 at 9am", {"freq": "yearly", "bymonth": [12], "bymonthday": [25]}),
    ("every morning", {"freq": "daily", "time": {"hour": 9, "minute": 0, "second": 0}}),
    ("monthly on the 3rd at 9", {"freq": "monthly", "bymonthday": [3]}),
    ("yearly on july 4 at 10", {"freq": "yearly", "bymonth": [7], "bymonthday": [4]}),
    ("weekly on monday at 9am", {"freq": "weekly", "byweekday": [0]}),
    ("daily at 7:30", {"freq": "daily", "time": {"hour": 7, "minute": 30, "second": 0}}),
]


@pytest.mark.parametrize("expression,expected", RULE_CASES)
def test_recurrence_rules(expression, expected):
    result = parse_recurrence(expression, CONTEXT)

    for key, value in expected.items():
        assert result.rule.get(key) == value
    assert result.rule["type"] == "rrule"
    assert result.next_occurrence > CONTEXT.now
    assert result.next_occurrence.tzinfo is not None


NEXT_CASES = [
    ("every day at 10:00", utc(2026, 11, 11, 10, 0)),
    ("every night at 11pm", utc(2026, 11, 11, 23, 0)),
    ("every morning", utc(2026, 11, 12, 9, 0)),
    ("every weekday at 9am", utc(2026, 11, 12, 9, 0)),
    ("every weekend at 10am", utc(2026, 11, 14, 10, 0)),
    ("every monday and thursday at 9am", utc(2026, 11, 12, 9, 0)),
    ("every first monday of the month at 9am", utc(2026, 12, 7, 9, 0)),
    ("every last friday of the month at 18:00", utc(2026, 11, 27, 18, 0)),
    ("every month on the 1st and 15th at 9am", utc(2026, 11, 15, 9, 0)),
    ("every year on december 25 at 9am", utc(2026, 12, 25, 9, 0)),
    ("every 2 hours", utc(2026, 11, 11, 11, 0)),
    ("every 30 minutes", utc(2026, 11, 11, 9, 30)),
    ("every 15 seconds", utc(2026, 11, 11, 9, 0, 15)),
    ("daily at 7:30", utc(2026, 11, 12, 7, 30)),
    ("weekly on monday at 9am", utc(2026, 11, 16, 9, 0)),
]


@pytest.mark.parametrize("expression,expected", NEXT_CASES)
def test_recurrence_next_occurrence(expression, expected):
    result = parse_recurrence(expression, CONTEXT)

    assert result.next_occurrence == expected


def test_parse_monthly_recurrence():
    result = parse_recurrence("every month on the 1st 09:00", CONTEXT)

    assert result.rule["freq"] == "monthly"
    assert result.rule["bymonthday"] == [1]
    assert result.rule["time"] == {"hour": 9, "minute": 0, "second": 0}


def test_compute_next_occurrence_from_rule():
    result = parse_recurrence("every weekday 10:00", CONTEXT)

    next_occurrence = compute_next_occurrence_from_rule(
        result.rule,
        "UTC",
        after=CONTEXT.now,
    )

    assert next_occurrence.weekday() < 5
    assert next_occurrence.hour == 10


def test_compute_next_hourly_occurrence_from_rule():
    result = parse_recurrence("every 2 hours", CONTEXT)

    next_occurrence = compute_next_occurrence_from_rule(
        result.rule,
        "UTC",
        after=utc(2026, 11, 11, 11, 0) + timedelta(seconds=1),
    )

    assert next_occurrence == utc(2026, 11, 11, 13, 0)


def test_compute_next_nth_weekday_from_rule():
    result = parse_recurrence("every first monday of the month at 9am", CONTEXT)

    next_occurrence = compute_next_occurrence_from_rule(
        result.rule,
        "UTC",
        after=utc(2026, 12, 7, 9, 0) + timedelta(seconds=1),
    )

    assert next_occurrence == utc(2027, 1, 4, 9, 0)


def test_compute_next_yearly_from_rule():
    result = parse_recurrence("every year on december 25 at 9am", CONTEXT)

    next_occurrence = compute_next_occurrence_from_rule(
        result.rule,
        "UTC",
        after=utc(2026, 12, 25, 9, 0) + timedelta(seconds=1),
    )

    assert next_occurrence == utc(2027, 12, 25, 9, 0)


def test_solar_recurrence_requires_daily():
    result = parse_recurrence("every day at sunrise", CONTEXT)

    assert result.rule["freq"] == "daily"
    assert result.rule["time"]["solar_event"] == "sunrise"

    with pytest.raises(RecurrenceParseError):
        parse_recurrence("every week at sunrise", CONTEXT)

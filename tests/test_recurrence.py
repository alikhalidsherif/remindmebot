from __future__ import annotations

from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from bot.parsing.recurrence import (
    RecurrenceContext,
    RecurrenceParseError,
    compute_next_occurrence_from_rule,
    parse_recurrence,
)


def test_parse_monthly_recurrence():
    context = RecurrenceContext(
        timezone="UTC",
        now=datetime(2024, 1, 15, 10, 0, tzinfo=ZoneInfo("UTC")),
    )
    result = parse_recurrence("every month on the 1st 09:00", context)

    assert result.rule["freq"] == "monthly"
    assert result.rule["bymonthday"] == [1]
    assert result.rule["time"] == {"hour": 9, "minute": 0, "second": 0}


def test_parse_every_other_tuesday():
    context = RecurrenceContext(
        timezone="UTC",
        now=datetime(2024, 1, 2, 8, 0, tzinfo=ZoneInfo("UTC")),
    )
    result = parse_recurrence("every other tuesday 14:00", context)

    assert result.rule["interval"] == 2
    assert result.rule["byweekday"] == [1]
    assert result.rule["time"]["hour"] == 14


def test_compute_next_occurrence_from_rule():
    context = RecurrenceContext(
        timezone="UTC",
        now=datetime(2024, 1, 1, 8, 0, tzinfo=ZoneInfo("UTC")),
    )
    result = parse_recurrence("every weekday 10:00", context)

    after = context.now
    next_occurrence = compute_next_occurrence_from_rule(
        result.rule,
        "UTC",
        after=after,
    )

    assert next_occurrence.weekday() < 5
    assert next_occurrence.hour == 10


def test_solar_recurrence_requires_daily():
    context = RecurrenceContext(
        timezone="UTC",
        now=datetime(2024, 1, 1, 5, 0, tzinfo=ZoneInfo("UTC")),
    )
    result = parse_recurrence("every day at sunrise", context)

    assert result.rule["freq"] == "daily"
    assert result.rule["time"]["solar_event"] == "sunrise"

    with pytest.raises(RecurrenceParseError):
        parse_recurrence("every week at sunrise", context)

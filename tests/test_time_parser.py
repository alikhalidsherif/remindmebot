from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from bot.parsing.time_parser import TimeParseError, parse_time_expression

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("UTC"))


def utc(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("UTC"))


ABSOLUTE_CASES = [
    # Relative offsets
    ("in 30 minutes", utc(2026, 11, 11, 9, 30)),
    ("in 2 hours", utc(2026, 11, 11, 11, 0)),
    ("in 90 minutes", utc(2026, 11, 11, 10, 30)),
    ("in 1 hour 30 minutes", utc(2026, 11, 11, 10, 30)),
    ("in half an hour", utc(2026, 11, 11, 9, 30)),
    ("in an hour and a half", utc(2026, 11, 11, 10, 30)),
    ("in 3 days", utc(2026, 11, 14, 9, 0)),
    ("in 2 weeks", utc(2026, 11, 25, 9, 0)),
    ("in 1 month", utc(2026, 12, 11, 9, 0)),
    ("in a year", utc(2027, 11, 11, 9, 0)),
    ("in a couple of days", utc(2026, 11, 13, 9, 0)),
    ("in a few minutes", utc(2026, 11, 11, 9, 3)),
    ("30 minutes from now", utc(2026, 11, 11, 9, 30)),
    ("in 2 days at 5pm", utc(2026, 11, 13, 17, 0)),
    # Day keywords
    ("tomorrow", utc(2026, 11, 12, 9, 0)),
    ("tomorrow at 5pm", utc(2026, 11, 12, 17, 0)),
    ("tomorrow 17:30", utc(2026, 11, 12, 17, 30)),
    ("tomorrow morning", utc(2026, 11, 12, 9, 0)),
    ("tomorrow evening", utc(2026, 11, 12, 18, 0)),
    ("tomorrow night at 11pm", utc(2026, 11, 12, 23, 0)),
    ("tonight", utc(2026, 11, 11, 21, 0)),
    ("tonight at 10pm", utc(2026, 11, 11, 22, 0)),
    ("today at 18:00", utc(2026, 11, 11, 18, 0)),
    ("the day after tomorrow at noon", utc(2026, 11, 13, 12, 0)),
    # Weekdays
    ("next monday 9am", utc(2026, 11, 16, 9, 0)),
    ("next monday at 9:30am", utc(2026, 11, 16, 9, 30)),
    ("monday at 9am", utc(2026, 11, 16, 9, 0)),
    ("this friday 5pm", utc(2026, 11, 13, 17, 0)),
    ("coming thursday at 8", utc(2026, 11, 12, 8, 0)),
    ("wednesday at 10am", utc(2026, 11, 11, 10, 0)),
    ("wednesday at 8am", utc(2026, 11, 18, 8, 0)),
    # Coarse anchors
    ("next week", utc(2026, 11, 18, 9, 0)),
    ("next month", utc(2026, 12, 11, 9, 0)),
    ("next year", utc(2027, 11, 11, 9, 0)),
    ("end of day", utc(2026, 11, 11, 23, 59)),
    ("end of week", utc(2026, 11, 15, 23, 59)),
    ("end of month", utc(2026, 11, 30, 23, 59)),
    # Explicit dates
    ("2026-12-01 18:30", utc(2026, 12, 1, 18, 30)),
    ("2026-12-01", utc(2026, 12, 1, 9, 0)),
    ("2026-12-01t18:30:00z", utc(2026, 12, 1, 18, 30)),
    ("december 25 at 9am", utc(2026, 12, 25, 9, 0)),
    ("25 december 2026 at 9am", utc(2026, 12, 25, 9, 0)),
    ("the 3rd of december at 5pm", utc(2026, 12, 3, 17, 0)),
    ("12/25/2026 at 9am", utc(2026, 12, 25, 9, 0)),
    ("25/12/2026 09:00", utc(2026, 12, 25, 9, 0)),
    ("the 5th", utc(2026, 12, 5, 9, 0)),
    ("december", utc(2026, 12, 1, 9, 0)),
    # Clock times
    ("5pm", utc(2026, 11, 11, 17, 0)),
    ("5:30pm", utc(2026, 11, 11, 17, 30)),
    ("17:45", utc(2026, 11, 11, 17, 45)),
    ("9am", utc(2026, 11, 12, 9, 0)),
    ("at 8pm", utc(2026, 11, 11, 20, 0)),
    ("5 o'clock pm", utc(2026, 11, 11, 17, 0)),
    ("five pm", utc(2026, 11, 11, 17, 0)),
    ("half past five pm", utc(2026, 11, 11, 17, 30)),
    ("quarter to six pm", utc(2026, 11, 11, 17, 45)),
    ("five thirty pm", utc(2026, 11, 11, 17, 30)),
    ("noon", utc(2026, 11, 11, 12, 0)),
    ("midnight", utc(2026, 11, 12, 0, 0)),
    # Solar events
    ("sunrise", utc(2026, 11, 12, 6, 0)),
    ("sunset+15m", utc(2026, 11, 11, 18, 15)),
    ("tomorrow at sunrise", utc(2026, 11, 12, 6, 0)),
]


@pytest.mark.parametrize("expression,expected", ABSOLUTE_CASES)
def test_absolute_and_relative_expressions(expression, expected):
    parsed = parse_time_expression(expression, timezone="UTC", now=NOW)

    assert not parsed.is_recurring
    assert parsed.local_time == expected
    assert parsed.timezone == "UTC"


def test_parse_relative_time_in_future():
    parsed = parse_time_expression("in 2 hours", timezone="UTC", now=NOW)

    delta = parsed.next_run_at - NOW
    assert timedelta(hours=2) - timedelta(minutes=1) < delta < timedelta(hours=2, minutes=1)


def test_parse_weekday_recurrence():
    tz_name = "Europe/Berlin"
    now = datetime(2024, 1, 1, 8, 0, tzinfo=ZoneInfo(tz_name))
    parsed = parse_time_expression("every weekday 10:00", timezone=tz_name, now=now)

    assert parsed.is_recurring
    assert parsed.recurrence["freq"] == "weekly"
    assert parsed.recurrence["byweekday"] == [0, 1, 2, 3, 4]
    assert parsed.local_time.hour == 10 and parsed.local_time.minute == 0


def test_parse_solar_fallback_time():
    tz_name = "UTC"
    now = datetime(2024, 1, 1, 5, 0, tzinfo=ZoneInfo(tz_name))
    parsed = parse_time_expression("sunrise", timezone=tz_name, now=now)

    assert parsed.solar_event == "sunrise"
    assert parsed.local_time.hour == 6 and parsed.local_time.minute == 0


@pytest.mark.parametrize(
    "expression",
    ["", "   ", "last year", "the day before yesterday", "not a time at all"],
)
def test_invalid_expressions_raise(expression):
    with pytest.raises(TimeParseError):
        parse_time_expression(expression, timezone="UTC", now=NOW)

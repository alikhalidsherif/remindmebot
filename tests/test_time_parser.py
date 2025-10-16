from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from bot.parsing.time_parser import TimeParseError, parse_time_expression


def test_parse_relative_time_in_future():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_time_expression("in 2 hours", timezone="UTC", now=now)

    assert not parsed.is_recurring
    delta = parsed.next_run_at - now.astimezone(ZoneInfo("UTC"))
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


def test_parse_invalid_expression():
    with pytest.raises(TimeParseError):
        parse_time_expression("last year", timezone="UTC")

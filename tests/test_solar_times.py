from __future__ import annotations

from datetime import datetime

from zoneinfo import ZoneInfo

from bot.parsing.solar import Location, compute_next_solar_time, parse_solar_expression


def test_parse_solar_expression_with_offset():
    expr = parse_solar_expression("sunrise+15m")
    assert expr is not None
    assert expr.event == "sunrise"
    assert expr.offset.total_seconds() == 900


def test_compute_next_solar_time_with_fallback():
    solar = parse_solar_expression("sunset")
    now = datetime(2024, 1, 1, 15, 0, tzinfo=ZoneInfo("UTC"))
    result = compute_next_solar_time(solar, "UTC", now)

    assert result.when > now
    assert result.when.hour == 18


def test_compute_next_solar_time_with_location():
    solar = parse_solar_expression("sunrise")
    location = Location(latitude=52.52, longitude=13.405, name="Berlin")
    now = datetime(2024, 6, 1, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    result = compute_next_solar_time(solar, "Europe/Berlin", now, location=location)

    assert result.when.tzinfo == ZoneInfo("Europe/Berlin")
    assert result.when > now

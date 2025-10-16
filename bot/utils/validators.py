"""Validation helpers."""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo

_LAT_LON_PATTERN = re.compile(
    r"^(?P<lat>-?\d{1,2}(?:\.\d+)?),(?P<lon>-?\d{1,3}(?:\.\d+)?)$"
)


def normalize_timezone(tz_name: str) -> str:
    """Validate and normalise a timezone string."""

    tz_name = tz_name.strip()
    # ``ZoneInfo`` raises ``ZoneInfoNotFoundError`` if invalid.
    ZoneInfo(tz_name)
    return tz_name


def parse_lat_lon(value: str) -> tuple[float, float]:
    """Parse a latitude/longitude string."""

    match = _LAT_LON_PATTERN.match(value.strip())
    if not match:
        raise ValueError("Invalid latitude/longitude format. Expected '<lat>,<lon>'.")
    lat = float(match.group("lat"))
    lon = float(match.group("lon"))
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("Latitude must be between -90 and 90; longitude between -180 and 180.")
    return lat, lon

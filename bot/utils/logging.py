"""Logging helpers."""
from __future__ import annotations

import logging

from ..config import Config


def setup_logging(config: Config) -> None:
    """Configure the root logger using config settings."""

    level_name = config.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

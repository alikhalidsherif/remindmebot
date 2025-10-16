"""Shared helpers for command handlers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telegram.ext import ContextTypes

from ..config import Config
from ..db import Database
from ..scheduler import ReminderScheduler


@dataclass(slots=True)
class CommandContext:
    config: Config
    database: Database
    scheduler: ReminderScheduler


def get_command_context(context: ContextTypes.DEFAULT_TYPE) -> CommandContext:
    bot_data = context.application.bot_data
    config: Config = bot_data["config"]
    database: Database = bot_data["database"]
    scheduler: ReminderScheduler = bot_data["scheduler"]
    return CommandContext(config=config, database=database, scheduler=scheduler)

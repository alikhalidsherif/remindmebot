"""Command handler registration."""
from __future__ import annotations

from telegram.ext import Application, CommandHandler

from .cancel import cancel
from .cancelreminder import cancel_reminder_command
from .help import help_command
from .list import list_reminders
from .location import location_command
from .remind import remind
from .start import start
from .timezone import timezone_command


def register(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("remind", remind))
    application.add_handler(CommandHandler("list", list_reminders))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("cancelreminder", cancel_reminder_command))
    application.add_handler(CommandHandler("timezone", timezone_command))
    application.add_handler(CommandHandler("location", location_command))

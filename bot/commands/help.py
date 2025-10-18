"""Implementation of the /help command."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    "Available commands:\n"
    "• /remind [@username|me] <message> at <time expression> [dm]\n"
    "• /list – list upcoming reminders\n"
    "• /cancel <id> – cancel a reminder by id\n"
    "• /cancelreminder – reply to a reminder to cancel it\n"
    "• /timezone [set <tz>|show] – view or change the timezone\n"
    "• /location [set <place>|show|clear] – manage location for solar events\n"
    "\nTime expressions can be absolute (2025-01-15 14:00), relative (in 2h), recurring (every weekday 10:00) or solar (sunrise+15m)."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(HELP_TEXT)

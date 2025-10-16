"""Implementation of the /timezone command."""
from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..services.settings import get_timezone, set_timezone
from ..services.users import ensure_user_and_chat
from .common import get_command_context


async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)
    args = (update.message.text or "").split()

    async with command_context.database.session_factory() as session:
        async with session.begin():
            user, chat = await ensure_user_and_chat(
                session,
                telegram_user=update.effective_user,
                telegram_chat=update.effective_chat,
            )

        if len(args) == 1 or (len(args) == 2 and args[1].lower() == "show"):
            timezone_resolution = await get_timezone(
                session,
                user=user,
                chat=chat,
                default_timezone=command_context.config.default_timezone,
            )
            scope = "group" if chat.type != ChatType.PRIVATE else "your"
            await update.message.reply_text(
                f"Current timezone for {scope} reminders: {timezone_resolution.timezone}"
            )
            return

        if args[1].lower() != "set" or len(args) < 3:
            await update.message.reply_text("Usage: /timezone set <Area/City> or /timezone show")
            return

        tz_value = args[2]
        try:
            ZoneInfo(tz_value)
        except ZoneInfoNotFoundError:
            await update.message.reply_text("Unknown timezone. Use a valid IANA timezone, e.g. Europe/Berlin.")
            return

        async with session.begin():
            result = await set_timezone(
                session,
                source_chat=chat if chat.type != ChatType.PRIVATE else None,
                source_user=user if chat.type == ChatType.PRIVATE else None,
                timezone=tz_value,
            )

        scope = "Group" if chat.type != ChatType.PRIVATE else "Your"
        await update.message.reply_text(f"{scope} timezone updated to {result.timezone}.")

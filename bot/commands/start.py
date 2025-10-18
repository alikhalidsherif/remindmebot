"""Implementation of the /start command."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..services.users import ensure_user_and_chat
from .common import get_command_context


WELCOME_MESSAGE = (
    "Hello! I'm your reminder assistant.\n"
    "Use /remind to schedule reminders, /list to view them, and /help for detailed instructions."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None or update.effective_chat is None:
        return

    command_context = get_command_context(context)

    async with command_context.database.session_factory() as session:
        user, chat = await ensure_user_and_chat(
            session,
            telegram_user=update.effective_user,
            telegram_chat=update.effective_chat,
        )
        if chat.type == ChatType.PRIVATE:
            user.is_dm_enabled = True
        await session.commit()

    await update.message.reply_text(WELCOME_MESSAGE)

"""Implementation of the /cancel command."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..db import ReminderStatus
from ..services.reminders import cancel_reminder, get_reminder
from ..services.users import ensure_user_and_chat
from .common import get_command_context


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)
    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /cancel <reminder id>")
        return

    try:
        reminder_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("Reminder id must be a number.")
        return

    async with command_context.database.session_factory() as session:
        async with session.begin():
            user, chat = await ensure_user_and_chat(
                session,
                telegram_user=update.effective_user,
                telegram_chat=update.effective_chat,
            )

            reminder = await get_reminder(session, reminder_id)
            if reminder is None or reminder.chat_id != chat.id:
                await update.message.reply_text("Reminder not found in this chat.")
                return

            if reminder.status != ReminderStatus.ACTIVE:
                await update.message.reply_text("Reminder is no longer active.")
                return

            await cancel_reminder(session, reminder)

        command_context.scheduler.cancel(reminder_id)

    await update.message.reply_text(f"Reminder #{reminder_id} cancelled.")

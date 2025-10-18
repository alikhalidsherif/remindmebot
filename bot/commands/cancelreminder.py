"""Implementation of the /cancelreminder command."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..db import ReminderStatus
from ..services.reminders import cancel_reminder, find_reminder_by_message
from ..services.users import ensure_user_and_chat
from .common import get_command_context


async def cancel_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    if update.message.reply_to_message is None:
        await update.message.reply_text("Reply to a reminder message with /cancelreminder.")
        return

    command_context = get_command_context(context)

    reply = update.message.reply_to_message
    async with command_context.database.session_factory() as session:
        async with session.begin():
            user, chat = await ensure_user_and_chat(
                session,
                telegram_user=update.effective_user,
                telegram_chat=update.effective_chat,
            )

            reminder = await find_reminder_by_message(
                session,
                telegram_chat_id=reply.chat_id,
                telegram_message_id=reply.message_id,
            )
            if reminder is None:
                await update.message.reply_text("I could not find a reminder linked to that message.")
                return

            if reminder.chat_id != chat.id:
                await update.message.reply_text("That reminder belongs to a different chat.")
                return

            if reminder.status != ReminderStatus.ACTIVE:
                await update.message.reply_text("That reminder is no longer active.")
                return

            await cancel_reminder(session, reminder)

        command_context.scheduler.cancel(reminder.id)

    await update.message.reply_text(f"Reminder #{reminder.id} cancelled.")

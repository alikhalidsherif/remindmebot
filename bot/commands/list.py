"""Implementation of the /list command."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..services.reminders import list_active_reminders
from ..services.users import ensure_user_and_chat
from ..utils.formatting import format_datetime
from .common import get_command_context


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)

    async with command_context.database.session_factory() as session:
        user, chat = await ensure_user_and_chat(
            session,
            telegram_user=update.effective_user,
            telegram_chat=update.effective_chat,
        )
        reminders = await list_active_reminders(session, chat=chat)

    if not reminders:
        await update.message.reply_text("No upcoming reminders.")
        return

    lines: list[str] = []
    for reminder in reminders:
        target_label = _render_target(reminder, user)
        next_time = format_datetime(reminder.next_run_at, reminder.timezone)
        line = f"#{reminder.id} {target_label}: {reminder.message} (next: {next_time})"
        if reminder.recurrence:
            line += f" [recurring {reminder.time_expression}]"
        if reminder.dm and chat.type != ChatType.PRIVATE:
            line += " [dm]"
        lines.append(line)

    await update.message.reply_text("\n".join(lines))


def _render_target(reminder, current_user) -> str:
    if reminder.target_user and reminder.target_user.telegram_id == current_user.telegram_id:
        return "you"
    if reminder.target_user and reminder.target_user.username:
        return f"@{reminder.target_user.username}"
    if reminder.target_user and reminder.target_user.first_name:
        return reminder.target_user.first_name
    if reminder.target_username:
        return f"@{reminder.target_username}"
    return "you"

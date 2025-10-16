"""Implementation of the /remind command."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from ..parsing.time_parser import TimeParseError, parse_time_expression
from ..services.reminders import create_reminder
from ..services.settings import get_location, get_timezone
from ..services.users import ensure_user_and_chat, find_user_by_username
from ..utils.formatting import format_datetime
from .common import get_command_context

_TARGET_PATTERN = re.compile(r"^@(?P<username>[a-z0-9_]{5,})$", re.IGNORECASE)


@dataclass(slots=True)
class ReminderCommand:
    target_username: Optional[str]
    target_is_me: bool
    message_text: str
    time_expression: str
    dm: bool


def _parse_command_body(body: str) -> ReminderCommand:
    body = body.strip()
    dm = False
    lowered = body.lower()
    if lowered.endswith(" [dm]"):
        dm = True
        body = body[: -len(" [dm]")].strip()
    elif lowered.endswith(" dm"):
        dm = True
        body = body[: -len(" dm")].strip()

    target_is_me = True
    target_username: Optional[str] = None

    tokens = body.split(maxsplit=1)
    if tokens:
        first = tokens[0]
        rest = tokens[1] if len(tokens) > 1 else ""
        if first.lower() == "me":
            body = rest
        else:
            match = _TARGET_PATTERN.match(first)
            if match:
                target_is_me = False
                target_username = match.group("username")
                body = rest
    else:
        raise ValueError("Incomplete reminder command.")

    split_index = body.lower().rfind(" at ")
    if split_index == -1:
        raise ValueError("Please include 'at <time expression>' in the command.")

    message_text = body[:split_index].strip()
    time_expression = body[split_index + 4 :].strip()

    if not message_text:
        raise ValueError("Reminder message cannot be empty.")
    if not time_expression:
        raise ValueError("Time expression cannot be empty.")

    return ReminderCommand(
        target_username=target_username,
        target_is_me=target_is_me,
        message_text=message_text,
        time_expression=time_expression,
        dm=dm,
    )


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)

    message_text = update.message.text or ""
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text(
            "Usage: /remind [@username|me] <message> at <time expression> [dm]"
        )
        return

    try:
        parsed_command = _parse_command_body(parts[1])
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    async with command_context.database.session_factory() as session:
        async with session.begin():
            user, chat = await ensure_user_and_chat(
                session,
                telegram_user=update.effective_user,
                telegram_chat=update.effective_chat,
            )

            timezone_resolution = await get_timezone(
                session,
                user=user,
                chat=chat,
                default_timezone=command_context.config.default_timezone,
            )

            location, location_missing = await get_location(
                session,
                user=user if chat.type == ChatType.PRIVATE else None,
                chat=chat if chat.type != ChatType.PRIVATE else None,
            )

            target_user = user if parsed_command.target_is_me or chat.type == ChatType.PRIVATE else None

            if parsed_command.target_username and chat.type != ChatType.PRIVATE:
                target_user = await find_user_by_username(session, parsed_command.target_username)
                if not target_user:
                    await update.message.reply_text(
                        f"I don't know @{parsed_command.target_username} yet. Ask them to /start me in a private chat first."
                    )
                    return
                try:
                    await context.bot.get_chat_member(chat.telegram_id, target_user.telegram_id)
                except (BadRequest, Forbidden):
                    await update.message.reply_text(
                        f"@{parsed_command.target_username} is not a member of this chat."
                    )
                    return

            if parsed_command.dm and chat.type != ChatType.PRIVATE:
                if not target_user or not target_user.is_dm_enabled:
                    await update.message.reply_text(
                        "Cannot DM the target user yet. Ask them to /start the bot in a private chat and try again."
                    )
                    return

            try:
                parsed_time = parse_time_expression(
                    parsed_command.time_expression,
                    timezone=timezone_resolution.timezone,
                    location=location,
                )
            except TimeParseError as exc:
                await update.message.reply_text(f"Time parsing failed: {exc}")
                return

            stored_username = parsed_command.target_username
            if target_user and target_user.username:
                stored_username = target_user.username

            reminder = await create_reminder(
                session,
                chat=chat,
                creator=user,
                target_user=target_user,
                target_username=stored_username,
                message=parsed_command.message_text,
                time_expression=parsed_command.time_expression,
                timezone=timezone_resolution.timezone,
                next_run_at=parsed_time.next_run_at,
                recurrence=parsed_time.recurrence,
                dm=parsed_command.dm,
            )

        command_context.scheduler.schedule_reminder(reminder)

    acknowledgement = (
        f"Reminder #{reminder.id} scheduled for {format_datetime(parsed_time.local_time, parsed_time.timezone)}."
    )

    if parsed_time.is_recurring:
        acknowledgement += f" Recurs ({parsed_time.description})."

    if timezone_resolution.is_default:
        acknowledgement += "\nTip: set a timezone with /timezone set <Area/City>."

    solar_requires_location = False
    if parsed_time.solar_event:
        solar_requires_location = True
    elif parsed_time.recurrence:
        time_spec = parsed_time.recurrence.get("time") if isinstance(parsed_time.recurrence, dict) else None
        if isinstance(time_spec, dict) and time_spec.get("solar_event"):
            solar_requires_location = True

    if solar_requires_location and location_missing:
        acknowledgement += "\nTip: set a location with /location set <city> for accurate solar times."

    await update.message.reply_text(acknowledgement)

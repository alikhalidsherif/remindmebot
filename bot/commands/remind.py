"""Implementation of the /remind command."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from ..parsing.time_parser import ParsedTime, TimeParseError, parse_time_expression
from ..services.reminders import create_reminder
from ..services.settings import get_location, get_timezone
from ..services.users import ensure_user_and_chat, find_user_by_username
from ..utils.formatting import format_datetime
from .common import get_command_context

_TARGET_PATTERN = re.compile(r"^@(?P<username>[a-z0-9_]{5,})$", re.IGNORECASE)

_TIME_LEAD_PATTERN = re.compile(
    r"^(?:\d|"
    r"every\b|each\b|daily\b|weekly\b|monthly\b|yearly\b|annually\b|hourly\b|nightly\b|"
    r"in\b|after\b|within\b|by\b|before\b|around\b|about\b|"
    r"tomorrow\b|today\b|tonight\b|yesterday\b|day after\b|the day after\b|"
    r"next\b|this\b|coming\b|following\b|upcoming\b|last\b|"
    r"at\b|on\b|now\b|right now\b|end of\b|eod\b|eow\b|eom\b|eoy\b|"
    r"sunrise\b|sunset\b|dawn\b|dusk\b|midday\b|noon\b|midnight\b|lunchtime\b|"
    r"morning\b|afternoon\b|evening\b|night\b|"
    r"mon(?:day)?\b|tue(?:sday|s)?\b|wed(?:nesday|s)?\b|thu(?:rsday|rs)?\b|"
    r"fri(?:day)?\b|sat(?:urday)?\b|sun(?:day)?\b|"
    r"jan(?:uary)?\b|feb(?:ruary)?\b|mar(?:ch)?\b|apr(?:il)?\b|may\b|jun(?:e)?\b|"
    r"jul(?:y)?\b|aug(?:ust)?\b|sep(?:t|tember)?\b|oct(?:ober)?\b|"
    r"nov(?:ember)?\b|dec(?:ember)?\b|"
    r"half\b|quarter\b|a\b|an\b|one\b|two\b|three\b|four\b|five\b|six\b|"
    r"seven\b|eight\b|nine\b|ten\b|eleven\b|twelve\b)"
)

_MAX_SUFFIX_TOKENS = 6


@dataclass(slots=True)
class ReminderCommand:
    target_username: Optional[str]
    target_is_me: bool
    message_text: str
    time_expression: str
    dm: bool


def _looks_like_time(expression: str) -> bool:
    return bool(_TIME_LEAD_PATTERN.match(expression.strip()))


def _candidate_splits(body: str) -> list[tuple[str, str]]:
    """Return candidate ``(message, time expression)`` splits for a command body.

    Separators are tried first, longest time expression first, so that
    ``buy milk tomorrow at 5pm`` keeps ``tomorrow`` in the time expression.
    When the message has no explicit separator, trailing words are offered as
    the time expression instead (``buy milk in 2 hours``).
    """

    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(message: str, expression: str) -> None:
        message = message.strip()
        expression = expression.strip()
        if not message or not expression:
            return
        key = (message, expression)
        if key in seen:
            return
        seen.add(key)
        candidates.append(key)

    separator_positions = [
        match.start() for match in re.finditer(r"\sat\s+", body, re.IGNORECASE)
    ]
    for position in separator_positions:
        add(body[:position], body[position + len(" at ") :])

    tokens = body.split()
    max_tokens = min(_MAX_SUFFIX_TOKENS, len(tokens) - 1)
    for count in range(max_tokens, 0, -1):
        expression = " ".join(tokens[-count:])
        if not _looks_like_time(expression):
            continue
        add(" ".join(tokens[:-count]), expression)

    candidates.sort(key=lambda candidate: len(candidate[1]), reverse=True)
    return candidates


def _resolve_time(
    body: str,
    *,
    timezone: str,
    location,
) -> tuple[Optional[str], Optional[str], Optional[ParsedTime]]:
    for message_text, expression in _candidate_splits(body):
        try:
            parsed_time = parse_time_expression(
                expression, timezone=timezone, location=location
            )
        except TimeParseError:
            continue
        return message_text, expression, parsed_time
    return None, None, None


def _split_target_and_flags(body: str) -> tuple[Optional[str], bool, str, bool]:
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
    if not tokens:
        raise ValueError("Incomplete reminder command.")
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

    return target_username, target_is_me, body.strip(), dm


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)

    message_text = update.message.text or ""
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text(
            "Usage: /remind [@username|me] <message> at <time expression> [dm]\n"
            "Examples: /remind me standup at tomorrow 9am · "
            "/remind me pills at every day at 8am"
        )
        return

    try:
        target_username, target_is_me, body, dm = _split_target_and_flags(parts[1])
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    if not body:
        await update.message.reply_text(
            "Please include the reminder message and when it should be sent."
        )
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

            target_user = user if target_is_me or chat.type == ChatType.PRIVATE else None

            if target_username and chat.type != ChatType.PRIVATE:
                target_user = await find_user_by_username(session, target_username)
                if not target_user:
                    await update.message.reply_text(
                        f"I don't know @{target_username} yet. Ask them to /start me in a private chat first."
                    )
                    return
                try:
                    await context.bot.get_chat_member(chat.telegram_id, target_user.telegram_id)
                except (BadRequest, Forbidden):
                    await update.message.reply_text(
                        f"@{target_username} is not a member of this chat."
                    )
                    return

            if dm and chat.type != ChatType.PRIVATE:
                if not target_user or not target_user.is_dm_enabled:
                    await update.message.reply_text(
                        "Cannot DM the target user yet. Ask them to /start the bot in a private chat and try again."
                    )
                    return

            reminder_message, time_expression, parsed_time = _resolve_time(
                body,
                timezone=timezone_resolution.timezone,
                location=location,
            )

            if parsed_time is None or reminder_message is None or time_expression is None:
                await update.message.reply_text(
                    "I couldn't understand the time expression.\n"
                    "Try 'tomorrow at 5pm', 'next monday 9am', 'in 2 hours', "
                    "'december 25 at 10:00', 'tonight at 8pm' or 'every day at 8am'."
                )
                return

            stored_username = target_username
            if target_user and target_user.username:
                stored_username = target_user.username

            reminder = await create_reminder(
                session,
                chat=chat,
                creator=user,
                target_user=target_user,
                target_username=stored_username,
                message=reminder_message,
                time_expression=time_expression,
                timezone=timezone_resolution.timezone,
                next_run_at=parsed_time.next_run_at,
                recurrence=parsed_time.recurrence,
                dm=dm,
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

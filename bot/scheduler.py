"""Scheduling helper built on top of APScheduler."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Message
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.helpers import mention_html

from .db import Reminder, ReminderStatus
from .parsing.recurrence import compute_next_occurrence_from_rule
from .services.reminders import record_sent_message
from .services.settings import get_location


class ReminderScheduler:
    """Manage reminder scheduling and dispatch."""

    def __init__(self, *, database, config):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._database = database
        self._config = config
        self._scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self._application = None

    def bind_application(self, application) -> None:
        self._application = application

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def restore(self) -> None:
        async with self._database.session_factory() as session:
            stmt = select(Reminder).where(Reminder.status == ReminderStatus.ACTIVE)
            result = await session.execute(stmt)
            for reminder in result.scalars():
                self.schedule_reminder(reminder)

    def schedule_reminder(self, reminder: Reminder) -> None:
        if reminder.status != ReminderStatus.ACTIVE:
            return
        run_at = reminder.next_run_at.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if run_at <= now:
            run_at = now + timedelta(seconds=5)
        job_id = f"reminder-{reminder.id}"
        self._scheduler.add_job(
            self._dispatch,
            trigger=DateTrigger(run_date=run_at, timezone=timezone.utc),
            id=job_id,
            replace_existing=True,
            coalesce=True,
            kwargs={"reminder_id": reminder.id},
            misfire_grace_time=60,
        )
        self._logger.debug("Scheduled reminder %s at %s", reminder.id, run_at)

    def cancel(self, reminder_id: int) -> None:
        job_id = f"reminder-{reminder_id}"
        try:
            self._scheduler.remove_job(job_id)
        except JobLookupError:
            self._logger.debug("No scheduled job found for reminder %s", reminder_id)

    async def _dispatch(self, reminder_id: int) -> None:
        if self._application is None:
            self._logger.error("Application not bound to scheduler; cannot dispatch reminders.")
            return

        async with self._database.session_factory() as session:
            reminder = await self._fetch_reminder(session, reminder_id)
            if reminder is None:
                return
            if reminder.status != ReminderStatus.ACTIVE:
                return

            await self._handle_delivery(session, reminder)
            await session.commit()

            if reminder.status == ReminderStatus.ACTIVE:
                self.schedule_reminder(reminder)

    async def _fetch_reminder(self, session: AsyncSession, reminder_id: int) -> Reminder | None:
        stmt = (
            select(Reminder)
            .options(
                selectinload(Reminder.chat),
                selectinload(Reminder.creator),
                selectinload(Reminder.target_user),
            )
            .where(Reminder.id == reminder_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _handle_delivery(self, session: AsyncSession, reminder: Reminder) -> None:
        bot = self._application.bot
        now_utc = datetime.now(timezone.utc)

        target_chat_id = reminder.chat.telegram_id
        mention_user = reminder.target_user
        mention_username = reminder.target_username

        parse_mode = ParseMode.HTML

        message_body_html = escape(reminder.message)

        if reminder.chat.type in {"group", "supergroup"}:
            mention = self._build_mention(mention_user, mention_username)
            text = f"{mention} {message_body_html}" if mention else message_body_html
            message = await self._send_message(bot, target_chat_id, text, parse_mode=parse_mode)
            if message:
                await record_sent_message(
                    session,
                    reminder=reminder,
                    chat=reminder.chat,
                    telegram_chat_id=message.chat_id,
                    telegram_message_id=message.message_id,
                )
        else:
            message = await self._send_message(bot, target_chat_id, message_body_html, parse_mode=parse_mode)
            if message:
                await record_sent_message(
                    session,
                    reminder=reminder,
                    chat=reminder.chat,
                    telegram_chat_id=message.chat_id,
                    telegram_message_id=message.message_id,
                )

        dm_candidate = None
        if reminder.chat.type == "private":
            dm_candidate = reminder.target_user or reminder.creator
        else:
            dm_candidate = reminder.target_user

        if reminder.dm and dm_candidate and dm_candidate.is_dm_enabled:
            dm_message = await self._send_message(bot, dm_candidate.telegram_id, message_body_html, parse_mode=parse_mode)
            if dm_message:
                await record_sent_message(
                    session,
                    reminder=reminder,
                    chat=None,
                    telegram_chat_id=dm_message.chat_id,
                    telegram_message_id=dm_message.message_id,
                )

        reminder.last_triggered_at = now_utc
        if reminder.recurrence:
            await self._update_next_run(session, reminder)
        else:
            reminder.status = ReminderStatus.COMPLETED

    async def _update_next_run(self, session: AsyncSession, reminder: Reminder) -> None:
        timezone_name = reminder.timezone
        location, _ = await get_location(
            session,
            user=reminder.target_user if reminder.chat.type != "private" else reminder.creator,
            chat=reminder.chat if reminder.chat.type != "private" else None,
        )
        try:
            next_occurrence = compute_next_occurrence_from_rule(
                reminder.recurrence,
                timezone_name,
                after=reminder.next_run_at + timedelta(seconds=1),
                location=location,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Failed to compute next occurrence for reminder %s: %s", reminder.id, exc)
            reminder.status = ReminderStatus.CANCELLED
            return
        reminder.next_run_at = next_occurrence.astimezone(timezone.utc)

    async def _send_message(self, bot, chat_id: int, text: str, parse_mode: ParseMode) -> Optional[Message]:
        try:
            return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        except (Forbidden, BadRequest) as exc:
            self._logger.warning("Unable to send message to chat %s: %s", chat_id, exc)
            return None

    def _build_mention(self, user, username: Optional[str]) -> str | None:
        if user and user.telegram_id:
            display = user.first_name or username or "there"
            return mention_html(user.telegram_id, display)
        if username:
            return f"@{username}"
        return None

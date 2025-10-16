"""Reminder persistence helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import Chat, Reminder, ReminderStatus, SentMessage, User


async def create_reminder(
    session: AsyncSession,
    *,
    chat: Chat,
    creator: User,
    target_user: User | None,
    target_username: str | None,
    message: str,
    time_expression: str,
    timezone: str,
    next_run_at: datetime,
    recurrence: dict | None,
    dm: bool,
) -> Reminder:
    reminder = Reminder(
        chat=chat,
        creator=creator,
        target_user=target_user,
        target_username=target_username,
        message=message,
        time_expression=time_expression,
        timezone=timezone,
        next_run_at=next_run_at,
        recurrence=recurrence,
        dm=dm,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def get_reminder(session: AsyncSession, reminder_id: int) -> Reminder | None:
    result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    return result.scalar_one_or_none()


async def list_active_reminders(session: AsyncSession, *, chat: Chat) -> list[Reminder]:
    stmt: Select = (
        select(Reminder)
        .options(
            selectinload(Reminder.target_user),
            selectinload(Reminder.creator),
        )
        .where(
            Reminder.chat_id == chat.id,
            Reminder.status == ReminderStatus.ACTIVE,
        )
        .order_by(Reminder.next_run_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars())


async def cancel_reminder(session: AsyncSession, reminder: Reminder) -> Reminder:
    reminder.status = ReminderStatus.CANCELLED
    await session.flush()
    return reminder


async def record_sent_message(
    session: AsyncSession,
    *,
    reminder: Reminder,
    chat: Chat | None,
    telegram_chat_id: int,
    telegram_message_id: int,
) -> SentMessage:
    record = SentMessage(
        reminder=reminder,
        chat=chat,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
    )
    session.add(record)
    await session.flush()
    return record


async def find_reminder_by_message(
    session: AsyncSession,
    *,
    telegram_chat_id: int,
    telegram_message_id: int,
) -> Reminder | None:
    stmt = select(SentMessage).where(
        SentMessage.telegram_chat_id == telegram_chat_id,
        SentMessage.telegram_message_id == telegram_message_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    return record.reminder if record else None

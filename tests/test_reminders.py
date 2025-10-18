from __future__ import annotations

from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from bot.db import Chat, ReminderStatus, User
from bot.services.reminders import create_reminder, list_active_reminders, record_sent_message


@pytest.mark.asyncio
async def test_create_and_list_reminder(database):
    async with database.session_factory() as session:
        async with session.begin():
            user = User(telegram_id=123, username="alice")
            chat = Chat(telegram_id=-100, type="group", title="Team Chat")
            session.add_all([user, chat])

        async with session.begin():
            reminder = await create_reminder(
                session,
                chat=chat,
                creator=user,
                target_user=user,
                target_username="alice",
                message="Daily standup",
                time_expression="tomorrow 9am",
                timezone="UTC",
                next_run_at=datetime(2024, 1, 1, 9, 0, tzinfo=ZoneInfo("UTC")),
                recurrence=None,
                dm=False,
            )

        reminders = await list_active_reminders(session, chat=chat)

    assert len(reminders) == 1
    fetched = reminders[0]
    assert fetched.message == "Daily standup"
    assert fetched.status == ReminderStatus.ACTIVE


@pytest.mark.asyncio
async def test_record_sent_message(database):
    async with database.session_factory() as session:
        async with session.begin():
            user = User(telegram_id=456, username="bob")
            chat = Chat(telegram_id=-200, type="group", title="Ops")
            session.add_all([user, chat])

        async with session.begin():
            reminder = await create_reminder(
                session,
                chat=chat,
                creator=user,
                target_user=user,
                target_username="bob",
                message="Check servers",
                time_expression="in 1h",
                timezone="UTC",
                next_run_at=datetime(2024, 1, 1, 11, 0, tzinfo=ZoneInfo("UTC")),
                recurrence=None,
                dm=True,
            )
            record = await record_sent_message(
                session,
                reminder=reminder,
                chat=chat,
                telegram_chat_id=chat.telegram_id,
                telegram_message_id=42,
            )

        assert record.id is not None
        assert record.reminder_id == reminder.id

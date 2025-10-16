"""User and chat persistence helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Chat, User


async def get_or_create_user(session: AsyncSession, *, telegram_id: int) -> User:
    """Fetch a user by telegram id or create a new record."""

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)
    return user


async def sync_user_profile(user: User, *, username: Optional[str], first_name: Optional[str], last_name: Optional[str], language_code: Optional[str]) -> None:
    """Update a user profile fields in-place."""

    user.username = username or user.username
    user.first_name = first_name or user.first_name
    user.last_name = last_name or user.last_name
    user.language_code = language_code or user.language_code


async def get_or_create_chat(session: AsyncSession, *, telegram_id: int, chat_type: str) -> Chat:
    """Fetch or create a chat record."""

    result = await session.execute(select(Chat).where(Chat.telegram_id == telegram_id))
    chat = result.scalar_one_or_none()
    if chat is None:
        chat = Chat(telegram_id=telegram_id, type=chat_type)
        session.add(chat)
    return chat


async def sync_chat_metadata(chat: Chat, *, title: Optional[str]) -> None:
    """Update chat metadata fields."""

    if title:
        chat.title = title


async def find_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(func.lower(User.username) == username.lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def ensure_user_and_chat(
    session: AsyncSession,
    *,
    telegram_user,
    telegram_chat,
) -> tuple[User, Chat]:
    """Ensure both user and chat records exist for the current update."""

    user = await get_or_create_user(session, telegram_id=telegram_user.id)
    await sync_user_profile(
        user,
        username=getattr(telegram_user, "username", None),
        first_name=getattr(telegram_user, "first_name", None),
        last_name=getattr(telegram_user, "last_name", None),
        language_code=getattr(telegram_user, "language_code", None),
    )

    chat = await get_or_create_chat(
        session,
        telegram_id=telegram_chat.id,
        chat_type=getattr(telegram_chat, "type", "private"),
    )
    await sync_chat_metadata(chat, title=getattr(telegram_chat, "title", None))

    return user, chat

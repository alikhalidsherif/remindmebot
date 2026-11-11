"""Database models and session management for the reminder bot."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .config import Config

Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """Persist datetimes as UTC and always return timezone-aware values.

    SQLite discards timezone information, so a plain ``DateTime(timezone=True)``
    column comes back naive and ``astimezone()`` then guesses the host timezone.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ReminderStatus(enum.Enum):
    """Lifecycle status for reminders."""

    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class SettingScope(enum.Enum):
    """Scope for stored settings."""

    USER = "user"
    CHAT = "chat"


class SettingKey(enum.Enum):
    """Supported setting keys."""

    TIMEZONE = "timezone"
    LOCATION = "location"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[Optional[str]] = mapped_column(String(32))
    is_dm_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    settings: Mapped[list["Setting"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reminders_created: Mapped[list["Reminder"]] = relationship(
        back_populates="creator",
        cascade="all",
        foreign_keys="Reminder.creator_id",
    )
    reminders_targeted: Mapped[list["Reminder"]] = relationship(
        back_populates="target_user",
        cascade="all",
        foreign_keys="Reminder.target_user_id",
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    settings: Mapped[list["Setting"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[SettingScope] = mapped_column(SqlEnum(SettingScope), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chats.id"))
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[Optional[User]] = relationship(back_populates="settings")
    chat: Mapped[Optional[Chat]] = relationship(back_populates="settings")

    __table_args__ = (
        UniqueConstraint("scope", "user_id", "chat_id", "key", name="uq_settings_scope_subject_key"),
    )


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    target_username: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    time_expression: Mapped[str] = mapped_column(String(255), nullable=False)
    recurrence: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    status: Mapped[ReminderStatus] = mapped_column(
        SqlEnum(ReminderStatus), default=ReminderStatus.ACTIVE, nullable=False
    )
    dm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chat: Mapped[Chat] = relationship(back_populates="reminders", foreign_keys=[chat_id])
    creator: Mapped[User] = relationship(back_populates="reminders_created", foreign_keys=[creator_id])
    target_user: Mapped[Optional[User]] = relationship(
        back_populates="reminders_targeted", foreign_keys=[target_user_id]
    )
    sent_messages: Mapped[list["SentMessage"]] = relationship(
        back_populates="reminder", cascade="all, delete-orphan"
    )


class SentMessage(Base):
    __tablename__ = "sent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"), nullable=False)
    chat_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chats.id"))
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reminder: Mapped[Reminder] = relationship(back_populates="sent_messages")
    chat: Mapped[Optional[Chat]] = relationship()


@dataclass(slots=True)
class Database:
    """Bundle of database artefacts."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def create_database(config: Config) -> Database:
    """Create the async engine and the session factory."""

    engine = create_async_engine(config.database_url, future=True, echo=False)

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        """Enable foreign key constraints for SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return Database(engine=engine, session_factory=session_factory)


async def init_db(database: Database) -> None:
    """Create database tables."""

    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session(database: Database) -> AsyncIterator[AsyncSession]:
    """Yield an async session context manager style."""

    async with database.session_factory() as session:
        yield session

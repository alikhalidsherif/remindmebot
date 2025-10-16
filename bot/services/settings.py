"""Settings helpers for timezones and locations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Chat, Setting, SettingKey, SettingScope, User
from ..parsing.solar import Location
from ..utils.validators import normalize_timezone


@dataclass(slots=True)
class TimezoneResolution:
    timezone: str
    is_default: bool


async def _get_setting(
    session: AsyncSession,
    *,
    scope: SettingScope,
    key: SettingKey,
    user: User | None = None,
    chat: Chat | None = None,
) -> Setting | None:
    stmt = select(Setting).where(Setting.scope == scope, Setting.key == key.value)
    if scope == SettingScope.USER:
        if not user:
            return None
        stmt = stmt.where(Setting.user_id == user.id)
    if scope == SettingScope.CHAT:
        if not chat:
            return None
        stmt = stmt.where(Setting.chat_id == chat.id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _set_setting(
    session: AsyncSession,
    *,
    scope: SettingScope,
    key: SettingKey,
    value: str,
    user: User | None = None,
    chat: Chat | None = None,
) -> Setting:
    setting = await _get_setting(session, scope=scope, key=key, user=user, chat=chat)
    if setting is None:
        setting = Setting(scope=scope, key=key.value)
        if scope == SettingScope.USER and user:
            setting.user = user
        if scope == SettingScope.CHAT and chat:
            setting.chat = chat
        session.add(setting)
    setting.value = value
    return setting


async def get_timezone(
    session: AsyncSession,
    *,
    user: User | None,
    chat: Chat | None,
    default_timezone: str,
) -> TimezoneResolution:
    if chat:
        setting = await _get_setting(session, scope=SettingScope.CHAT, key=SettingKey.TIMEZONE, chat=chat)
        if setting:
            return TimezoneResolution(timezone=setting.value, is_default=False)
    if user:
        setting = await _get_setting(session, scope=SettingScope.USER, key=SettingKey.TIMEZONE, user=user)
        if setting:
            return TimezoneResolution(timezone=setting.value, is_default=False)
    return TimezoneResolution(timezone=default_timezone, is_default=True)


async def set_timezone(
    session: AsyncSession,
    *,
    source_chat: Chat | None,
    source_user: User | None,
    timezone: str,
) -> TimezoneResolution:
    timezone = normalize_timezone(timezone)
    if source_chat:
        await _set_setting(
            session,
            scope=SettingScope.CHAT,
            key=SettingKey.TIMEZONE,
            value=timezone,
            chat=source_chat,
        )
        return TimezoneResolution(timezone=timezone, is_default=False)
    if source_user:
        await _set_setting(
            session,
            scope=SettingScope.USER,
            key=SettingKey.TIMEZONE,
            value=timezone,
            user=source_user,
        )
        return TimezoneResolution(timezone=timezone, is_default=False)
    raise ValueError("Either source_chat or source_user must be provided.")


async def get_location(
    session: AsyncSession,
    *,
    user: User | None,
    chat: Chat | None,
) -> tuple[Location | None, bool]:
    if chat:
        setting = await _get_setting(session, scope=SettingScope.CHAT, key=SettingKey.LOCATION, chat=chat)
        if setting:
            return _decode_location(setting.value), False
    if user:
        setting = await _get_setting(session, scope=SettingScope.USER, key=SettingKey.LOCATION, user=user)
        if setting:
            return _decode_location(setting.value), False
    return None, True


async def set_location(
    session: AsyncSession,
    *,
    source_chat: Chat | None,
    source_user: User | None,
    location: Location,
) -> None:
    value = _encode_location(location)
    if source_chat:
        await _set_setting(
            session,
            scope=SettingScope.CHAT,
            key=SettingKey.LOCATION,
            value=value,
            chat=source_chat,
        )
        return
    if source_user:
        await _set_setting(
            session,
            scope=SettingScope.USER,
            key=SettingKey.LOCATION,
            value=value,
            user=source_user,
        )
        return
    raise ValueError("Either source_chat or source_user must be provided.")


async def clear_location(
    session: AsyncSession,
    *,
    source_chat: Chat | None,
    source_user: User | None,
) -> bool:
    if source_chat:
        setting = await _get_setting(session, scope=SettingScope.CHAT, key=SettingKey.LOCATION, chat=source_chat)
        if setting:
            await session.delete(setting)
            return True
        return False
    if source_user:
        setting = await _get_setting(session, scope=SettingScope.USER, key=SettingKey.LOCATION, user=source_user)
        if setting:
            await session.delete(setting)
            return True
        return False
    raise ValueError("Either source_chat or source_user must be provided.")


def _encode_location(location: Location) -> str:
    payload = {"lat": location.latitude, "lon": location.longitude, "name": location.name}
    return json.dumps(payload)


def _decode_location(value: str) -> Location:
    payload = json.loads(value)
    return Location(
        latitude=float(payload["lat"]),
        longitude=float(payload["lon"]),
        name=payload.get("name"),
    )

"""Implementation of the /location command."""
from __future__ import annotations

import asyncio

from geopy.geocoders import Nominatim
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..parsing.solar import Location
from ..services.settings import clear_location, get_location, set_location
from ..services.users import ensure_user_and_chat
from ..utils.validators import parse_lat_lon
from .common import get_command_context


async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None or update.effective_user is None:
        return

    command_context = get_command_context(context)
    args = (update.message.text or "").split(maxsplit=2)

    async with command_context.database.session_factory() as session:
        async with session.begin():
            user, chat = await ensure_user_and_chat(
                session,
                telegram_user=update.effective_user,
                telegram_chat=update.effective_chat,
            )

        if len(args) == 1 or (len(args) == 2 and args[1].lower() == "show"):
            location, _ = await get_location(
                session,
                user=user if chat.type == ChatType.PRIVATE else None,
                chat=chat if chat.type != ChatType.PRIVATE else None,
            )
            if location:
                await update.message.reply_text(
                    f"Current location: {location.name or f'{location.latitude},{location.longitude}'}"
                )
            else:
                await update.message.reply_text(
                    "No location configured yet. Use /location set <city> or /location set <lat,lon>."
                )
            return

        action = args[1].lower()
        if action == "clear":
            async with session.begin():
                removed = await clear_location(
                    session,
                    source_chat=chat if chat.type != ChatType.PRIVATE else None,
                    source_user=user if chat.type == ChatType.PRIVATE else None,
                )
            if removed:
                await update.message.reply_text("Location cleared.")
            else:
                await update.message.reply_text("No location was set.")
            return

        if action != "set" or len(args) < 3:
            await update.message.reply_text(
                "Usage: /location show | /location set <city|lat,lon> | /location clear"
            )
            return

        value = args[2]
        location = await _resolve_location(value, command_context.config.nominatim_user_agent)
        if location is None:
            await update.message.reply_text("I couldn't resolve that location. Try a more specific query or coordinates.")
            return

        async with session.begin():
            await set_location(
                session,
                source_chat=chat if chat.type != ChatType.PRIVATE else None,
                source_user=user if chat.type == ChatType.PRIVATE else None,
                location=location,
            )

        await update.message.reply_text(
            f"Location set to {location.name or f'{location.latitude},{location.longitude}'}."
        )


async def _resolve_location(query: str, user_agent: str) -> Location | None:
    query = query.strip()
    try:
        lat, lon = parse_lat_lon(query)
        return Location(latitude=lat, longitude=lon, name=query)
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    geocoder = Nominatim(user_agent=user_agent, timeout=10)

    def _geocode() -> Location | None:
        result = geocoder.geocode(query, exactly_one=True)
        if result is None:
            return None
        return Location(latitude=result.latitude, longitude=result.longitude, name=result.address)

    return await loop.run_in_executor(None, _geocode)

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from bot.config import Config
from bot.db import create_database, init_db


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def database(tmp_path: Path):
    db_path = tmp_path / "test-reminders.db"
    config = Config(
        telegram_bot_token="TEST",
        default_timezone="UTC",
        log_level="INFO",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        nominatim_user_agent="test-agent",
    )
    database = create_database(config)
    await init_db(database)
    try:
        yield database
    finally:
        await database.engine.dispose()

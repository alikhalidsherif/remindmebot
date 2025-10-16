"""Entrypoint for the Telegram reminder bot."""
from __future__ import annotations

import asyncio

from telegram.ext import Application

from .commands import register
from .config import load_config
from .db import create_database, init_db
from .scheduler import ReminderScheduler
from .utils.logging import setup_logging


def main() -> None:
    config = load_config()
    setup_logging(config)

    database = create_database(config)
    asyncio.run(init_db(database))

    scheduler = ReminderScheduler(database=database, config=config)

    async def on_startup(application: Application) -> None:
        scheduler.bind_application(application)
        scheduler.start()
        await scheduler.restore()

    async def on_shutdown(application: Application) -> None:
        scheduler.shutdown()

    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    application.bot_data["config"] = config
    application.bot_data["database"] = database
    application.bot_data["scheduler"] = scheduler

    register(application)

    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

# Telegram Reminder Bot

An asynchronous Telegram bot that provides flexible reminders for individuals and groups. It supports natural language time parsing, recurring schedules, solar-event triggers, DM delivery and per-user/per-group settings for timezone and location.

## Features

- `/remind` command with natural language time expressions (relative, absolute, recurring, solar events)
- Group-aware targeting with membership validation and optional DM delivery
- Persistent storage via SQLite and SQLAlchemy
- APScheduler-based dispatcher that survives restarts
- Per-user and per-group timezone/location settings
- `/list`, `/cancel`, `/cancelreminder`, `/timezone`, `/location` command suite
- Astral-powered solar event calculations with fallback times
- Geocoding via OpenStreetMap (Nominatim) for location lookups

## Requirements

- Python 3.11+
- Telegram Bot API token (`TELEGRAM_BOT_TOKEN`)

## Quick start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set required environment variables:

   ```bash
   export TELEGRAM_BOT_TOKEN=your-token-here
   export DEFAULT_TIMEZONE=Europe/Berlin        # optional, defaults to UTC
   export NOMINATIM_USER_AGENT=reminder-bot     # recommended for geopy
   ```

3. Run the bot:

   ```bash
   python -m bot.main
   ```

4. Interact with the bot on Telegram. Use `/start` in a private chat to enable DMs.

## Testing

Tests rely on `pytest` and `pytest-asyncio`:

```bash
pytest
```

## Configuration

Configuration is managed via environment variables (see `bot/config.py`). By default, the bot stores data in `data/reminders.db`; override with `DATABASE_URL` if required.

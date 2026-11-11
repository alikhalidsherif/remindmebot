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

## Supported time expressions

`/remind` accepts natural language in `message at <time expression>` form. The
separator is optional when the time expression is unambiguous
(`/remind me call mom in 2 hours` works as well).

- **Relative**: `in 30 minutes`, `in 2 hours`, `in 3 days`, `in 2 weeks`, `in 1 month`, `in a year`, `in half an hour`, `in an hour and a half`, `in a couple of days`, `30 minutes from now`, `in 2 days at 5pm`
- **Day keywords**: `today`, `tomorrow`, `tonight`, `the day after tomorrow`, `next week`, `next month`, `next year`, `end of day`/`eod`, `end of week`/`eow`, `end of month`/`eom`, `end of year`/`eoy`, `this weekend`, `next weekend`
- **Weekdays**: `monday 9am`, `next monday 9am`, `this friday 5pm`, `coming thursday at 8`, `monday next week 8am`, abbreviations such as `mon`, `wed`, `fri`
- **Clock times**: `5pm`, `5:30pm`, `17:45`, `17:45:30`, `9am`, `at 8`, `five pm`, `five thirty pm`, `half past five`, `quarter to six`, `5 o'clock pm`, `noon`, `midday`, `midnight`, plus parts of the day (`morning` 09:00, `afternoon` 15:00, `evening` 18:00, `night` 21:00)
- **Dates**: `2026-12-01`, `2026-12-01 18:30`, `2026-12-01T18:30:00Z`, `december 25`, `december 25 at 9am`, `25 december 2026`, `the 3rd of december at 5pm`, `12/25/2026` (month/day), `25/12/2026` (day/month when the first number is > 12), `the 5th`
- **Solar events**: `sunrise`, `sunset`, `dawn`, `dusk` with offsets such as `sunset+15m`, optionally anchored to a day (`tomorrow at sunrise`)
- **Recurring**: `every day at 10:00`, `every morning`, `every night at 11pm`, `every 15 seconds`, `every 30 minutes`, `every 2 hours`, `every weekday at 9am`, `every weekend at 10am`, `every monday and thursday at 9am`, `every 2 weeks on monday at 9am`, `every month on the 1st and 15th at 9am`, `every first monday of the month at 9am`, `every last friday of the month at 18:00`, `every year on december 25 at 9am`, and the shorthand forms `daily at 7:30`, `weekly on monday at 9`, `monthly on the 3rd at 9`, `yearly on july 4 at 10`

Recurring reminders are stored as rules, so the next occurrence is recomputed
from the stored rule rather than from the original phrase.

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

## Deployment

This bot can be deployed in two ways:

### Option 1: Automated Deployment (Recommended)

Use GitHub Actions with a self-hosted runner for secure, automated deployments:

- ✅ Secrets managed securely via GitHub Secrets
- ✅ Automated deployments on every push
- ✅ Zero-downtime updates with health checks
- ✅ Automatic database backups

**Quick Setup:**
```bash
# 1. Install self-hosted runner
./setup-runner.sh

# 2. Add TELEGRAM_BOT_TOKEN to GitHub Secrets
# (Settings → Secrets and variables → Actions)

# 3. Push to main branch
git push origin main
```

**📖 Detailed Guide:** [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md)

### Option 2: Manual Deployment

Use Docker Compose for traditional deployment:

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Add your TELEGRAM_BOT_TOKEN

# 2. Run pre-deployment checks
./pre-deploy-check.sh

# 3. Deploy
make deploy
# or: docker-compose up -d
```

**📖 Detailed Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

### Quick Commands

```bash
make deploy   # Full deployment with checks
make update   # Update and restart
make logs     # View logs
make status   # Check status
make backup   # Backup database
```

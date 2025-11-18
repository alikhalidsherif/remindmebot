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

# Deployment Guide

This guide covers deploying the Telegram Reminder Bot to a home server using Docker and Docker Compose.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Deployment Options](#deployment-options)
   - [Manual Deployment](#manual-deployment)
   - [Automated Deployment (Recommended)](#automated-deployment-recommended)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)
7. [CI/CD Integration](#cicd-integration)
8. [Backup & Recovery](#backup--recovery)

## Prerequisites

### Required Software

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git** (for cloning the repository)

### System Requirements

- **OS**: Linux (Ubuntu/Debian recommended), macOS, or Windows with WSL2
- **RAM**: Minimum 512MB, Recommended 1GB
- **Disk**: Minimum 1GB free space
- **Network**: Stable internet connection

### Getting a Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token securely - you'll need it for configuration

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd remindmebot
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your bot token
nano .env  # or use your preferred editor
```

Set at minimum:
```env
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
```

### 3. Run Pre-Deployment Checks

```bash
./pre-deploy-check.sh
```

This script validates:
- Docker installation
- Required files
- Environment configuration
- Network connectivity
- System resources

### 4. Deploy

```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f
```

That's it! Your bot should now be running.

## Configuration

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional
DEFAULT_TIMEZONE=UTC                    # Default timezone for users
NOMINATIM_USER_AGENT=reminder-bot      # User agent for geocoding
LOG_LEVEL=INFO                          # Logging level
DATABASE_URL=sqlite+aiosqlite:////data/reminders.db  # Database connection (absolute path)
```

### Docker Compose Configuration

The `docker-compose.yml` includes:

- **Resource Limits**: 512MB RAM, 1 CPU core max
- **Health Checks**: Monitors bot status
- **Auto-Restart**: Restarts on failure
- **Log Rotation**: Prevents disk space issues
- **Persistent Storage**: SQLite database in `./data` directory

## Deployment Options

There are two ways to deploy this bot:

1. **Automated Deployment (Recommended)**: Uses GitHub Actions and self-hosted runner for automated, secure deployments
2. **Manual Deployment**: Traditional Docker Compose deployment

### Automated Deployment (Recommended)

Automated deployment uses GitHub Actions with a self-hosted runner on your home server. This provides:

- ✅ **Secure secret management** via GitHub Secrets (no `.env` files to manage)
- ✅ **Automated deployments** on every push to main
- ✅ **Automatic database backups** before each deployment
- ✅ **Zero-downtime updates** with health checks
- ✅ **Deployment history** and rollback capability

**Prerequisites:**
- GitHub repository
- Self-hosted GitHub Actions runner on your server

**Setup Steps:**

1. **Install Self-Hosted Runner** (one-time setup)

   ```bash
   # Download and run the automated setup script
   curl -O https://raw.githubusercontent.com/<username>/remindmebot/main/setup-runner.sh
   chmod +x setup-runner.sh
   ./setup-runner.sh
   ```

   The script will:
   - Install GitHub Actions runner
   - Configure it as a system service
   - Set up Docker permissions
   - Create helper scripts

2. **Add Secrets to GitHub**

   Go to your repository: Settings → Secrets and variables → Actions

   Add these secrets:
   - **Required**: `TELEGRAM_BOT_TOKEN` (from @BotFather)
   - **Optional**: `DEFAULT_TIMEZONE`, `LOG_LEVEL`, `NOMINATIM_USER_AGENT`

3. **Deploy**

   Simply push to the main branch:
   ```bash
   git push origin main
   ```

   Or trigger manually:
   - Go to Actions tab → "Deploy to Home Server"
   - Click "Run workflow"

4. **Monitor Deployment**

   Watch the deployment progress in the Actions tab of your repository.

**📖 For detailed instructions, see:** [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md)

**Helper Commands:**
```bash
# Check runner status
~/runner-status.sh

# Restart runner
~/runner-restart.sh

# View bot logs
docker logs -f telegram-reminder-bot

# Check container status
docker ps -f name=telegram-reminder-bot
```

### Manual Deployment

For traditional Docker Compose deployment without CI/CD:

#### Standard Deployment

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f bot
```

#### Building from Scratch

```bash
# Rebuild image
docker-compose build --no-cache

# Start with fresh build
docker-compose up -d --force-recreate
```

#### Updating the Bot

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Or use the update script
./update.sh
```

#### Using Makefile Commands

```bash
# Deploy (with pre-checks)
make deploy

# Update
make update

# View logs
make logs

# Check status
make status

# Backup database
make backup
```

## Monitoring & Maintenance

### Viewing Logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Logs from specific time
docker-compose logs --since 30m
```

### Health Checks

```bash
# Check container health
docker-compose ps

# Detailed container info
docker inspect telegram-reminder-bot
```

### Resource Usage

```bash
# Monitor resource usage
docker stats telegram-reminder-bot

# Check disk usage
docker system df
```

### Database Backup

```bash
# Backup SQLite database
docker-compose exec bot cp /data/reminders.db /data/reminders.db.backup

# Copy to host
cp ./data/reminders.db ./backups/reminders_$(date +%Y%m%d_%H%M%S).db
```

## Troubleshooting

### Bot Not Starting

1. **Check logs**:
   ```bash
   docker-compose logs bot
   ```

2. **Verify token**:
   ```bash
   echo $TELEGRAM_BOT_TOKEN
   ```

3. **Test bot token**:
   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
   ```

### Database Issues

**Permission errors when creating/opening database:**

The container runs as a non-root user (specified by UID/GID). Ensure the `./data` directory has proper permissions:

**Quick Fix (Recommended):**
```bash
# Run the automated fix script
./fix-data-permissions.sh

# Then set environment variables and restart
export UID=$(id -u) GID=$(id -g)
docker-compose down
docker-compose up -d
```

**Manual Fix:**
```bash
# Set proper ownership (use your user's UID/GID)
export UID=$(id -u) GID=$(id -g)
sudo chown $UID:$GID data/
chmod 755 data/

# Restart the container
docker-compose down
docker-compose up -d
```

**Check database file and permissions:**

```bash
# Check database file on host
ls -lh data/reminders.db

# Check permissions inside container
docker-compose exec bot ls -la /data
```

### Network Issues

```bash
# Test Telegram API connectivity
docker-compose exec bot ping -c 3 api.telegram.org

# Check DNS resolution
docker-compose exec bot nslookup api.telegram.org
```

### Container Restart Loop

```bash
# Check health status
docker inspect telegram-reminder-bot | grep -A 10 Health

# Review startup logs
docker-compose logs --tail=50 bot
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Permission denied on data directory | `sudo chown $(id -u):$(id -g) data && chmod 755 data` |
| Unable to open database file | Ensure data directory has correct ownership (see above) |
| Container constantly restarting | Check bot token is valid |
| Out of memory errors | Increase Docker memory limits |
| Database locked | Stop duplicate bot instances |

## CI/CD Integration

### GitHub Actions

The repository includes a CI/CD pipeline (`.github/workflows/ci-cd.yml`) that:

1. **Runs tests** on every push/PR
2. **Builds Docker image** and caches layers
3. **Scans for vulnerabilities** using Trivy
4. **Publishes images** to GitHub Container Registry (optional)
5. **Notifies deployment readiness**

### Setting Up CI/CD

1. **Enable GitHub Actions** in your repository settings

2. **Add secrets** (Settings → Secrets and variables → Actions):
   - `TELEGRAM_BOT_TOKEN`: Your bot token (for testing)
   - `GHCR_TOKEN`: GitHub token for container registry (optional)

3. **Workflow triggers**:
   - Push to `main`, `develop`, or `claude/**` branches
   - Pull requests to `main` or `develop`
   - Manual workflow dispatch

### Continuous Deployment (Optional)

For automatic deployment to your home server:

1. **Set up SSH access** from GitHub Actions to your server
2. **Add deployment step** to workflow:

```yaml
- name: Deploy to home server
  uses: appleboy/ssh-action@master
  with:
    host: ${{ secrets.SERVER_HOST }}
    username: ${{ secrets.SERVER_USER }}
    key: ${{ secrets.SSH_PRIVATE_KEY }}
    script: |
      cd /path/to/remindmebot
      git pull origin main
      ./pre-deploy-check.sh
      docker-compose up -d --build
```

## Backup & Recovery

### Automated Backup Script

Create `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp ./data/reminders.db "$BACKUP_DIR/reminders_$TIMESTAMP.db"

# Keep only last 7 days
find $BACKUP_DIR -name "reminders_*.db" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/reminders_$TIMESTAMP.db"
```

### Cron Job for Daily Backups

```bash
# Add to crontab (crontab -e)
0 2 * * * /path/to/remindmebot/backup.sh
```

### Restore from Backup

```bash
# Stop bot
docker-compose down

# Restore database
cp ./backups/reminders_YYYYMMDD_HHMMSS.db ./data/reminders.db

# Start bot
docker-compose up -d
```

## Advanced Configuration

### Using PostgreSQL Instead of SQLite

1. **Add PostgreSQL to docker-compose.yml**:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: reminders
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

  bot:
    depends_on:
      - postgres
    environment:
      DATABASE_URL: postgresql+asyncpg://botuser:${DB_PASSWORD}@postgres/reminders

volumes:
  postgres-data:
```

2. **Update requirements.txt**:
```
asyncpg==0.29.0
```

### Reverse Proxy Setup (Optional)

If you need to expose metrics or health endpoints:

```yaml
# Add to docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - bot
```

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use strong tokens** and rotate them periodically
3. **Keep Docker updated** for security patches
4. **Run as non-root user** (already configured)
5. **Limit resource usage** to prevent DoS
6. **Monitor logs** for suspicious activity
7. **Regular backups** of database
8. **Use firewall rules** to restrict access

## Performance Tuning

### For Low-Resource Servers

Adjust `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 256M
```

### For High-Load Scenarios

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
```

## Support

For issues or questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review logs: `docker-compose logs -f`
3. Run pre-deployment checks: `./pre-deploy-check.sh`
4. Check GitHub issues
5. Consult the README.md

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)

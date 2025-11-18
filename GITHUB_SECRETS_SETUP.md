# GitHub Secrets & Self-Hosted Runner Setup Guide

This guide walks you through setting up GitHub Secrets and a self-hosted GitHub Actions runner for secure automated deployment of your Telegram Reminder Bot.

## Table of Contents

1. [Understanding the Secure Deployment Flow](#understanding-the-secure-deployment-flow)
2. [Step 1: Store Secrets in GitHub](#step-1-store-secrets-in-github)
3. [Step 2: Set Up Self-Hosted Runner](#step-2-set-up-self-hosted-runner)
4. [Step 3: Test the Deployment](#step-3-test-the-deployment)
5. [Security Best Practices](#security-best-practices)
6. [Troubleshooting](#troubleshooting)

## Understanding the Secure Deployment Flow

Here's how the secure deployment works:

```
┌─────────────────┐
│  GitHub Secrets │  ← Your secrets stored securely in GitHub
│   (Vault)       │
└────────┬────────┘
         │
         │ (1) Push to main branch
         ▼
┌─────────────────────┐
│  GitHub Actions     │  ← Workflow triggered
│  (deploy.yml)       │
└──────────┬──────────┘
           │
           │ (2) Pulls secrets from vault
           ▼
┌─────────────────────────┐
│  Self-Hosted Runner     │  ← Running on your server
│  (Your Home Server)     │
└──────────┬──────────────┘
           │
           │ (3) Creates .env file with secrets
           ▼
┌─────────────────────────┐
│  Docker Container       │  ← Bot reads .env file
│  (Telegram Bot)         │
└──────────┬──────────────┘
           │
           │ (4) .env file deleted (security)
           ▼
      [Running Bot]
```

**Key Security Features:**
- Secrets never appear in code or logs
- `.env` file is created temporarily during deployment
- `.env` file is securely deleted after container starts
- All secrets are encrypted in GitHub's vault

## Step 1: Store Secrets in GitHub

### 1.1 Navigate to Repository Settings

1. Go to your GitHub repository: `https://github.com/<username>/remindmebot`
2. Click on **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**

### 1.2 Add Required Secrets

Click the **New repository secret** button for each secret below:

#### Required Secret

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot API token from @BotFather | `123456789:ABCdefGHIjklMNOpqrsTUVwxyz` |

**Steps to add:**
1. Click **New repository secret**
2. **Name:** `TELEGRAM_BOT_TOKEN`
3. **Secret:** Paste your bot token (get it from @BotFather on Telegram)
4. Click **Add secret**

#### Optional Secrets

| Secret Name | Description | Default Value | Example |
|-------------|-------------|---------------|---------|
| `DEFAULT_TIMEZONE` | Default timezone for users | `UTC` | `America/New_York` |
| `NOMINATIM_USER_AGENT` | User agent for geocoding | `reminder-bot` | `my-reminder-bot` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG` or `WARNING` |

**Note:** If you don't add optional secrets, the workflow will use the default values.

### 1.3 Verify Secrets Are Added

After adding secrets, you should see them listed (values will be hidden):

```
TELEGRAM_BOT_TOKEN              Updated 1 minute ago
DEFAULT_TIMEZONE                Updated 1 minute ago
LOG_LEVEL                       Updated 1 minute ago
NOMINATIM_USER_AGENT           Updated 1 minute ago
```

## Step 2: Set Up Self-Hosted Runner

A self-hosted runner is a service that runs on your home server and executes GitHub Actions workflows.

### 2.1 System Requirements

**Minimum Requirements:**
- **OS:** Linux (Ubuntu 20.04+ recommended), macOS, or Windows
- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 10GB free space
- **Docker:** Must be installed and running
- **Network:** Stable internet connection

### 2.2 Install GitHub Actions Runner

#### Option A: Automated Installation Script

We've created a script to automate the runner setup:

```bash
# Download and run the setup script
curl -O https://raw.githubusercontent.com/<username>/remindmebot/main/setup-runner.sh
chmod +x setup-runner.sh
./setup-runner.sh
```

#### Option B: Manual Installation

**Step 1: Navigate to Runner Settings**

1. Go to your repository on GitHub
2. Click **Settings** → **Actions** → **Runners**
3. Click **New self-hosted runner**
4. Select your operating system (Linux, macOS, or Windows)

**Step 2: Download and Configure Runner**

GitHub will show you commands like these (use the actual commands from your screen):

```bash
# Create a directory for the runner
mkdir actions-runner && cd actions-runner

# Download the runner (Linux x64 example)
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

# Extract the installer
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# Configure the runner
./config.sh --url https://github.com/<username>/remindmebot --token <YOUR_TOKEN>
```

**Step 3: Configure the Runner**

When prompted during configuration:

```
Enter the name of the runner group [press Enter for Default]:
[Press Enter]

Enter the name of runner [press Enter for hostname]:
home-server-runner

Enter any additional labels (ex. label-1,label-2) [press Enter to skip]:
[Press Enter]

Enter name of work folder [press Enter for _work]:
[Press Enter]
```

**Step 4: Install as a Service (Recommended)**

This ensures the runner starts automatically:

**Linux (systemd):**
```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

**macOS (launchd):**
```bash
./svc.sh install
./svc.sh start
./svc.sh status
```

**Step 5: Verify Runner is Connected**

1. Go to **Settings** → **Actions** → **Runners** in your GitHub repository
2. You should see your runner listed with a green "Idle" status

### 2.3 Configure Runner Permissions

Ensure the runner user has Docker permissions:

```bash
# Add user to docker group
sudo usermod -aG docker $(whoami)

# Apply the group membership (or log out and back in)
newgrp docker

# Test Docker access
docker ps
```

### 2.4 Set Up Working Directory

```bash
# Create a directory for deployments
mkdir -p ~/remindmebot-deployments
cd ~/remindmebot-deployments

# The runner will clone the repository here during deployment
```

## Step 3: Test the Deployment

### 3.1 Trigger a Deployment

There are two ways to trigger a deployment:

**Method 1: Push to Main Branch**
```bash
# Make a small change and push
git checkout main
echo "# Test deployment" >> README.md
git add README.md
git commit -m "test: trigger deployment"
git push origin main
```

**Method 2: Manual Workflow Dispatch**
1. Go to **Actions** tab in your repository
2. Click on **Deploy to Home Server** workflow
3. Click **Run workflow** button
4. Select `main` branch
5. Click **Run workflow**

### 3.2 Monitor the Deployment

1. Go to the **Actions** tab
2. Click on your running workflow
3. Click on the **Deploy to Self-Hosted Server** job
4. Watch the steps execute in real-time

**Expected Output:**
```
✓ Checkout code
✓ Create .env file from secrets
✓ Backup existing database
✓ Stop and remove old container
✓ Build Docker image
✓ Run new container
✓ Wait for container to be healthy
✓ Verify bot is working
✓ Remove .env file
✓ Deployment Successful
```

### 3.3 Verify Bot is Running

On your home server:

```bash
# Check container status
docker ps -f name=telegram-reminder-bot

# View logs
docker logs -f telegram-reminder-bot

# Test the bot on Telegram
# Send /start to your bot
```

## Security Best Practices

### ✅ DO:

1. **Use GitHub Secrets for ALL sensitive data**
   - Never commit `.env` files to git
   - Never hardcode secrets in code

2. **Limit runner access**
   - Run the runner as a non-root user when possible
   - Use firewall rules to restrict runner access

3. **Rotate secrets regularly**
   - Update `TELEGRAM_BOT_TOKEN` periodically
   - Use GitHub's audit log to track secret access

4. **Monitor deployment logs**
   - Check for failed deployments
   - Review logs for suspicious activity

5. **Keep runner updated**
   - Update the runner software regularly
   - Keep Docker and system packages updated

### ❌ DON'T:

1. **Never commit `.env` files** to your repository
   - Add `.env` to `.gitignore` (already configured)

2. **Never expose secrets in logs**
   - The workflow masks secret values automatically

3. **Never share your `TELEGRAM_BOT_TOKEN`**
   - Anyone with this token can control your bot

4. **Don't run runner as root** (if possible)
   - Use a dedicated user with minimal permissions

## Troubleshooting

### Problem: "TELEGRAM_BOT_TOKEN is not set" Error

**Solution:**
1. Verify secret is added in GitHub: Settings → Secrets → Actions
2. Ensure the secret name is exactly `TELEGRAM_BOT_TOKEN` (case-sensitive)
3. Re-run the workflow

### Problem: Runner Shows "Offline" Status

**Solution:**
```bash
# Check runner status
cd ~/actions-runner
./svc.sh status

# If stopped, restart it
sudo ./svc.sh start  # Linux
./svc.sh start       # macOS

# Check logs
journalctl -u actions.runner.* -f  # Linux
```

### Problem: "Permission denied" for Docker

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $(whoami)

# Log out and back in, or:
newgrp docker

# Verify
docker ps
```

### Problem: Container Fails to Start

**Solution:**
1. Check the workflow logs in GitHub Actions
2. Verify secrets are set correctly
3. Check container logs on server:
   ```bash
   docker logs telegram-reminder-bot
   ```

### Problem: ".env file not found" During Deployment

**Solution:**
- This is normal! The workflow creates and deletes `.env` automatically
- Check the "Create .env file from secrets" step in workflow logs
- Verify `TELEGRAM_BOT_TOKEN` is set in GitHub Secrets

### Problem: Old Containers Not Removed

**Solution:**
```bash
# Manually clean up
docker stop telegram-reminder-bot
docker rm telegram-reminder-bot

# Remove old images
docker image prune -a
```

## Advanced Configuration

### Adding More Secrets

If you need to add custom environment variables:

1. Add secret in GitHub: Settings → Secrets → Actions
2. Update `.github/workflows/deploy.yml`:
   ```yaml
   - name: Create .env file from secrets
     run: |
       echo "YOUR_NEW_SECRET=${{ secrets.YOUR_NEW_SECRET }}" >> .env
   ```

### Using PostgreSQL Instead of SQLite

1. Add database secrets:
   - `DB_PASSWORD`
   - `DB_USER`
   - `DB_NAME`

2. Update workflow to create DATABASE_URL:
   ```yaml
   echo "DATABASE_URL=postgresql+asyncpg://${{ secrets.DB_USER }}:${{ secrets.DB_PASSWORD }}@postgres:5432/${{ secrets.DB_NAME }}" >> .env
   ```

### Multiple Environments (Staging/Production)

Use GitHub Environments:

1. Create environments: Settings → Environments
2. Add environment-specific secrets
3. Update workflow:
   ```yaml
   jobs:
     deploy:
       runs-on: self-hosted
       environment: production  # or staging
   ```

## Maintenance

### Regular Tasks

**Weekly:**
- Check deployment logs for errors
- Verify bot is responding to commands

**Monthly:**
- Update runner: `./config.sh --update`
- Review and clean old Docker images
- Test backup restoration

**Quarterly:**
- Rotate `TELEGRAM_BOT_TOKEN`
- Review GitHub Actions usage
- Update system packages

### Backup Strategy

Backups are automatic with each deployment:
- Database backed up to `./backups/`
- Last 10 backups are kept
- Manual backup: `make backup`

## Support & Resources

- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Self-Hosted Runners:** https://docs.github.com/en/actions/hosting-your-own-runners
- **Docker Security:** https://docs.docker.com/engine/security/
- **Repository Issues:** https://github.com/<username>/remindmebot/issues

## Summary Checklist

Before going live, ensure you've completed:

- [ ] Added `TELEGRAM_BOT_TOKEN` to GitHub Secrets
- [ ] Set up self-hosted runner on your server
- [ ] Runner shows "Idle" status in GitHub
- [ ] Tested deployment with workflow dispatch
- [ ] Verified bot container is running
- [ ] Tested bot responds to `/start` command
- [ ] Confirmed `.env` file is not in repository
- [ ] Reviewed security best practices
- [ ] Set up automated backups
- [ ] Documented your specific configuration

Once all items are checked, your bot is ready for production! 🚀

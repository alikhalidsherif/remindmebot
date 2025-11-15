#!/bin/bash

# Update script for Telegram Reminder Bot
# This script safely updates the bot with minimal downtime

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Telegram Reminder Bot - Update Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Backup current database
echo -e "${YELLOW}[1/6]${NC} Backing up database..."
mkdir -p backups
if [ -f "./data/reminders.db" ]; then
    BACKUP_FILE="./backups/reminders_$(date +%Y%m%d_%H%M%S).db"
    cp ./data/reminders.db "$BACKUP_FILE"
    echo -e "${GREEN}✓${NC} Database backed up to: $BACKUP_FILE"
else
    echo -e "${YELLOW}⚠${NC} No database found to backup (fresh installation?)"
fi

# Step 2: Pull latest changes
echo ""
echo -e "${YELLOW}[2/6]${NC} Pulling latest changes from git..."
git fetch origin
CURRENT_BRANCH=$(git branch --show-current)
git pull origin "$CURRENT_BRANCH"
echo -e "${GREEN}✓${NC} Code updated from branch: $CURRENT_BRANCH"

# Step 3: Stop current bot
echo ""
echo -e "${YELLOW}[3/6]${NC} Stopping current bot..."
docker-compose down
echo -e "${GREEN}✓${NC} Bot stopped"

# Step 4: Build new image
echo ""
echo -e "${YELLOW}[4/6]${NC} Building new Docker image..."
docker-compose build --no-cache
echo -e "${GREEN}✓${NC} Image built successfully"

# Step 5: Start updated bot
echo ""
echo -e "${YELLOW}[5/6]${NC} Starting updated bot..."
docker-compose up -d
echo -e "${GREEN}✓${NC} Bot started"

# Step 6: Verify deployment
echo ""
echo -e "${YELLOW}[6/6]${NC} Verifying deployment..."
sleep 5

if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓${NC} Bot is running successfully"

    # Show container status
    echo ""
    docker-compose ps

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Update completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "To check status:"
    echo "  docker-compose ps"
else
    echo -e "${RED}✗${NC} Bot failed to start. Check logs:"
    echo "  docker-compose logs"
    exit 1
fi

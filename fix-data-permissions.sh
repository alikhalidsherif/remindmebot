#!/bin/bash

# Quick fix script for data directory permission issues
# This script ensures the data directory has the correct ownership for Docker

set -e

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Data Directory Permission Fix"
echo "=========================================="
echo ""

# Get current user's UID and GID
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

echo "Current user UID:GID = $CURRENT_UID:$CURRENT_GID"
echo ""

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo -e "${YELLOW}Creating data directory...${NC}"
    mkdir -p data
    echo -e "${GREEN}✓${NC} Data directory created"
else
    echo -e "${GREEN}✓${NC} Data directory exists"
fi

# Set ownership
echo ""
echo -e "${YELLOW}Setting ownership to $CURRENT_UID:$CURRENT_GID...${NC}"
if sudo chown $CURRENT_UID:$CURRENT_GID data/ 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Ownership set successfully"
else
    echo -e "${RED}✗${NC} Failed to set ownership. You may need to run:"
    echo "  sudo chown $CURRENT_UID:$CURRENT_GID data/"
fi

# Set permissions
echo ""
echo -e "${YELLOW}Setting permissions to 755...${NC}"
if chmod 755 data/ 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Permissions set successfully"
else
    echo -e "${RED}✗${NC} Failed to set permissions"
fi

# Check if any database files exist and fix their permissions too
if [ -f "data/reminders.db" ]; then
    echo ""
    echo -e "${YELLOW}Fixing database file permissions...${NC}"
    sudo chown $CURRENT_UID:$CURRENT_GID data/reminders.db 2>/dev/null
    chmod 644 data/reminders.db 2>/dev/null
    echo -e "${GREEN}✓${NC} Database file permissions fixed"
fi

# Export UID and GID for docker-compose
echo ""
echo "=========================================="
echo -e "${GREEN}Done!${NC}"
echo "=========================================="
echo ""
echo "To ensure docker-compose uses the correct user, export these variables:"
echo ""
echo -e "${YELLOW}  export UID=$CURRENT_UID GID=$CURRENT_GID${NC}"
echo ""
echo "Then restart the container:"
echo ""
echo "  docker-compose down"
echo "  docker-compose up -d"
echo ""

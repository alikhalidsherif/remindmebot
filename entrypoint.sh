#!/bin/bash
set -e

echo "==================================="
echo "Telegram Reminder Bot - Starting"
echo "==================================="
echo ""

# Show current user info
echo "Container user: $(id)"
echo ""

# Check if /data directory exists
if [ ! -d /data ]; then
    echo "ERROR: /data directory does not exist"
    echo "This should not happen as it's created in the Dockerfile"
    exit 1
fi

# Check /data directory permissions
echo "Data directory info:"
ls -la /data || echo "Cannot list /data directory"
echo ""

# Test write permissions
if ! touch /data/.write-test 2>/dev/null; then
    echo "=================================="
    echo "ERROR: Cannot write to /data directory"
    echo "=================================="
    echo ""
    echo "This is usually a permissions issue. To fix:"
    echo ""
    echo "1. Stop the container:"
    echo "   docker-compose down"
    echo ""
    echo "2. Fix data directory permissions on the host:"
    echo "   mkdir -p ./data"
    echo "   sudo chown \$(id -u):\$(id -g) ./data"
    echo "   chmod 755 ./data"
    echo ""
    echo "3. Or use the provided script:"
    echo "   ./fix-data-permissions.sh"
    echo ""
    echo "4. Restart the container:"
    echo "   docker-compose up -d"
    echo ""
    exit 1
fi

# Clean up test file
rm -f /data/.write-test

echo "✓ Data directory is writable"
echo ""
echo "Starting application..."
echo ""

# Start the bot
exec python -m bot.main

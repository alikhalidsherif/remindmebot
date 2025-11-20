#!/bin/bash

# Pre-deployment checks for Telegram Reminder Bot
# This script validates the environment and configuration before deployment

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Helper functions
print_header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo "  ℹ $1"
}

# Check 1: Docker installation
print_header "1. Checking Docker Installation"
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker is installed: $DOCKER_VERSION"

    # Check if Docker daemon is running
    if docker info &> /dev/null; then
        print_success "Docker daemon is running"
    else
        print_error "Docker daemon is not running. Please start Docker."
    fi
else
    print_error "Docker is not installed. Please install Docker first."
fi

# Check 2: Docker Compose installation
print_header "2. Checking Docker Compose Installation"
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    if docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version)
    else
        COMPOSE_VERSION=$(docker-compose --version)
    fi
    print_success "Docker Compose is installed: $COMPOSE_VERSION"
else
    print_error "Docker Compose is not installed. Please install Docker Compose."
fi

# Check 3: Required files
print_header "3. Checking Required Files"
REQUIRED_FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "requirements.txt"
    "bot/main.py"
    "bot/config.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "Found: $file"
    else
        print_error "Missing: $file"
    fi
done

# Check 4: Environment variables
print_header "4. Checking Environment Variables"

# Check for .env file
if [ -f ".env" ]; then
    print_success "Found .env file"
    source .env 2>/dev/null || true
else
    print_warning "No .env file found. Using environment variables or defaults."
    print_info "Consider creating a .env file from .env.example"
fi

# Check TELEGRAM_BOT_TOKEN
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    print_error "TELEGRAM_BOT_TOKEN is not set"
    print_info "This is required for the bot to work. Set it in .env or export it."
else
    # Validate token format (should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
    if [[ $TELEGRAM_BOT_TOKEN =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
        TOKEN_PREVIEW="${TELEGRAM_BOT_TOKEN:0:10}...${TELEGRAM_BOT_TOKEN: -5}"
        print_success "TELEGRAM_BOT_TOKEN is set and formatted correctly: $TOKEN_PREVIEW"
    else
        print_error "TELEGRAM_BOT_TOKEN has invalid format"
        print_info "Expected format: <bot_id>:<token>"
    fi
fi

# Check optional variables
if [ -n "$DEFAULT_TIMEZONE" ]; then
    print_success "DEFAULT_TIMEZONE is set: $DEFAULT_TIMEZONE"
else
    print_info "DEFAULT_TIMEZONE not set, will use UTC"
fi

if [ -n "$LOG_LEVEL" ]; then
    print_success "LOG_LEVEL is set: $LOG_LEVEL"
else
    print_info "LOG_LEVEL not set, will use INFO"
fi

# Check 5: Data directory
print_header "5. Checking Data Directory"
if [ -d "data" ]; then
    print_success "Data directory exists"

    # Check permissions
    if [ -w "data" ]; then
        print_success "Data directory is writable"
    else
        print_error "Data directory is not writable"
        print_info "Run: chmod 755 data"
    fi
else
    print_warning "Data directory does not exist. Creating it now..."
    if mkdir -p data 2>/dev/null; then
        print_success "Created data directory"
        # Ensure the directory has proper permissions for the container user
        chmod 755 data 2>/dev/null

        # If UID/GID are set, try to set ownership (may require sudo)
        if [ -n "$UID" ] && [ -n "$GID" ]; then
            if chown $UID:$GID data 2>/dev/null; then
                print_success "Set ownership to $UID:$GID"
            else
                print_info "Could not set ownership. If you get permission errors, run:"
                print_info "  sudo chown \$UID:\$GID data"
            fi
        else
            print_info "Set UID and GID environment variables for proper ownership:"
            print_info "  export UID=\$(id -u) GID=\$(id -g)"
        fi
    else
        print_error "Failed to create data directory"
    fi
fi

# Check 6: Port availability (not needed for polling, but good to check)
print_header "6. Checking System Resources"

# Check available memory
if command -v free &> /dev/null; then
    AVAILABLE_MEM=$(free -m | awk 'NR==2 {print $7}')
    if [ "$AVAILABLE_MEM" -gt 512 ]; then
        print_success "Sufficient memory available: ${AVAILABLE_MEM}MB"
    else
        print_warning "Low memory: ${AVAILABLE_MEM}MB available. Recommended: 512MB+"
    fi
else
    print_info "Cannot check memory availability (free command not found)"
fi

# Check disk space
AVAILABLE_DISK=$(df -m . | awk 'NR==2 {print $4}')
if [ "$AVAILABLE_DISK" -gt 1024 ]; then
    print_success "Sufficient disk space: ${AVAILABLE_DISK}MB"
else
    print_warning "Low disk space: ${AVAILABLE_DISK}MB. Recommended: 1GB+"
fi

# Check 7: Network connectivity
print_header "7. Checking Network Connectivity"

# Check internet connectivity
if ping -c 1 8.8.8.8 &> /dev/null; then
    print_success "Internet connectivity confirmed"
else
    print_error "No internet connectivity detected"
fi

# Check Telegram API accessibility
if command -v curl &> /dev/null; then
    if curl -s --head --max-time 5 https://api.telegram.org | grep "200 OK" > /dev/null; then
        print_success "Telegram API is reachable"
    else
        print_warning "Cannot reach Telegram API (may be temporary)"
    fi
else
    print_info "curl not available, skipping Telegram API check"
fi

# Check 8: Docker build test
print_header "8. Testing Docker Build"
print_info "This may take a few minutes on first run..."

if docker build -t telegram-reminder-bot:test . > /dev/null 2>&1; then
    print_success "Docker build successful"

    # Get image size
    IMAGE_SIZE=$(docker images telegram-reminder-bot:test --format "{{.Size}}")
    print_info "Image size: $IMAGE_SIZE"
else
    print_error "Docker build failed. Check Dockerfile and dependencies."
fi

# Check 9: Python requirements validation
print_header "9. Validating Python Requirements"
if [ -f "requirements.txt" ]; then
    PACKAGE_COUNT=$(wc -l < requirements.txt)
    print_success "Found $PACKAGE_COUNT packages in requirements.txt"

    # Check for security vulnerabilities (if safety is installed)
    if command -v safety &> /dev/null; then
        if safety check -r requirements.txt > /dev/null 2>&1; then
            print_success "No known security vulnerabilities in dependencies"
        else
            print_warning "Potential security vulnerabilities found. Run 'safety check -r requirements.txt' for details"
        fi
    else
        print_info "Install 'safety' package to check for security vulnerabilities"
    fi
fi

# Summary
print_header "Pre-Deployment Check Summary"
echo ""
echo "Checks passed:  $CHECKS_PASSED"
echo "Checks failed:  $CHECKS_FAILED"
echo "Warnings:       $WARNINGS"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed! Ready for deployment.${NC}"
    echo ""
    echo "To deploy, run:"
    echo "  docker-compose up -d"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix the issues before deploying.${NC}"
    exit 1
fi

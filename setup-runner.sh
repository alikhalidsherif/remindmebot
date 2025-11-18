#!/bin/bash

# GitHub Actions Self-Hosted Runner Setup Script
# This script automates the installation and configuration of a GitHub Actions runner

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "  ℹ $1"
}

# Welcome message
print_header "GitHub Actions Runner Setup"
echo "This script will help you set up a self-hosted GitHub Actions runner"
echo "for automated deployment of your Telegram Reminder Bot."
echo ""

# Check if running on a supported OS
OS=$(uname -s)
ARCH=$(uname -m)

print_info "Detected OS: $OS"
print_info "Detected Architecture: $ARCH"
echo ""

if [[ "$OS" != "Linux" && "$OS" != "Darwin" ]]; then
    print_error "This script only supports Linux and macOS"
    exit 1
fi

# Check prerequisites
print_header "Step 1: Checking Prerequisites"

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker is installed: $DOCKER_VERSION"

    if docker info &> /dev/null; then
        print_success "Docker daemon is running"
    else
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
else
    print_error "Docker is not installed. Please install Docker first."
    print_info "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if user is in docker group (Linux only)
if [[ "$OS" == "Linux" ]]; then
    if groups | grep -q docker; then
        print_success "User is in docker group"
    else
        print_warning "User is not in docker group"
        print_info "Adding user to docker group..."
        sudo usermod -aG docker $USER
        print_success "Added to docker group. You may need to log out and back in."
    fi
fi

# Check curl
if command -v curl &> /dev/null; then
    print_success "curl is installed"
else
    print_error "curl is not installed. Please install curl first."
    exit 1
fi

# Get repository information
print_header "Step 2: Repository Information"
echo "We need some information about your GitHub repository."
echo ""

read -p "Enter your GitHub username: " GITHUB_USER
read -p "Enter your repository name [remindmebot]: " REPO_NAME
REPO_NAME=${REPO_NAME:-remindmebot}

REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME"

print_info "Repository: $REPO_URL"
echo ""

# Get runner token
print_header "Step 3: Runner Token"
echo "To get your runner token:"
echo "1. Go to: $REPO_URL/settings/actions/runners"
echo "2. Click 'New self-hosted runner'"
echo "3. Copy the token from the configuration command"
echo ""
read -p "Enter your runner token: " RUNNER_TOKEN

if [[ -z "$RUNNER_TOKEN" ]]; then
    print_error "Runner token cannot be empty"
    exit 1
fi

# Determine runner version and download URL
print_header "Step 4: Downloading Runner"

RUNNER_VERSION="2.311.0"

if [[ "$OS" == "Linux" ]]; then
    if [[ "$ARCH" == "x86_64" ]]; then
        RUNNER_FILE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
    elif [[ "$ARCH" == "aarch64" ]]; then
        RUNNER_FILE="actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
    else
        print_error "Unsupported architecture: $ARCH"
        exit 1
    fi
elif [[ "$OS" == "Darwin" ]]; then
    if [[ "$ARCH" == "x86_64" ]]; then
        RUNNER_FILE="actions-runner-osx-x64-${RUNNER_VERSION}.tar.gz"
    elif [[ "$ARCH" == "arm64" ]]; then
        RUNNER_FILE="actions-runner-osx-arm64-${RUNNER_VERSION}.tar.gz"
    else
        print_error "Unsupported architecture: $ARCH"
        exit 1
    fi
fi

DOWNLOAD_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILE}"

# Create runner directory
RUNNER_DIR="$HOME/actions-runner"
if [ -d "$RUNNER_DIR" ]; then
    print_warning "Runner directory already exists: $RUNNER_DIR"
    read -p "Remove existing directory? (y/n): " REMOVE_DIR
    if [[ "$REMOVE_DIR" == "y" ]]; then
        rm -rf "$RUNNER_DIR"
        print_success "Removed existing directory"
    else
        print_error "Cannot continue with existing directory"
        exit 1
    fi
fi

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

print_info "Downloading runner from: $DOWNLOAD_URL"
curl -o "$RUNNER_FILE" -L "$DOWNLOAD_URL"
print_success "Runner downloaded"

# Extract runner
print_info "Extracting runner..."
tar xzf "$RUNNER_FILE"
rm "$RUNNER_FILE"
print_success "Runner extracted"

# Configure runner
print_header "Step 5: Configuring Runner"

RUNNER_NAME="home-server-runner"
read -p "Enter runner name [$RUNNER_NAME]: " CUSTOM_NAME
RUNNER_NAME=${CUSTOM_NAME:-$RUNNER_NAME}

print_info "Configuring runner..."
./config.sh \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "$RUNNER_NAME" \
    --work "_work" \
    --unattended

print_success "Runner configured"

# Install as service
print_header "Step 6: Installing Runner as Service"

if [[ "$OS" == "Linux" ]]; then
    print_info "Installing systemd service..."
    sudo ./svc.sh install
    sudo ./svc.sh start
    print_success "Runner service installed and started"

    print_info "Checking service status..."
    sudo ./svc.sh status
elif [[ "$OS" == "Darwin" ]]; then
    print_info "Installing launchd service..."
    ./svc.sh install
    ./svc.sh start
    print_success "Runner service installed and started"

    print_info "Checking service status..."
    ./svc.sh status
fi

# Create helper script
print_header "Step 7: Creating Helper Scripts"

cat > "$HOME/runner-status.sh" << 'EOF'
#!/bin/bash
cd ~/actions-runner
./svc.sh status
echo ""
echo "Runner logs (last 50 lines):"
if [[ "$(uname -s)" == "Linux" ]]; then
    sudo journalctl -u actions.runner.* -n 50
else
    tail -n 50 ~/actions-runner/_diag/*.log 2>/dev/null | tail -n 50
fi
EOF

chmod +x "$HOME/runner-status.sh"
print_success "Created ~/runner-status.sh"

cat > "$HOME/runner-restart.sh" << 'EOF'
#!/bin/bash
cd ~/actions-runner
if [[ "$(uname -s)" == "Linux" ]]; then
    sudo ./svc.sh stop
    sudo ./svc.sh start
    sudo ./svc.sh status
else
    ./svc.sh stop
    ./svc.sh start
    ./svc.sh status
fi
EOF

chmod +x "$HOME/runner-restart.sh"
print_success "Created ~/runner-restart.sh"

# Final summary
print_header "Setup Complete!"

echo -e "${GREEN}✓ GitHub Actions Runner is installed and running${NC}"
echo ""
echo "Repository:    $REPO_URL"
echo "Runner Name:   $RUNNER_NAME"
echo "Runner Dir:    $RUNNER_DIR"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "1. Verify runner status: $REPO_URL/settings/actions/runners"
echo "2. The runner should show as 'Idle' (green)"
echo ""
echo -e "${YELLOW}Helper Commands:${NC}"
echo "  Check status:    ~/runner-status.sh"
echo "  Restart runner:  ~/runner-restart.sh"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Add TELEGRAM_BOT_TOKEN to GitHub Secrets"
echo "   Go to: $REPO_URL/settings/secrets/actions"
echo ""
echo "2. Test deployment:"
echo "   - Push to main branch, or"
echo "   - Use 'Run workflow' button in Actions tab"
echo ""
echo "3. Read the deployment guide:"
echo "   cat GITHUB_SECRETS_SETUP.md"
echo ""

if [[ "$OS" == "Linux" ]] && ! groups | grep -q docker; then
    print_warning "Docker group membership may require logout/login to take effect"
    print_info "Run: newgrp docker  (or log out and back in)"
fi

print_success "Setup completed successfully!"

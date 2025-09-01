#!/bin/bash

# Auto-update setup script for lrfs
# This script installs and configures the systemd timer for automatic updates

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LRFS_PATH="$SCRIPT_DIR"

print_status "Setting up auto-updates for lrfs..."
print_status "Installation path: $LRFS_PATH"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    LRFS_USER="root"
    LRFS_GROUP="root"
else
    LRFS_USER="$(whoami)"
    LRFS_GROUP="$(id -gn)"
    print_warning "Not running as root. Services will run as user: $LRFS_USER"
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "This directory is not a git repository. Auto-updates require git."
    exit 1
fi

# Make scripts executable
print_status "Making scripts executable..."
chmod +x "$LRFS_PATH/check_updates.sh"
chmod +x "$LRFS_PATH/build.sh"

# Create systemd service files with correct paths
print_status "Creating systemd service files..."

# Create service file
cat > /tmp/check_updates.service << EOF
[Unit]
Description=Check for updates on GitHub and run build script
After=network-online.target

[Service]
Type=oneshot
ExecStart=$LRFS_PATH/check_updates.sh
WorkingDirectory=$LRFS_PATH
User=$LRFS_USER
Group=$LRFS_GROUP

[Install]
WantedBy=multi-user.target
EOF

# Copy timer file (it doesn't need path substitution)
cp "$LRFS_PATH/setup/etc_systemd_system/check_updates.timer" /tmp/

# Install systemd files
print_status "Installing systemd files..."
if [[ $EUID -eq 0 ]]; then
    # Running as root
    cp /tmp/check_updates.service /etc/systemd/system/
    cp /tmp/check_updates.timer /etc/systemd/system/
else
    # Not root, need sudo
    sudo cp /tmp/check_updates.service /etc/systemd/system/
    sudo cp /tmp/check_updates.timer /etc/systemd/system/
fi

# Clean up temp files
rm /tmp/check_updates.service /tmp/check_updates.timer

# Reload systemd and enable services
print_status "Reloading systemd daemon..."
if [[ $EUID -eq 0 ]]; then
    systemctl daemon-reload
    systemctl enable check_updates.timer
    systemctl start check_updates.timer
else
    sudo systemctl daemon-reload
    sudo systemctl enable check_updates.timer
    sudo systemctl start check_updates.timer
fi

print_status "Checking timer status..."
if [[ $EUID -eq 0 ]]; then
    systemctl status check_updates.timer --no-pager
else
    sudo systemctl status check_updates.timer --no-pager
fi

print_status "Auto-update setup completed successfully!"
print_status "The system will now check for updates every 24 hours."
print_status "Logs will be written to: $LRFS_PATH/update.log"
echo
print_status "Useful commands:"
echo "  - Check timer status: sudo systemctl status check_updates.timer"
echo "  - View timer schedule: sudo systemctl list-timers check_updates.timer"
echo "  - Run update check manually: sudo systemctl start check_updates.service"
echo "  - View update logs: tail -f $LRFS_PATH/update.log"
echo "  - Disable auto-updates: sudo systemctl disable check_updates.timer"
#!/bin/bash

# install_chrome.sh - Install Google Chrome with sudo -S

set -e  # Exit on error

PASSWORD="lostriver"

echo "Starting Google Chrome installation..."

# Update package list
echo "Updating package list..."
echo "$PASSWORD" | sudo -S apt-get update

# Install dependencies
echo "Installing dependencies..."
echo "$PASSWORD" | sudo -S apt-get install -y wget apt-transport-https

# Download Google Chrome .deb package
echo "Downloading Google Chrome..."
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/google-chrome-stable_current_amd64.deb

# Install Chrome
echo "Installing Google Chrome..."
echo "$PASSWORD" | sudo -S apt-get install -y /tmp/google-chrome-stable_current_amd64.deb

# Fix any dependency issues
echo "$PASSWORD" | sudo -S apt-get install -f -y

# Clean up
echo "Cleaning up..."
rm /tmp/google-chrome-stable_current_amd64.deb

# Verify installation
if command -v google-chrome &> /dev/null; then
    echo "✓ Google Chrome installed successfully!"
    google-chrome --version
else
    echo "✗ Installation failed"
    exit 1
fi

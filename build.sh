#!/bin/bash

# Read password from stdin
read -r PASSWORD

echo "Updating lrfs code..."
git stash
git pull

echo "Installing Python dependencies..."
# Activate virtual environment and install dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo "stopping lrfs..."
echo "$PASSWORD" | sudo -S systemctl stop uwsgi-lrfs
echo "$PASSWORD" | sudo -S systemctl stop cloudflared
echo "reloading daemons..."
echo "$PASSWORD" | sudo -S systemctl daemon-reload
echo "starting up lrfs..."
echo "$PASSWORD" | sudo -S systemctl start uwsgi-lrfs
echo "$PASSWORD" | sudo -S systemctl start cloudflared
echo "lrfs is now up and running"

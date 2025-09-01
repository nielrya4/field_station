echo "Updating lrfs code..."
git pull

echo "Installing Python dependencies..."
# Activate virtual environment and install dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo "stopping lrfs..."
sudo systemctl stop uwsgi-lrfs
sudo systemctl stop cloudflared
echo "reloading daemons..."
sudo systemctl daemon-reload
echo "starting up lrfs..."
sudo systemctl start uwsgi-lrfs
sudo systemctl start cloudflared
echo "lrfs is now up and running"

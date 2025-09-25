from app import app
from flask_cloudflared import run_with_cloudflared

run_with_cloudflared(app)

if __name__ == "__main__":
    with app.app_context():
        app.run()

from flask import Flask, render_template_string, session, request
from flask_socketio import SocketIO, emit
from pages import borah_cam, contact, home, visit, weather, gallery, facilities, seismic
import pty
import os
import select
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

home.register(app)
contact.register(app)
borah_cam.register(app)
visit.register(app)
weather.register(app)
gallery.register(app)
facilities.register(app)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)

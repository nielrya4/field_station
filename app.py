from flask import Flask
from pages import borah_cam, contact, home, visit, weather, gallery, facilities, seismic

app = Flask(__name__)

home.register(app)
contact.register(app)
borah_cam.register(app)
visit.register(app)
weather.register(app)
gallery.register(app)
facilities.register(app)
seismic.register(app)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)

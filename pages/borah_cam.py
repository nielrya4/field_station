from flask import render_template, Response
import cv2
import time


def register(app):
    @app.route('/borah-cam')
    def borah_cam():
        return render_template("borah_cam/borah_cam.html")

    @app.route('/borah-cam/video-feed')
    def video_feed():
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


def generate_frames():
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    frame_count = 0
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            frame_count += 1
            if frame_count % 2 != 0:
                continue
            frame = cv2.resize(frame, (640, 480))
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            time.sleep(0.15)

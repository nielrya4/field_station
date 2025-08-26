from flask import render_template, Response
import cv2
import time
import threading
from io import BytesIO

# Global camera instance and thread management
camera = None
camera_lock = threading.Lock()
current_frame = None
frame_lock = threading.Lock()
camera_thread = None
camera_active = False

def initialize_camera():
    """Initialize camera with proper error handling"""
    global camera
    try:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("Warning: Camera not found, using placeholder")
            camera = None
            return False
        
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return True
    except Exception as e:
        print(f"Camera initialization error: {e}")
        camera = None
        return False

def camera_capture_loop():
    """Main camera capture loop - runs in background thread"""
    global camera, current_frame, camera_active
    
    frame_count = 0
    
    while camera_active:
        if camera is None:
            time.sleep(1)
            continue
            
        try:
            with camera_lock:
                if camera is not None:
                    success, frame = camera.read()
                else:
                    success = False
                    
            if success:
                frame_count += 1
                if frame_count % 2 == 0:  # Skip every other frame
                    frame = cv2.resize(frame, (640, 480))
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    
                    if ret:
                        with frame_lock:
                            current_frame = buffer.tobytes()
            else:
                # Camera read failed, try to reinitialize
                print("Camera read failed, attempting to reconnect...")
                with camera_lock:
                    if camera is not None:
                        camera.release()
                    initialize_camera()
                
            time.sleep(0.1)  # 10 FPS
            
        except Exception as e:
            print(f"Camera capture error: {e}")
            time.sleep(1)

def get_placeholder_frame():
    """Generate a placeholder frame when camera is not available"""
    import numpy as np
    
    # Create a simple placeholder image
    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
    placeholder.fill(50)  # Dark gray background
    
    # Add text (if opencv has font support)
    try:
        cv2.putText(placeholder, 'Camera Unavailable', (180, 220), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(placeholder, 'Check camera connection', (160, 260), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
    except:
        pass
    
    ret, buffer = cv2.imencode('.jpg', placeholder)
    return buffer.tobytes()

def generate_frames():
    """Generate frames for the video stream"""
    global current_frame
    
    while True:
        with frame_lock:
            if current_frame is not None:
                frame_data = current_frame
            else:
                frame_data = get_placeholder_frame()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n\r\n')
        time.sleep(0.1)  # Control stream rate

def register(app):
    global camera_thread, camera_active
    
    @app.route('/borah-cam')
    def borah_cam():
        return render_template("borah_cam/borah_cam.html")

    @app.route('/borah-cam/video-feed')
    def video_feed():
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    
    # Initialize camera and start capture thread
    camera_active = True
    initialize_camera()
    camera_thread = threading.Thread(target=camera_capture_loop, daemon=True)
    camera_thread.start()
    print("Borah Cam: Camera thread started")

from flask import render_template, Response, request
import cv2
import time
import threading
from io import BytesIO
import signal
import os

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
    print("=== INITIALIZING CAMERA ===")
    try:
        # Check if camera is already in use
        import subprocess
        result = subprocess.run(['lsof', '/dev/video0'], capture_output=True, text=True)
        if result.stdout:
            print(f"WARNING: Camera may be in use: {result.stdout.strip()}")
        
        print("Opening camera with V4L2 backend...")
        camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not camera.isOpened():
            print("ERROR: Camera failed to open")
            camera = None
            return False
        
        print("Camera opened, setting properties...")
        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        camera.set(cv2.CAP_PROP_FPS, 30)
        
        # Test reading a frame
        print("Testing frame capture...")
        ret, test_frame = camera.read()
        if ret:
            print(f"SUCCESS: Camera initialized and test frame captured: {test_frame.shape}")
            return True
        else:
            print("ERROR: Camera opened but cannot read frames")
            camera.release()
            camera = None
            return False
            
    except Exception as e:
        print(f"Camera initialization error: {e}")
        import traceback
        traceback.print_exc()
        if camera:
            camera.release()
        camera = None
        return False

def camera_capture_loop():
    """Main camera capture loop - runs in background thread"""
    global camera, current_frame, camera_active
    
    frame_count = 0
    print(f"Camera thread starting in process {os.getpid()}")
    
    while camera_active:
        if camera is None:
            print("Camera is None, attempting to initialize...")
            initialize_camera()
            if camera is None:
                time.sleep(2)
                continue
            
        try:
            with camera_lock:
                if camera is not None:
                    success, frame = camera.read()
                else:
                    success = False
                    
            if success:
                frame_count += 1
                # Keep original resolution for high quality, increase JPEG quality
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                if ret:
                    with frame_lock:
                        current_frame = buffer.tobytes()
                    if frame_count % 30 == 0:  # Log every 30 frames
                        print(f"Camera thread PID {os.getpid()}: {frame_count} frames captured, current_frame size: {len(current_frame) if current_frame else 0}")
                else:
                    print(f"Failed to encode frame {frame_count}")
            else:
                # Camera read failed, try to reinitialize
                print("Camera read failed, attempting to reconnect...")
                with camera_lock:
                    if camera is not None:
                        camera.release()
                        camera = None
                time.sleep(1)
                
            time.sleep(0.033)  # 30 FPS capture rate
            
        except Exception as e:
            print(f"Camera capture error: {e}")
            with camera_lock:
                if camera is not None:
                    camera.release()
                    camera = None
            time.sleep(1)

def get_placeholder_frame():
    """Generate a placeholder frame when camera is not available"""
    import numpy as np
    
    # Create a simple placeholder image at 1080p resolution
    placeholder = np.zeros((1080, 1920, 3), dtype=np.uint8)
    placeholder.fill(50)  # Dark gray background
    
    # Add text (if opencv has font support) - scaled for 1080p
    try:
        cv2.putText(placeholder, 'Camera Unavailable', (660, 500), 
                   cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 4)
        cv2.putText(placeholder, 'Check camera connection', (640, 580), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (200, 200, 200), 3)
    except:
        pass
    
    ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buffer.tobytes()

def generate_frames():
    """Generate frames for the video stream - serves shared frames to multiple clients"""
    frame_count = 0
    try:
        while True:
            frame_count += 1
            with frame_lock:
                if current_frame is not None:
                    frame_data = current_frame
                    if frame_count % 30 == 0:  # Log every 30 frames
                        print(f"Stream serving real frame {frame_count}")
                else:
                    frame_data = get_placeholder_frame()
                    if frame_count % 30 == 0:  # Log every 30 frames
                        print(f"Stream serving placeholder frame {frame_count} - current_frame is None")
            
            frame_bytes = (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n\r\n')
            yield frame_bytes
            time.sleep(0.033)  # 30 FPS
            
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"Client disconnected: {e}")
    except GeneratorExit:
        print("Video stream generator closed by client")
    except Exception as e:
        print(f"Frame generation error: {e}")

def ensure_camera_started():
    """Ensure camera thread is started in this process"""
    global camera_thread, camera_active, current_frame
    if camera_thread is None:
        print(f"Starting camera thread in process {os.getpid()}")
        camera_active = True
        initialize_camera()
        camera_thread = threading.Thread(target=camera_capture_loop, daemon=True)
        camera_thread.start()
        print("Borah Cam: Shared camera thread started for multiple viewers")
        
        # Wait a moment for the camera thread to capture the first frame
        for i in range(10):  # Wait up to 1 second
            time.sleep(0.1)
            with frame_lock:
                if current_frame is not None:
                    print("Camera thread has captured first frame")
                    break

def register(app):
    global camera_thread, camera_active
    
    @app.route('/borah-cam')
    def borah_cam():
        ensure_camera_started()
        return render_template("borah_cam/borah_cam.html")

    @app.route('/borah-cam/video-feed')
    def video_feed():
        ensure_camera_started()
        try:
            response = Response(generate_frames(), 
                              mimetype='multipart/x-mixed-replace; boundary=frame',
                              headers={'Cache-Control': 'no-cache, no-store, must-revalidate',
                                     'Pragma': 'no-cache',
                                     'Expires': '0'})
            return response
        except Exception as e:
            print(f"Video feed error: {e}")
            # Return a single frame as fallback
            placeholder_frame = get_placeholder_frame()
            return Response(placeholder_frame, mimetype='image/jpeg')

    @app.route('/borah-cam/test-frame')
    def test_frame():
        """Return current shared frame for testing"""
        ensure_camera_started()
        try:
            print(f"TEST endpoint called in process {os.getpid()}")
            with frame_lock:
                if current_frame is not None:
                    frame_data = current_frame
                    print(f"TEST: Serving real frame (size: {len(frame_data)} bytes)")
                else:
                    frame_data = get_placeholder_frame()
                    print(f"TEST: Serving placeholder - current_frame is None")
            
            return Response(frame_data, mimetype='image/jpeg',
                          headers={'Cache-Control': 'no-cache'})
        except Exception as e:
            print(f"Test frame error: {e}")
            return Response(get_placeholder_frame(), mimetype='image/jpeg')

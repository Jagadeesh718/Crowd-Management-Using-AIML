"""
Crowd Ease - Main Application Entry Point
AI-powered crowd monitoring with real-time density detection and alerts
"""

import time
import base64
import threading
import cv2
from datetime import datetime
from flask import Flask
from flask_socketio import SocketIO

# Local modules
from config import (
    FRONTEND_DIR, SECRET_KEY, 
    FRAME_RATE, MAX_HISTORY_LENGTH
)
from detector import detector
from camera import camera_manager
from alerts import alert_manager
from chatbot import ChatBot
from routes import register_routes
from sockets import register_socket_events
from face_recognition import face_recognizer
from prediction import crowd_predictor
from reports import reports_generator


# ===================================
# Flask App Initialization
# ===================================
app = Flask(__name__, 
            template_folder=FRONTEND_DIR,
            static_folder=FRONTEND_DIR)
app.config['SECRET_KEY'] = SECRET_KEY

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# ===================================
# Camera Data State
# ===================================
camera_data = {
    'cam1': {'name': 'Camera 1 - Main Entrance', 'headcount': 0, 'density': 0, 'status': 'online', 'history': []},
    'cam2': {'name': 'Camera 2 - Stage Area', 'headcount': 0, 'density': 0, 'status': 'offline', 'history': []},
    'cam3': {'name': 'Camera 3 - Food Court', 'headcount': 0, 'density': 0, 'status': 'offline', 'history': []},
    'cam4': {'name': 'Camera 4 - Exit Gate', 'headcount': 0, 'density': 0, 'status': 'offline', 'history': []},
}

camera_lock = threading.Lock()


# ===================================
# Helper Functions
# ===================================
def get_camera_data():
    """Get current camera data (thread-safe copy)."""
    try:
        # Try to acquire lock with timeout to avoid deadlock
        if camera_lock.acquire(timeout=0.5):
            try:
                return camera_data.copy()
            finally:
                camera_lock.release()
        else:
            # If can't get lock, return current data without copy
            return dict(camera_data)
    except:
        return dict(camera_data)


def get_alerts():
    """Get current alerts list."""
    return alert_manager.get_alerts()


# ===================================
# Initialize Components
# ===================================
# Create chatbot with data access and predictor
chatbot = ChatBot(get_camera_data, get_alerts, crowd_predictor)

# Register routes and socket events
register_routes(app, get_camera_data, get_alerts, camera_lock, face_recognizer, reports_generator)
register_socket_events(socketio, camera_data, alert_manager, chatbot, camera_lock, face_recognizer)


# ===================================
# Shared State for Multi-threaded Processing
# ===================================
ai_results = {
    'headcount': 0,
    'density': 0,
    'matches': [],
    'trend': {'direction': 'stable'},
    'predictions': [],
    'detections': []  # Store detection box coordinates only
}
ai_results_lock = threading.Lock()
latest_raw_frame = None
frame_lock = threading.Lock()


# ===================================
# Background Processing Tasks
# ===================================
def video_streaming_loop():
    """
    FAST video streaming loop - draws detection boxes from cached coordinates.
    No heavy processing - just draws rectangles.
    """
    global latest_raw_frame
    
    while True:
        try:
            if camera_manager.start_camera():
                frame = camera_manager.get_frame()
                
                if frame is not None:
                    # Store raw frame for AI processing thread
                    with frame_lock:
                        latest_raw_frame = frame
                    
                    # Get latest AI results (non-blocking)
                    with ai_results_lock:
                        headcount = ai_results['headcount']
                        density = ai_results['density']
                        trend = ai_results['trend']
                        predictions = ai_results['predictions']
                        detections = ai_results['detections'].copy()
                    
                    # Draw detection boxes (very fast - just rectangles)
                    for det in detections:
                        x, y, w, h = det['x'], det['y'], det['w'], det['h']
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (52, 199, 89), 2)
                        if det.get('label'):
                            cv2.putText(frame, det['label'], (x, y-10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (52, 199, 89), 2)
                    
                    # Draw info overlay
                    cv2.rectangle(frame, (5, 5), (180, 55), (255, 255, 255), -1)
                    cv2.rectangle(frame, (5, 5), (180, 55), (200, 200, 200), 1)
                    
                    color = (52, 199, 89) if headcount < 3 else (0, 149, 255) if headcount < 5 else (48, 59, 255)
                    cv2.putText(frame, f'People: {headcount}', (12, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color[::-1], 2)
                    cv2.putText(frame, f'Density: {density}%', (12, 48),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
                    
                    # Fast JPEG encode
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    frame_data = base64.b64encode(buffer).decode('utf-8')
                    
                    # Emit frame
                    socketio.emit('camera_frame', {
                        'camera': 'cam1',
                        'frame': frame_data,
                        'headcount': headcount,
                        'density': density,
                        'trend': trend,
                        'prediction': predictions[1] if len(predictions) > 1 else None
                    })
            
            # ~30 FPS streaming
            time.sleep(0.033)
            
        except Exception as e:
            print(f"Video streaming error: {e}")
            time.sleep(0.1)


def ai_processing_loop():
    """
    SLOW AI processing loop - extracts detection coordinates only.
    Doesn't copy full frames - just shares box positions.
    """
    global camera_data
    
    while True:
        try:
            # Get latest frame (no copy needed - just reference)
            frame = latest_raw_frame
            
            if frame is not None:
                # Heavy AI processing (runs at ~2-3 FPS, doesn't block video)
                headcount, detections = detector.detect_people(frame.copy())
                
                # Log to reports
                reports_generator.log_headcount('cam1', headcount, min(100, headcount * 20))
                
                # Add observation to predictor
                crowd_predictor.add_observation(headcount)
                
                # Search for missing persons
                matches = face_recognizer.search_in_frame(
                    frame, 
                    camera_data['cam1']['name']
                )
                
                # Send alerts for missing person matches
                for match in matches:
                    socketio.emit('missing_person_found', {
                        'person_name': match['name'],
                        'camera': match['camera'],
                        'confidence': match['confidence'],
                        'time': match['time'],
                        'method': match.get('method', 'Histogram')
                    })
                
                # Get prediction analytics
                analytics = crowd_predictor.get_analytics()
                trend = analytics['trend']
                predictions = analytics['predictions']
                
                # Update shared AI results (only coordinates, not full frame)
                with ai_results_lock:
                    ai_results['headcount'] = headcount
                    ai_results['density'] = min(100, headcount * 20)
                    ai_results['matches'] = matches
                    ai_results['trend'] = trend
                    ai_results['predictions'] = predictions
                    ai_results['detections'] = detections  # Just coordinates
                
                # Update camera data
                with camera_lock:
                    camera_data['cam1']['headcount'] = headcount
                    camera_data['cam1']['density'] = min(100, headcount * 20)
                    camera_data['cam1']['status'] = 'online'
                    camera_data['cam1']['trend'] = trend['direction']
                    camera_data['cam1']['prediction'] = predictions[1] if len(predictions) > 1 else None
                    
                    # Add to history
                    current_time = time.time()
                    if not hasattr(ai_processing_loop, 'last_history_time') or current_time - ai_processing_loop.last_history_time > 1:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        camera_data['cam1']['history'].append({
                            'time': timestamp,
                            'count': headcount,
                            'density': camera_data['cam1']['density']
                        })
                        ai_processing_loop.last_history_time = current_time
                    
                    # Trim history
                    if len(camera_data['cam1']['history']) > MAX_HISTORY_LENGTH:
                        camera_data['cam1']['history'] = camera_data['cam1']['history'][-MAX_HISTORY_LENGTH:]
                
                # Emit camera data update
                socketio.emit('camera_update', camera_data)
            
            # AI runs at ~3 FPS (every 300ms) - plenty for detection
            time.sleep(0.3)
            
        except Exception as e:
            print(f"AI processing error: {e}")
            time.sleep(0.5)


def simulate_other_cameras():
    """Simulate data for cameras 2-4 (offline/demo mode)."""
    global camera_data
    
    while True:
        try:
            with camera_lock:
                for cam_id in ['cam2', 'cam3', 'cam4']:
                    camera_data[cam_id]['headcount'] = 0
                    camera_data[cam_id]['density'] = 0
                    camera_data[cam_id]['status'] = 'offline'
            
            time.sleep(5)
            
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)


# ===================================
# Application Entry Point
# ===================================
if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🎯 Crowd Ease - Crowd Management System")
    print("=" * 50)
    
    # Start background threads
    # Video thread - high priority, fast
    video_thread = threading.Thread(target=video_streaming_loop, daemon=True)
    video_thread.start()
    
    # AI thread - lower priority, slower but thorough
    ai_thread = threading.Thread(target=ai_processing_loop, daemon=True)
    ai_thread.start()
    
    # Simulation thread
    sim_thread = threading.Thread(target=simulate_other_cameras, daemon=True)
    sim_thread.start()
    
    print("✅ System ready - Dual-thread mode (smooth video + AI)")
    print("🌐 Open http://localhost:5000")
    print("=" * 50 + "\n")
    
    # Start Flask server
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

"""
Crowd Ease - Main Application Entry Point
AI-powered crowd monitoring with real-time density detection and alerts.
"""

import base64
import threading
import time
from datetime import datetime
from queue import Empty, Full, Queue

import cv2
from flask import Flask
from flask_socketio import SocketIO

from alerts import alert_manager
from api.routes import register_routes
from api.sockets import register_socket_events
from camera import camera_manager
from chatbot import ChatBot
from config import (
    AI_FRAME_QUEUE_SIZE,
    AI_LOOP_SLEEP,
    FRONTEND_DIR,
    MAX_HISTORY_LENGTH,
    SECRET_KEY,
    STREAM_LOOP_SLEEP,
)
from core.metrics import MetricsCollector
from detector import detector
from face_recognition import face_recognizer
from prediction import crowd_predictor
from reports import reports_generator
from venue_map import venue_map


app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


camera_data = {
    'cam1': {'name': 'Camera 1 - Main Entrance', 'headcount': 0, 'density': 0, 'status': 'online', 'history': []},
    'cam2': {'name': 'Camera 2 - Stage Area', 'headcount': 0, 'density': 0, 'status': 'simulated', 'history': []},
    'cam3': {'name': 'Camera 3 - Food Court', 'headcount': 0, 'density': 0, 'status': 'simulated', 'history': []},
    'cam4': {'name': 'Camera 4 - Exit Gate', 'headcount': 0, 'density': 0, 'status': 'simulated', 'history': []},
}
camera_lock = threading.Lock()

ai_results = {
    'headcount': 0,
    'density': 0,
    'matches': [],
    'trend': {'direction': 'stable'},
    'predictions': [],
    'detections': [],
}
ai_results_lock = threading.Lock()

ai_frame_queue = Queue(maxsize=AI_FRAME_QUEUE_SIZE)
metrics_collector = MetricsCollector()

# Emergency mode state
emergency_mode = {'active': False, 'activated_at': None}


def _camera_data_snapshot_unlocked():
    snapshot = {}
    for cam_id, cam in camera_data.items():
        cam_copy = dict(cam)
        if isinstance(cam_copy.get('history'), list):
            cam_copy['history'] = list(cam_copy['history'])
        snapshot[cam_id] = cam_copy
    return snapshot


def get_camera_data():
    """Get camera state as a thread-safe snapshot."""
    with camera_lock:
        return _camera_data_snapshot_unlocked()


def get_alerts():
    """Get current alerts list."""
    return alert_manager.get_alerts()


def get_metrics():
    """Get runtime pipeline metrics snapshot."""
    return metrics_collector.snapshot()


def get_venue_data():
    """Get venue map zone data."""
    return venue_map.get_zone_data()


def get_emergency_status():
    """Get emergency mode status."""
    return emergency_mode


chatbot = ChatBot(get_camera_data, get_alerts, crowd_predictor)

register_routes(
    app,
    get_camera_data,
    get_alerts,
    camera_lock,
    face_recognizer,
    reports_generator,
    get_metrics=get_metrics,
    get_venue_data=get_venue_data,
    get_emergency_status=get_emergency_status,
    emergency_mode=emergency_mode,
)
register_socket_events(socketio, camera_data, alert_manager, chatbot, camera_lock, face_recognizer)


def push_frame_for_ai(frame):
    """Push latest frame to AI queue with drop-oldest policy when full."""
    try:
        ai_frame_queue.put_nowait(frame.copy())
    except Full:
        try:
            ai_frame_queue.get_nowait()
            metrics_collector.mark_frame_dropped()
        except Empty:
            pass
        try:
            ai_frame_queue.put_nowait(frame.copy())
        except Full:
            metrics_collector.mark_frame_dropped()
    metrics_collector.set_queue_depth(ai_frame_queue.qsize())


def video_streaming_loop():
    """High-rate stream loop that overlays cached detections and emits frames."""
    while True:
        try:
            if not camera_manager.start_camera():
                time.sleep(0.1)
                continue

            frame = camera_manager.get_frame()
            if frame is None:
                time.sleep(STREAM_LOOP_SLEEP)
                continue

            metrics_collector.mark_stream_tick()
            push_frame_for_ai(frame)

            with ai_results_lock:
                headcount = ai_results['headcount']
                density = ai_results['density']
                trend = dict(ai_results['trend'])
                predictions = list(ai_results['predictions'])
                detections = list(ai_results['detections'])

            for det in detections:
                x, y, w, h = det['x'], det['y'], det['w'], det['h']
                conf = det.get('confidence', 0)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (52, 199, 89), 2)
                label = det.get('label', '')
                if conf > 0:
                    label = f'{label} {conf:.0%}'
                if label:
                    cv2.putText(
                        frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (52, 199, 89), 2,
                    )

            # Draw overlay HUD
            cv2.rectangle(frame, (5, 5), (240, 80), (255, 255, 255), -1)
            cv2.rectangle(frame, (5, 5), (240, 80), (200, 200, 200), 1)
            color = (52, 199, 89) if headcount < 3 else (0, 149, 255) if headcount < 5 else (48, 59, 255)
            cv2.putText(frame, f'People: {headcount}', (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color[::-1], 2)
            cv2.putText(frame, f'Density: {density}%', (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

            # Show detection method
            from detector import YOLO_AVAILABLE
            method_text = "YOLOv8" if YOLO_AVAILABLE else "HOG"
            cv2.putText(frame, f'Model: {method_text}', (12, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)

            metrics_snapshot = metrics_collector.snapshot()
            cv2.putText(
                frame,
                f"AI: {metrics_snapshot['ai_fps']:.1f} fps",
                (150, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1,
            )

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_data = base64.b64encode(buffer).decode('utf-8')

            socketio.emit(
                'camera_frame',
                {
                    'camera': 'cam1',
                    'frame': frame_data,
                    'headcount': headcount,
                    'density': density,
                    'trend': trend,
                    'prediction': predictions[1] if len(predictions) > 1 else None,
                },
            )

            time.sleep(STREAM_LOOP_SLEEP)
        except Exception as e:
            print(f"Video streaming error: {e}")
            time.sleep(0.1)


def ai_processing_loop():
    """AI loop consuming queued frames at bounded latency."""
    while True:
        try:
            try:
                frame = ai_frame_queue.get(timeout=1.0)
                metrics_collector.set_queue_depth(ai_frame_queue.qsize())
            except Empty:
                time.sleep(AI_LOOP_SLEEP)
                continue

            inference_start = time.perf_counter()
            headcount, detections = detector.detect_people(frame.copy())
            inference_ms = (time.perf_counter() - inference_start) * 1000
            metrics_collector.mark_ai_processed(inference_ms)

            density = min(100, headcount * 20)
            reports_generator.log_headcount('cam1', headcount, density)
            crowd_predictor.add_observation(headcount)

            with camera_lock:
                camera_name = camera_data['cam1']['name']

            matches = face_recognizer.search_in_frame(frame, camera_name)
            for match in matches:
                socketio.emit(
                    'missing_person_found',
                    {
                        'person_name': match['name'],
                        'camera': match['camera'],
                        'confidence': match['confidence'],
                        'time': match['time'],
                        'method': match.get('method', 'Histogram'),
                    },
                )

            analytics = crowd_predictor.get_analytics()
            trend = analytics['trend']
            predictions = analytics['predictions']

            with ai_results_lock:
                ai_results['headcount'] = headcount
                ai_results['density'] = density
                ai_results['matches'] = matches
                ai_results['trend'] = trend
                ai_results['predictions'] = predictions
                ai_results['detections'] = detections

            # Update venue map with real camera data
            venue_map.update_zone_from_camera('cam1', headcount, density, trend.get('direction', 'stable'))

            with camera_lock:
                camera_data['cam1']['headcount'] = headcount
                camera_data['cam1']['density'] = density
                camera_data['cam1']['status'] = 'online'
                camera_data['cam1']['trend'] = trend['direction']
                camera_data['cam1']['prediction'] = predictions[1] if len(predictions) > 1 else None

                now = time.time()
                last_history_time = getattr(ai_processing_loop, 'last_history_time', 0.0)
                if now - last_history_time > 1:
                    camera_data['cam1']['history'].append(
                        {'time': datetime.now().strftime('%H:%M:%S'), 'count': headcount, 'density': density}
                    )
                    ai_processing_loop.last_history_time = now

                if len(camera_data['cam1']['history']) > MAX_HISTORY_LENGTH:
                    camera_data['cam1']['history'] = camera_data['cam1']['history'][-MAX_HISTORY_LENGTH:]

                camera_snapshot = _camera_data_snapshot_unlocked()

            socketio.emit('camera_update', camera_snapshot)

            # Emit venue map update periodically
            socketio.emit('venue_update', venue_map.get_zone_data())

        except Exception as e:
            print(f"AI processing error: {e}")
            time.sleep(0.5)


def simulate_other_cameras():
    """Simulate realistic data for cameras 2-4 in demo mode."""
    import random
    while True:
        try:
            with camera_lock:
                for cam_id in ['cam2', 'cam3', 'cam4']:
                    headcount, density = venue_map.get_simulated_headcount(cam_id)
                    camera_data[cam_id]['headcount'] = headcount
                    camera_data[cam_id]['density'] = density
                    camera_data[cam_id]['status'] = 'simulated'

                    # Determine trend from history
                    history = camera_data[cam_id]['history']
                    if len(history) >= 2:
                        prev = history[-1]['count']
                        if headcount > prev + 1:
                            camera_data[cam_id]['trend'] = 'increasing'
                        elif headcount < prev - 1:
                            camera_data[cam_id]['trend'] = 'decreasing'
                        else:
                            camera_data[cam_id]['trend'] = 'stable'

                    camera_data[cam_id]['history'].append({
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'count': headcount,
                        'density': density,
                    })
                    if len(camera_data[cam_id]['history']) > MAX_HISTORY_LENGTH:
                        camera_data[cam_id]['history'] = camera_data[cam_id]['history'][-MAX_HISTORY_LENGTH:]

                    # Update venue map
                    venue_map.update_zone_from_camera(
                        cam_id, headcount, density,
                        camera_data[cam_id].get('trend', 'stable')
                    )

            time.sleep(3)
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  Crowd Ease - AI Crowd Management System")
    print("  Powered by YOLOv8 + ARIMA + Face Recognition")
    print("=" * 60)

    threading.Thread(target=video_streaming_loop, daemon=True).start()
    threading.Thread(target=ai_processing_loop, daemon=True).start()
    threading.Thread(target=simulate_other_cameras, daemon=True).start()

    print("✅ System ready — queue-based AI pipeline enabled")
    print("🌐 Open http://localhost:5000")
    print("=" * 60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)

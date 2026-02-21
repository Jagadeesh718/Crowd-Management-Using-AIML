"""
Crowd Ease - Socket Events Module
WebSocket event handlers for real-time communication
"""

from flask_socketio import emit


def register_socket_events(socketio, camera_data, alerts_manager, chatbot, camera_lock, face_recognizer):
    """
    Register all WebSocket event handlers.
    
    Args:
        socketio: Flask-SocketIO instance
        camera_data: Dictionary of camera data
        alerts_manager: AlertManager instance
        chatbot: ChatBot instance
        camera_lock: Threading lock for camera data
        face_recognizer: FaceRecognizer instance
    """
    
    active_camera = 'cam1'
    
    @socketio.on('connect')
    def handle_connect():
        """Handle new client connection."""
        print('Client connected')
        emit('camera_update', camera_data)
        emit('alerts_update', alerts_manager.get_alerts())
        # Send current missing persons list
        emit('missing_persons_update', face_recognizer.get_all_missing_persons())
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        print('Client disconnected')
    
    @socketio.on('select_camera')
    def handle_camera_select(data):
        """Handle camera selection from client."""
        nonlocal active_camera
        camera_id = data.get('camera_id')
        
        if camera_id in camera_data:
            active_camera = camera_id
            emit('camera_selected', {
                'camera_id': camera_id,
                'data': camera_data[camera_id]
            })
    
    @socketio.on('chatbot_message')
    def handle_chatbot_message(data):
        """Handle chatbot message from client."""
        message = data.get('message', '')
        response = chatbot.process_message(message)
        emit('chatbot_response', {'message': response})
    
    @socketio.on('get_missing_persons')
    def handle_get_missing_persons():
        """Send current missing persons list."""
        emit('missing_persons_update', face_recognizer.get_all_missing_persons())

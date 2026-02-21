"""
Crowd Ease - Flask Routes Module
HTTP endpoints and static file serving
"""

import os
import base64
from datetime import datetime
from flask import render_template, jsonify, send_from_directory, request, Response
from config import FRONTEND_DIR


def register_routes(app, get_camera_data, get_alerts, camera_lock, face_recognizer, reports_generator):
    """
    Register all HTTP routes with the Flask app.
    
    Args:
        app: Flask application instance
        get_camera_data: Function to get camera data
        get_alerts: Function to get alerts
        camera_lock: Threading lock for camera data
        face_recognizer: FaceRecognizer instance for missing persons
        reports_generator: ReportsGenerator instance for analytics
    """
    
    @app.route('/')
    def index():
        """Serve the main dashboard page."""
        return render_template('index.html')
    
    @app.route('/static/css/<path:filename>')
    def serve_css(filename):
        """Serve CSS files from frontend folder."""
        return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)
    
    @app.route('/static/js/<path:filename>')
    def serve_js(filename):
        """Serve JavaScript files from frontend folder."""
        return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)
    
    @app.route('/static/<path:filename>')
    def serve_assets(filename):
        """Serve asset files (images, etc.) from frontend folder."""
        return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), filename)
    
    @app.route('/api/cameras')
    def api_cameras():
        """API endpoint to get all camera data."""
        with camera_lock:
            return jsonify(get_camera_data())
    
    @app.route('/api/alerts')
    def api_alerts():
        """API endpoint to get all alerts."""
        return jsonify(get_alerts())
    
    # ===================================
    # Missing Persons API
    # ===================================
    
    @app.route('/api/missing-persons', methods=['GET'])
    def get_missing_persons():
        """Get all registered missing persons."""
        return jsonify(face_recognizer.get_all_missing_persons())
    
    @app.route('/api/missing-persons', methods=['POST'])
    def add_missing_person():
        """Add a new missing person."""
        try:
            # Handle form data with file upload
            name = request.form.get('name', '').strip()
            photo = request.files.get('photo')
            
            if not name:
                return jsonify({'error': 'Name is required'}), 400
            
            if not photo:
                return jsonify({'error': 'Photo is required'}), 400
            
            # Read and encode the image as base64
            image_data = photo.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_data_url = f"data:{photo.content_type};base64,{image_base64}"
            
            result = face_recognizer.add_missing_person(name, image_data_url)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': f'{name} added to missing persons list',
                    'person': result
                })
            else:
                return jsonify({
                    'error': 'Failed to process image. Please ensure a clear face is visible.'
                }), 400
        except Exception as e:
            print(f"Error adding missing person: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/missing-persons/<int:person_id>', methods=['DELETE'])
    def remove_missing_person(person_id):
        """Remove a missing person from the database."""
        if face_recognizer.remove_missing_person(person_id):
            return jsonify({'success': True, 'message': 'Person removed'})
        else:
            return jsonify({'error': 'Person not found'}), 404
    
    # ===================================
    # Reports & Export API
    # ===================================
    
    @app.route('/api/reports/summary')
    def get_reports_summary():
        """Get analytics summary as JSON."""
        try:
            camera_data = get_camera_data()
            return jsonify(reports_generator.generate_summary_json(camera_data))
        except Exception as e:
            print(f"Error getting summary: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/reports/export/csv')
    def export_csv_report():
        """Export crowd analytics as CSV file."""
        try:
            camera_data = get_camera_data()
            csv_data = reports_generator.generate_csv_report(camera_data)
            
            filename = f"crowdease_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}',
                    'Content-Type': 'text/csv; charset=utf-8'
                }
            )
        except Exception as e:
            print(f"Error exporting CSV: {e}")
            return Response(f"Error: {e}", status=500)
    
    @app.route('/api/reports/export/json')
    def export_json_report():
        """Export crowd analytics as JSON file."""
        try:
            camera_data = get_camera_data()
            report = reports_generator.generate_summary_json(camera_data)
            report['export_time'] = datetime.now().isoformat()
            return jsonify(report)
        except Exception as e:
            print(f"Error exporting JSON: {e}")
            return jsonify({'error': str(e)}), 500

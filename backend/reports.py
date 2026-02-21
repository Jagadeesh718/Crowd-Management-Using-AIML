"""
Crowd Ease - Reports Module
Generates exportable reports in CSV and PDF formats
"""

import csv
import io
from datetime import datetime, timedelta
from collections import deque
import time


class ReportsGenerator:
    """Generates exportable crowd analytics reports."""
    
    def __init__(self, max_events=500):
        """
        Initialize the reports generator.
        
        Args:
            max_events: Maximum number of events to store
        """
        self.event_log = deque(maxlen=max_events)
        self.hourly_stats = {}
        self.daily_stats = {}
        self.start_time = datetime.now()
    
    def log_event(self, event_type, camera, data=None):
        """
        Log an event for reporting.
        
        Args:
            event_type: Type of event (detection, alert, missing_person, etc.)
            camera: Camera ID where event occurred
            data: Additional event data
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'time_formatted': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': event_type,
            'camera': camera,
            'data': data or {}
        }
        self.event_log.append(event)
        
        # Update hourly stats
        hour_key = datetime.now().strftime('%Y-%m-%d %H:00')
        if hour_key not in self.hourly_stats:
            self.hourly_stats[hour_key] = {
                'total_detections': 0,
                'peak_count': 0,
                'alerts': 0,
                'missing_person_matches': 0
            }
        
        stats = self.hourly_stats[hour_key]
        if event_type == 'detection':
            stats['total_detections'] += 1
            if data and data.get('headcount', 0) > stats['peak_count']:
                stats['peak_count'] = data['headcount']
        elif event_type == 'alert':
            stats['alerts'] += 1
        elif event_type == 'missing_person_match':
            stats['missing_person_matches'] += 1
    
    def log_headcount(self, camera, headcount, density):
        """Log a headcount reading."""
        self.log_event('detection', camera, {
            'headcount': headcount,
            'density': density
        })
    
    def log_alert(self, camera, severity, message):
        """Log an alert event."""
        self.log_event('alert', camera, {
            'severity': severity,
            'message': message
        })
    
    def log_missing_person_match(self, camera, person_name, confidence):
        """Log a missing person match."""
        self.log_event('missing_person_match', camera, {
            'person_name': person_name,
            'confidence': confidence
        })
    
    def get_summary(self):
        """Get a summary of the current session."""
        if not self.event_log:
            return {
                'session_duration': '0:00:00',
                'total_events': 0,
                'peak_headcount': 0,
                'total_alerts': 0,
                'missing_person_matches': 0
            }
        
        duration = datetime.now() - self.start_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        peak = 0
        alerts = 0
        matches = 0
        
        for event in self.event_log:
            if event['type'] == 'detection':
                hc = event['data'].get('headcount', 0)
                if hc > peak:
                    peak = hc
            elif event['type'] == 'alert':
                alerts += 1
            elif event['type'] == 'missing_person_match':
                matches += 1
        
        return {
            'session_start': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'session_duration': f'{hours}:{minutes:02d}:{seconds:02d}',
            'total_events': len(self.event_log),
            'peak_headcount': peak,
            'total_alerts': alerts,
            'missing_person_matches': matches
        }
    
    def generate_csv_report(self, camera_data, include_events=True):
        """
        Generate a CSV report of crowd analytics.
        
        Args:
            camera_data: Current camera data dict
            include_events: Whether to include event log
            
        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header section
        summary = self.get_summary()
        writer.writerow(['Crowd Ease - Analytics Report'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Session Start:', summary['session_start']])
        writer.writerow(['Session Duration:', summary['session_duration']])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['=== SESSION SUMMARY ==='])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Peak Headcount', summary['peak_headcount']])
        writer.writerow(['Total Alerts', summary['total_alerts']])
        writer.writerow(['Missing Person Matches', summary['missing_person_matches']])
        writer.writerow(['Total Events Logged', summary['total_events']])
        writer.writerow([])
        
        # Camera status section
        writer.writerow(['=== CAMERA STATUS ==='])
        writer.writerow(['Camera', 'Name', 'Status', 'Current Count', 'Density', 'Peak'])
        
        for cam_id, cam in camera_data.items():
            writer.writerow([
                cam_id,
                cam.get('name', cam_id),
                cam.get('status', 'unknown'),
                cam.get('headcount', 0),
                f"{cam.get('density', 0)}%",
                cam.get('peak', cam.get('headcount', 0))
            ])
        writer.writerow([])
        
        # Hourly stats section
        if self.hourly_stats:
            writer.writerow(['=== HOURLY STATISTICS ==='])
            writer.writerow(['Hour', 'Peak Count', 'Alerts', 'Missing Person Matches'])
            
            for hour, stats in sorted(self.hourly_stats.items()):
                writer.writerow([
                    hour,
                    stats['peak_count'],
                    stats['alerts'],
                    stats['missing_person_matches']
                ])
            writer.writerow([])
        
        # Event log section
        if include_events and self.event_log:
            writer.writerow(['=== EVENT LOG ==='])
            writer.writerow(['Timestamp', 'Type', 'Camera', 'Details'])
            
            # Get last 100 events
            recent_events = list(self.event_log)[-100:]
            for event in recent_events:
                details = ''
                if event['type'] == 'detection':
                    details = f"Headcount: {event['data'].get('headcount', 0)}, Density: {event['data'].get('density', 0)}%"
                elif event['type'] == 'alert':
                    details = f"{event['data'].get('severity', 'unknown')}: {event['data'].get('message', '')}"
                elif event['type'] == 'missing_person_match':
                    details = f"{event['data'].get('person_name', 'Unknown')} - {event['data'].get('confidence', 0)}% confidence"
                
                writer.writerow([
                    event['time_formatted'],
                    event['type'],
                    event['camera'],
                    details
                ])
        
        return output.getvalue()
    
    def generate_summary_json(self, camera_data):
        """
        Generate a JSON summary for API response.
        
        Args:
            camera_data: Current camera data dict
            
        Returns:
            Dictionary with summary data
        """
        summary = self.get_summary()
        
        cameras = []
        for cam_id, cam in camera_data.items():
            cameras.append({
                'id': cam_id,
                'name': cam.get('name', cam_id),
                'status': cam.get('status', 'unknown'),
                'headcount': cam.get('headcount', 0),
                'density': cam.get('density', 0)
            })
        
        hourly = []
        for hour, stats in sorted(self.hourly_stats.items()):
            hourly.append({
                'hour': hour,
                'peak_count': stats['peak_count'],
                'alerts': stats['alerts']
            })
        
        return {
            'summary': summary,
            'cameras': cameras,
            'hourly_stats': hourly,
            'recent_events': list(self.event_log)[-20:]
        }


# Singleton instance
reports_generator = ReportsGenerator()

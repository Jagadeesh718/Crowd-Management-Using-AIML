"""
Crowd Ease - Alert Management Module
Handles alert creation, storage, and notifications
"""

from datetime import datetime
from config import MAX_ALERTS


class AlertManager:
    """Manages crowd alerts and notifications."""
    
    def __init__(self):
        self.alerts_log = []
    
    def add_alert(self, camera_id, camera_name, headcount, severity='warning'):
        """
        Create and store a new alert.
        
        Args:
            camera_id: ID of the camera that triggered the alert
            camera_name: Display name of the camera
            headcount: Number of people detected
            severity: 'warning' or 'critical'
            
        Returns:
            dict: The created alert object
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if severity == 'critical':
            message = f"🚨 CRITICAL: {camera_name} - {headcount} people detected! Immediate action required."
        else:
            message = f"⚠️ WARNING: {camera_name} approaching capacity ({headcount} people)"
        
        alert = {
            'id': len(self.alerts_log) + 1,
            'timestamp': timestamp,
            'camera': camera_id,
            'camera_name': camera_name,
            'headcount': headcount,
            'severity': severity,
            'message': message
        }
        
        # Add to front of list (most recent first)
        self.alerts_log.insert(0, alert)
        
        # Trim to max size
        if len(self.alerts_log) > MAX_ALERTS:
            self.alerts_log = self.alerts_log[:MAX_ALERTS]
        
        return alert
    
    def get_alerts(self, limit=None):
        """
        Get stored alerts.
        
        Args:
            limit: Optional max number of alerts to return
            
        Returns:
            list: List of alert objects
        """
        if limit:
            return self.alerts_log[:limit]
        return self.alerts_log
    
    def clear_alerts(self):
        """Clear all stored alerts."""
        self.alerts_log = []
    
    def get_alert_count(self):
        """Get total number of alerts."""
        return len(self.alerts_log)


# Singleton instance
alert_manager = AlertManager()

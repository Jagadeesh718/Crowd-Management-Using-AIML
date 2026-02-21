"""
Crowd Ease - Chatbot Module
AI assistant for crowd management queries with prediction support
"""

from config import WARNING_THRESHOLD, CRITICAL_THRESHOLD


class ChatBot:
    """Handles chatbot interactions and responses."""
    
    def __init__(self, camera_data_getter, alerts_getter, predictor=None):
        """
        Initialize chatbot with data access functions.
        
        Args:
            camera_data_getter: Function that returns current camera data
            alerts_getter: Function that returns alerts list
            predictor: CrowdPredictor instance for predictions
        """
        self.get_camera_data = camera_data_getter
        self.get_alerts = alerts_getter
        self.predictor = predictor
    
    def process_message(self, message):
        """
        Process a user message and generate a response.
        
        Args:
            message: User's input message
            
        Returns:
            str: Bot's response message
        """
        message = message.lower().strip()
        
        if 'status' in message or 'how' in message:
            return self._get_status_response()
        
        elif 'predict' in message or 'forecast' in message or 'future' in message:
            return self._get_prediction_response()
        
        elif 'trend' in message:
            return self._get_trend_response()
        
        elif 'analytics' in message or 'stats' in message:
            return self._get_analytics_response()
        
        elif 'alert' in message:
            return self._get_alerts_response()
        
        elif 'report' in message or 'export' in message:
            return self._get_report_response()
        
        elif 'heatmap' in message or 'heat' in message:
            return self._get_heatmap_response()
        
        elif 'help' in message:
            return self._get_help_response()
        
        elif 'threshold' in message:
            return self._get_threshold_response()
        
        elif 'camera' in message:
            return self._get_camera_response(message)
        
        else:
            return "👋 Hi! I'm your crowd management assistant. Type 'help' to see what I can do."
    
    def _get_status_response(self):
        """Generate status response with all camera info and trend."""
        camera_data = self.get_camera_data()
        total = sum(cam['headcount'] for cam in camera_data.values())
        
        # Get trend info
        trend_info = ""
        if self.predictor:
            trend = self.predictor.get_trend()
            trend_icon = "📈" if trend['direction'] == 'increasing' else "📉" if trend['direction'] == 'decreasing' else "➡️"
            trend_info = f"\n\nTrend: {trend_icon} {trend['direction'].title()}"
        
        response = f"📊 Current Status\n\nTotal people: {total}{trend_info}\n\n"
        
        for cam_id, cam in camera_data.items():
            if cam['headcount'] < WARNING_THRESHOLD:
                icon = "🟢"
            elif cam['headcount'] < CRITICAL_THRESHOLD:
                icon = "🟡"
            else:
                icon = "🔴"
            response += f"{icon} {cam['name']}: {cam['headcount']} people\n"
        
        return response
    
    def _get_prediction_response(self):
        """Generate crowd prediction response using ARIMA model."""
        if not self.predictor:
            return "⚠️ Prediction system not available."
        
        predictions = self.predictor.get_predictions()
        
        if not predictions:
            return "📊 Not enough data for predictions yet. Keep monitoring!"
        
        # Check prediction method
        method = predictions[0].get('method', 'Ensemble')
        method_info = "🔬 Using ARIMA time-series model" if method == 'ARIMA' else "📈 Using ensemble prediction"
        
        response = f"🔮 Crowd Predictions\n{method_info}\n\n"
        
        for pred in predictions:
            mins = pred['minutes_ahead']
            count = pred['predicted_count']
            conf = pred['confidence']
            
            if count < WARNING_THRESHOLD:
                icon = "🟢"
            elif count < CRITICAL_THRESHOLD:
                icon = "🟡"
            else:
                icon = "🔴"
            
            response += f"{icon} In {mins} min: ~{int(count)} people ({conf:.0f}% conf)\n"
        
        # Add recommendation
        next_pred = predictions[1] if len(predictions) > 1 else predictions[0]
        if next_pred['predicted_count'] >= CRITICAL_THRESHOLD:
            response += "\n⚠️ Warning: Overcrowding predicted! Consider taking action."
        
        return response
    
    def _get_trend_response(self):
        """Generate trend analysis response."""
        if not self.predictor:
            return "⚠️ Trend analysis not available."
        
        trend = self.predictor.get_trend()
        
        if trend['direction'] == 'increasing':
            icon = "📈"
            msg = "Crowd is growing"
        elif trend['direction'] == 'decreasing':
            icon = "📉"
            msg = "Crowd is shrinking"
        else:
            icon = "➡️"
            msg = "Crowd is stable"
        
        response = f"{icon} Trend Analysis\n\n"
        response += f"Direction: {msg}\n"
        response += f"Rate: {abs(trend['rate']):.1f} change/10sec\n"
        response += f"Confidence: {trend['confidence']:.0f}%"
        
        return response
    
    def _get_analytics_response(self):
        """Generate comprehensive analytics response."""
        if not self.predictor:
            return "⚠️ Analytics not available."
        
        analytics = self.predictor.get_analytics()
        
        response = "📈 Crowd Analytics\n\n"
        response += f"Current: {analytics['current']} people\n"
        response += f"Peak (recent): {analytics['peak_recent']} people\n"
        response += f"Average: {analytics['average_recent']:.1f} people\n"
        response += f"Minimum: {analytics['min_recent']} people\n"
        response += f"Data points: {analytics['data_points']}\n"
        
        trend = analytics['trend']
        trend_icon = "📈" if trend['direction'] == 'increasing' else "📉" if trend['direction'] == 'decreasing' else "➡️"
        response += f"\nTrend: {trend_icon} {trend['direction'].title()}"
        
        return response
    
    def _get_alerts_response(self):
        """Generate response with recent alerts."""
        alerts = self.get_alerts()
        
        if alerts:
            response = "📢 Recent Alerts\n\n"
            for alert in alerts[:5]:
                response += f"[{alert['timestamp']}] {alert['message']}\n\n"
        else:
            response = "✅ No alerts. All areas operating normally."
        
        return response
    
    def _get_help_response(self):
        """Generate help response with available commands."""
        return (
            "🤖 Available Commands\n\n"
            "• status - Current crowd levels\n"
            "• predict - Future crowd forecast\n"
            "• trend - Crowd trend analysis\n"
            "• analytics - Detailed statistics\n"
            "• alerts - View recent alerts\n"
            "• camera 1-4 - Specific camera info\n"
            "• threshold - Alert settings\n"
            "• report - View session summary\n"
            "• heatmap - Toggle density heatmap"
        )
    
    def _get_threshold_response(self):
        """Generate response with threshold settings."""
        return (
            f"⚙️ Alert Thresholds\n\n"
            f"• Warning: {WARNING_THRESHOLD}+ people\n"
            f"• Critical: {CRITICAL_THRESHOLD}+ people"
        )
    
    def _get_camera_response(self, message):
        """Generate response for specific camera query."""
        camera_data = self.get_camera_data()
        
        for i in range(1, 5):
            if str(i) in message:
                cam = camera_data.get(f'cam{i}')
                if cam:
                    trend = cam.get('trend', 'stable')
                    trend_icon = "📈" if trend == 'increasing' else "📉" if trend == 'decreasing' else "➡️"
                    
                    response = (
                        f"📷 {cam['name']}\n\n"
                        f"People: {cam['headcount']}\n"
                        f"Density: {cam['density']}%\n"
                        f"Status: {cam['status']}\n"
                        f"Trend: {trend_icon} {trend.title()}"
                    )
                    
                    # Add prediction if available
                    if cam.get('prediction'):
                        pred = cam['prediction']
                        response += f"\n\n🔮 5-min forecast: ~{int(pred['predicted_count'])} people"
                    
                    return response
        
        return "Please specify camera 1-4"
    
    def _get_report_response(self):
        """Generate report/export help response."""
        return (
            "📊 Export Reports\n\n"
            "You can export crowd analytics data:\n\n"
            "• Click the 📄 CSV button in Analytics panel\n"
            "• Click the 📋 JSON button for raw data\n\n"
            "Reports include session summary, camera status, hourly stats, and event logs."
        )
    
    def _get_heatmap_response(self):
        """Generate heatmap help response."""
        return (
            "🔥 Crowd Heatmap\n\n"
            "The heatmap shows crowd density visually:\n\n"
            "• 🔵 Blue = Low density\n"
            "• 🟢 Green = Moderate\n"
            "• 🟡 Yellow = High\n"
            "• 🔴 Red = Very high\n\n"
            "Click the 🔥 button above the camera feeds to toggle it on/off."
        )

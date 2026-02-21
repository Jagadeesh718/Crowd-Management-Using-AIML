"""
Crowd Ease - Crowd Flow Prediction Module
Time-series based crowd prediction using ARIMA model
"""

import numpy as np
from datetime import datetime, timedelta
from collections import deque
import warnings
warnings.filterwarnings('ignore')

# Try to import ARIMA, fall back to simple prediction if not available
try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
    print("✅ ARIMA model enabled for advanced predictions")
except ImportError:
    ARIMA_AVAILABLE = False
    print("⚠️ statsmodels not available, using simple prediction")


class CrowdPredictor:
    """Predicts future crowd levels using ARIMA time-series model."""
    
    def __init__(self, history_size=200):
        # Store historical data points
        self.history_size = history_size
        self.crowd_history = deque(maxlen=history_size)
        
        # Time-based patterns (hour -> average count)
        self.hourly_patterns = {i: [] for i in range(24)}
        
        # Prediction parameters
        self.trend_window = 10  # Number of recent points for trend
        self.prediction_horizons = [1, 5, 10]  # Minutes ahead to predict
        
        # ARIMA parameters (p, d, q)
        # p = autoregressive order
        # d = differencing order  
        # q = moving average order
        self.arima_order = (2, 1, 2)
        self.min_data_for_arima = 30  # Minimum data points needed for ARIMA
        
        # Alert thresholds
        self.warning_threshold = 3
        self.critical_threshold = 5
        
        # Cache for ARIMA model (refit periodically)
        self.arima_model = None
        self.last_model_fit = None
        self.model_refit_interval = 20  # Refit every 20 observations
        
    def add_observation(self, count, timestamp=None):
        """
        Add a new crowd count observation.
        
        Args:
            count: Current headcount
            timestamp: Observation time (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.crowd_history.append({
            'count': count,
            'timestamp': timestamp,
            'hour': timestamp.hour,
            'minute': timestamp.minute
        })
        
        # Update hourly patterns
        hour = timestamp.hour
        self.hourly_patterns[hour].append(count)
        
        # Keep only recent data for hourly patterns (last 50 per hour)
        if len(self.hourly_patterns[hour]) > 50:
            self.hourly_patterns[hour] = self.hourly_patterns[hour][-50:]
    
    def get_trend(self):
        """
        Calculate current crowd trend.
        
        Returns:
            dict: Trend info with direction and rate of change
        """
        if len(self.crowd_history) < 3:
            return {'direction': 'stable', 'rate': 0, 'confidence': 0}
        
        recent = list(self.crowd_history)[-self.trend_window:]
        counts = [p['count'] for p in recent]
        
        # Calculate linear regression slope
        x = np.arange(len(counts))
        slope = np.polyfit(x, counts, 1)[0] if len(counts) > 1 else 0
        
        # Calculate rate of change per minute
        if len(recent) >= 2:
            time_diff = (recent[-1]['timestamp'] - recent[0]['timestamp']).total_seconds() / 60
            if time_diff > 0:
                rate = slope / time_diff * 10  # Change per 10 seconds
            else:
                rate = 0
        else:
            rate = 0
        
        # Determine direction
        if slope > 0.3:
            direction = 'increasing'
        elif slope < -0.3:
            direction = 'decreasing'
        else:
            direction = 'stable'
        
        # Confidence based on data consistency
        if len(counts) > 2:
            variance = np.var(counts)
            confidence = max(0, min(100, 100 - variance * 10))
        else:
            confidence = 30
        
        return {
            'direction': direction,
            'rate': round(rate, 2),
            'confidence': round(confidence, 1),
            'slope': round(slope, 3)
        }
    
    def predict_crowd(self, minutes_ahead=5):
        """
        Predict crowd count for a future time using ARIMA model.
        
        Args:
            minutes_ahead: How many minutes to predict ahead
            
        Returns:
            dict: Prediction with estimated count and confidence
        """
        if len(self.crowd_history) < 5:
            current = self.crowd_history[-1]['count'] if self.crowd_history else 0
            return {
                'predicted_count': current,
                'confidence': 20,
                'method': 'insufficient_data'
            }
        
        recent = list(self.crowd_history)[-50:]
        counts = [p['count'] for p in recent]
        current_count = counts[-1]
        
        # Number of steps to predict (assuming ~3 observations per minute)
        steps = max(1, int(minutes_ahead * 3))
        
        # Try ARIMA prediction if we have enough data
        arima_prediction = None
        if ARIMA_AVAILABLE and len(counts) >= self.min_data_for_arima:
            arima_prediction = self._arima_predict(counts, steps)
        
        # Fallback: Trend-based prediction
        trend = self.get_trend()
        trend_prediction = current_count + (trend['slope'] * minutes_ahead * 6)
        
        # Moving average prediction
        ma_5 = np.mean(counts[-5:]) if len(counts) >= 5 else current_count
        ma_10 = np.mean(counts[-10:]) if len(counts) >= 10 else ma_5
        
        # Hourly pattern (if available)
        future_hour = (datetime.now() + timedelta(minutes=minutes_ahead)).hour
        if self.hourly_patterns[future_hour] and len(self.hourly_patterns[future_hour]) > 5:
            hourly_avg = np.mean(self.hourly_patterns[future_hour])
            hourly_weight = 0.2
        else:
            hourly_avg = current_count
            hourly_weight = 0
        
        # Combine predictions
        if arima_prediction is not None:
            # ARIMA available - weight it heavily
            arima_weight = 0.5
            trend_weight = 0.2 - hourly_weight / 2
            ma_weight = 0.3 - hourly_weight / 2
            
            predicted = (
                arima_prediction * arima_weight +
                trend_prediction * trend_weight +
                ma_10 * ma_weight +
                hourly_avg * hourly_weight
            )
            method = 'ARIMA'
            base_confidence = 75
        else:
            # No ARIMA - use ensemble
            trend_weight = 0.5 - hourly_weight / 2
            ma_weight = 0.5 - hourly_weight / 2
            
            predicted = (
                trend_prediction * trend_weight +
                ma_10 * ma_weight +
                hourly_avg * hourly_weight
            )
            method = 'Ensemble'
            base_confidence = 60
        
        # Ensure non-negative
        predicted = max(0, predicted)
        
        # Calculate confidence
        confidence = base_confidence * (trend['confidence'] / 100)
        if minutes_ahead > 5:
            confidence *= 0.85  # Reduce for longer predictions
        if minutes_ahead > 10:
            confidence *= 0.85
        
        return {
            'predicted_count': round(predicted, 1),
            'current_count': current_count,
            'minutes_ahead': minutes_ahead,
            'confidence': round(min(95, max(20, confidence)), 1),
            'trend': trend['direction'],
            'method': method
        }
    
    def _arima_predict(self, data, steps):
        """
        Make prediction using ARIMA model.
        
        Args:
            data: Historical time series data
            steps: Number of steps to forecast
            
        Returns:
            float: Predicted value or None if failed
        """
        try:
            # Check if we need to refit the model
            should_refit = (
                self.arima_model is None or 
                self.last_model_fit is None or
                len(self.crowd_history) - self.last_model_fit >= self.model_refit_interval
            )
            
            if should_refit:
                # Fit ARIMA model
                # Use smaller order if not enough data
                if len(data) < 50:
                    order = (1, 1, 1)
                else:
                    order = self.arima_order
                
                model = ARIMA(data, order=order)
                self.arima_model = model.fit()
                self.last_model_fit = len(self.crowd_history)
            
            # Make forecast
            forecast = self.arima_model.forecast(steps=steps)
            
            # Return the last predicted value
            predicted = forecast[-1] if len(forecast) > 0 else None
            
            return predicted
            
        except Exception as e:
            # ARIMA failed, return None to use fallback
            return None
    
    def get_predictions(self):
        """
        Get predictions for multiple time horizons.
        
        Returns:
            list: Predictions for 1, 5, and 10 minutes ahead
        """
        predictions = []
        for minutes in self.prediction_horizons:
            pred = self.predict_crowd(minutes)
            predictions.append(pred)
        return predictions
    
    def check_proactive_alert(self):
        """
        Check if a proactive alert should be triggered based on predictions.
        
        Returns:
            dict or None: Alert info if threshold will be exceeded
        """
        current = self.crowd_history[-1]['count'] if self.crowd_history else 0
        
        # Check predictions
        for minutes in [1, 3, 5]:
            pred = self.predict_crowd(minutes)
            predicted = pred['predicted_count']
            
            # Check if will exceed critical threshold
            if predicted >= self.critical_threshold and current < self.critical_threshold:
                return {
                    'type': 'proactive_critical',
                    'message': f'⚠️ PREDICTION: Crowd may reach CRITICAL level ({int(predicted)} people) in ~{minutes} minutes!',
                    'predicted_count': int(predicted),
                    'current_count': current,
                    'time_to_threshold': minutes,
                    'confidence': pred['confidence'],
                    'severity': 'critical'
                }
            
            # Check if will exceed warning threshold
            elif predicted >= self.warning_threshold and current < self.warning_threshold:
                return {
                    'type': 'proactive_warning',
                    'message': f'📊 PREDICTION: Crowd may reach WARNING level ({int(predicted)} people) in ~{minutes} minutes.',
                    'predicted_count': int(predicted),
                    'current_count': current,
                    'time_to_threshold': minutes,
                    'confidence': pred['confidence'],
                    'severity': 'warning'
                }
        
        return None
    
    def get_analytics(self):
        """
        Get comprehensive crowd analytics.
        
        Returns:
            dict: Analytics including trend, predictions, and patterns
        """
        if not self.crowd_history:
            return {
                'current': 0,
                'trend': {'direction': 'stable', 'rate': 0},
                'predictions': [],
                'peak_today': 0,
                'average_today': 0
            }
        
        counts = [p['count'] for p in self.crowd_history]
        current_hour = datetime.now().hour
        
        return {
            'current': counts[-1] if counts else 0,
            'trend': self.get_trend(),
            'predictions': self.get_predictions(),
            'peak_recent': max(counts),
            'average_recent': round(np.mean(counts), 1),
            'min_recent': min(counts),
            'hourly_average': round(np.mean(self.hourly_patterns[current_hour]), 1) if self.hourly_patterns[current_hour] else 0,
            'data_points': len(self.crowd_history)
        }


# Singleton instance
crowd_predictor = CrowdPredictor()

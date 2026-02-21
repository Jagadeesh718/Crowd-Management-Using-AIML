"""
Crowd Ease - Configuration Settings
"""

import os

# Directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

# Flask settings
SECRET_KEY = 'crowd_management_secret_key'

# Alert thresholds
MAX_PEOPLE_THRESHOLD = 2
WARNING_THRESHOLD = 2
CRITICAL_THRESHOLD = 3

# Camera settings
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FRAME_RATE = 0.033  # ~30 FPS for smooth video

# History settings
MAX_HISTORY_LENGTH = 20
MAX_ALERTS = 50

# Alert cooldown (seconds)
CRITICAL_ALERT_COOLDOWN = 10
WARNING_ALERT_COOLDOWN = 15

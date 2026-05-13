"""
Crowd Ease - Configuration Settings
"""

import os

# Directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

# Flask settings
SECRET_KEY = 'crowd_management_secret_key'

# Alert thresholds (consistent across backend and frontend)
MAX_PEOPLE_THRESHOLD = 5
WARNING_THRESHOLD = 3
CRITICAL_THRESHOLD = 5

# Camera settings
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FRAME_RATE = 0.033  # ~30 FPS for smooth video
AI_FRAME_QUEUE_SIZE = 3
AI_LOOP_SLEEP = 0.05
STREAM_LOOP_SLEEP = 0.033

# History settings
MAX_HISTORY_LENGTH = 60
MAX_ALERTS = 50

# Alert cooldown (seconds)
CRITICAL_ALERT_COOLDOWN = 10
WARNING_ALERT_COOLDOWN = 15

# ===================================
# Venue Map Zone Configuration
# ===================================
VENUE_ZONES = {
    'entrance': {
        'name': 'Main Entrance',
        'camera': 'cam1',
        'capacity': 50,
        'x': 0.5, 'y': 0.85,       # Relative position on map
        'width': 0.25, 'height': 0.12,
        'color': '#007aff',
        'connections': ['stage', 'food_court'],
    },
    'stage': {
        'name': 'Stage Area',
        'camera': 'cam2',
        'capacity': 100,
        'x': 0.5, 'y': 0.35,
        'width': 0.4, 'height': 0.25,
        'color': '#ff9500',
        'connections': ['entrance', 'food_court', 'exit'],
    },
    'food_court': {
        'name': 'Food Court',
        'camera': 'cam3',
        'capacity': 40,
        'x': 0.15, 'y': 0.55,
        'width': 0.2, 'height': 0.2,
        'color': '#34c759',
        'connections': ['entrance', 'stage'],
    },
    'exit': {
        'name': 'Exit Gate',
        'camera': 'cam4',
        'capacity': 50,
        'x': 0.85, 'y': 0.55,
        'width': 0.2, 'height': 0.12,
        'color': '#af52de',
        'connections': ['stage', 'food_court'],
    },
}

# Simulated camera patterns (hour -> avg headcount)
# Used to generate realistic demo data for cameras 2-4
SIMULATED_PATTERNS = {
    'cam2': {  # Stage Area — peaks during performances
        'base': 8, 'variance': 5,
        'peak_hours': [10, 11, 14, 15, 19, 20],
        'peak_multiplier': 2.5,
    },
    'cam3': {  # Food Court — peaks at meal times
        'base': 5, 'variance': 3,
        'peak_hours': [12, 13, 18, 19],
        'peak_multiplier': 3.0,
    },
    'cam4': {  # Exit Gate — peaks after events
        'base': 3, 'variance': 2,
        'peak_hours': [12, 16, 21, 22],
        'peak_multiplier': 2.0,
    },
}

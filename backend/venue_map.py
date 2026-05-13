"""
Crowd Ease - Venue Map & Zone Analytics Module
Provides real-time venue layout data, zone density, and people flow simulation.
"""

import math
import random
import time
from datetime import datetime

from config import VENUE_ZONES, SIMULATED_PATTERNS


class VenueMap:
    """Manages venue layout, zone densities, and simulated camera data."""

    def __init__(self):
        self.zones = {}
        for zone_id, zone_cfg in VENUE_ZONES.items():
            self.zones[zone_id] = {
                **zone_cfg,
                'headcount': 0,
                'density': 0,
                'trend': 'stable',
                'history': [],
            }

        # People flow particles for visualization
        self.flow_particles = []
        self._last_flow_update = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_zone_from_camera(self, camera_id, headcount, density, trend='stable'):
        """Update a zone based on real camera data."""
        for zone_id, zone in self.zones.items():
            if zone['camera'] == camera_id:
                zone['headcount'] = headcount
                zone['density'] = density
                zone['trend'] = trend
                zone['history'].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'count': headcount,
                    'density': density,
                })
                # Keep last 60 entries
                if len(zone['history']) > 60:
                    zone['history'] = zone['history'][-60:]
                break

    def get_simulated_headcount(self, camera_id):
        """
        Generate a realistic headcount for a simulated camera based on
        time-of-day patterns + random variance.
        """
        pattern = SIMULATED_PATTERNS.get(camera_id)
        if not pattern:
            return 0, 0

        hour = datetime.now().hour
        minute = datetime.now().minute
        base = pattern['base']
        variance = pattern['variance']

        # Apply peak multiplier if current hour is a peak hour
        if hour in pattern['peak_hours']:
            # Smooth ramp: stronger in the middle of the hour
            ramp = math.sin(math.pi * minute / 60)
            base = int(base * pattern['peak_multiplier'] * (0.6 + 0.4 * ramp))

        # Add realistic noise
        headcount = max(0, base + random.randint(-variance, variance))
        density = min(100, int(headcount / (pattern['base'] * pattern['peak_multiplier']) * 100))

        return headcount, density

    def generate_flow_particles(self):
        """Generate people-flow particles between connected zones."""
        now = time.time()
        if now - self._last_flow_update < 0.5:
            return self.flow_particles

        self._last_flow_update = now
        new_particles = []

        for zone_id, zone in self.zones.items():
            if zone['headcount'] <= 0:
                continue
            for conn in zone.get('connections', []):
                target = self.zones.get(conn)
                if not target:
                    continue
                # More particles when density is higher
                count = max(1, zone['headcount'] // 8)
                for _ in range(count):
                    progress = random.random()
                    new_particles.append({
                        'from': zone_id,
                        'to': conn,
                        'x': zone['x'] + (target['x'] - zone['x']) * progress,
                        'y': zone['y'] + (target['y'] - zone['y']) * progress,
                        'progress': progress,
                        'speed': 0.002 + random.random() * 0.005,
                    })

        self.flow_particles = new_particles[:80]  # Cap at 80 particles
        return self.flow_particles

    def get_zone_data(self):
        """Return all zone data for the frontend venue map."""
        zones_out = {}
        for zone_id, zone in self.zones.items():
            capacity = zone.get('capacity', 50)
            headcount = zone['headcount']
            density_pct = min(100, int(headcount / capacity * 100)) if capacity else 0

            # Determine severity
            if density_pct >= 80:
                severity = 'critical'
            elif density_pct >= 50:
                severity = 'warning'
            else:
                severity = 'normal'

            zones_out[zone_id] = {
                'name': zone['name'],
                'headcount': headcount,
                'density': density_pct,
                'capacity': capacity,
                'trend': zone.get('trend', 'stable'),
                'severity': severity,
                'x': zone['x'],
                'y': zone['y'],
                'width': zone['width'],
                'height': zone['height'],
                'color': zone['color'],
                'connections': zone.get('connections', []),
            }

        return zones_out

    def get_emergency_data(self):
        """Return evacuation-relevant data."""
        total_people = sum(z['headcount'] for z in self.zones.values())
        exit_capacity_per_min = 20  # people per minute through exit

        return {
            'total_people': total_people,
            'estimated_evacuation_min': max(1, math.ceil(total_people / exit_capacity_per_min)),
            'zones': {
                zid: {
                    'name': z['name'],
                    'headcount': z['headcount'],
                    'nearest_exit': 'exit',
                }
                for zid, z in self.zones.items()
            },
        }


# Singleton
venue_map = VenueMap()

"""
Runtime metrics collector for pipeline health and performance visibility.
"""

import threading
import time


class MetricsCollector:
    """Thread-safe collector for streaming and inference metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._last_stream_tick = None
        self._last_ai_tick = None
        self._data = {
            'stream_fps': 0.0,
            'ai_fps': 0.0,
            'last_inference_ms': 0.0,
            'avg_inference_ms': 0.0,
            'max_inference_ms': 0.0,
            'frames_seen': 0,
            'frames_processed': 0,
            'frames_dropped': 0,
            'queue_depth': 0
        }

    def _update_fps(self, key, last_tick_attr):
        now = time.time()
        last_tick = getattr(self, last_tick_attr)
        if last_tick is not None:
            delta = now - last_tick
            if delta > 0:
                self._data[key] = round(1.0 / delta, 2)
        setattr(self, last_tick_attr, now)

    def mark_stream_tick(self):
        with self._lock:
            self._data['frames_seen'] += 1
            self._update_fps('stream_fps', '_last_stream_tick')

    def mark_ai_processed(self, inference_ms):
        with self._lock:
            self._data['frames_processed'] += 1
            self._data['last_inference_ms'] = round(inference_ms, 2)
            self._data['max_inference_ms'] = round(
                max(self._data['max_inference_ms'], inference_ms), 2
            )
            processed = self._data['frames_processed']
            prev_avg = self._data['avg_inference_ms']
            self._data['avg_inference_ms'] = round(
                ((prev_avg * (processed - 1)) + inference_ms) / processed, 2
            )
            self._update_fps('ai_fps', '_last_ai_tick')

    def mark_frame_dropped(self, count=1):
        with self._lock:
            self._data['frames_dropped'] += count

    def set_queue_depth(self, depth):
        with self._lock:
            self._data['queue_depth'] = depth

    def snapshot(self):
        with self._lock:
            uptime = int(time.time() - self._started_at)
            return {
                **self._data,
                'uptime_seconds': uptime
            }


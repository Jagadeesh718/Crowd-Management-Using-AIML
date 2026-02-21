"""
Crowd Ease - Camera Management Module
Handles camera connections and frame capture with threading for low latency
"""

import cv2
import threading
import time
from config import CAMERA_WIDTH, CAMERA_HEIGHT


class CameraManager:
    """Manages camera connections and frame capture with minimal latency."""
    
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.capture_thread = None
    
    def start_camera(self):
        """
        Initialize and start the camera with dedicated capture thread.
        
        Returns:
            bool: True if camera started successfully
        """
        if self.cap is None or not self.cap.isOpened():
            # Use DirectShow backend on Windows for lower latency
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            # Optimize for minimal latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.running = True
            
            # Start dedicated capture thread for real-time frames
            if self.capture_thread is None or not self.capture_thread.is_alive():
                self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
                self.capture_thread.start()
                
        return self.cap.isOpened()
    
    def _capture_loop(self):
        """Continuously capture frames in background - always has latest frame."""
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame
            time.sleep(0.001)  # Minimal sleep, max ~1000 FPS capture rate
    
    def get_frame(self):
        """
        Get the most recent frame (non-blocking, always fresh).
        
        Returns:
            numpy.ndarray or None: The latest frame, or None if not available
        """
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def stop_camera(self):
        """Stop the camera and release resources."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1)
        if self.cap:
            self.cap.release()
            self.cap = None
        self.current_frame = None
    
    def is_running(self):
        """Check if camera is currently running."""
        return self.running and self.cap is not None and self.cap.isOpened()


# Default camera manager instance
camera_manager = CameraManager()

"""
Crowd Ease - Person Detection Module
AI-powered person detection using OpenCV Haar Cascades and HOG
"""

import cv2
from config import WARNING_THRESHOLD, CRITICAL_THRESHOLD


class PersonDetector:
    """Detects people in video frames using face detection and HOG body detection."""
    
    def __init__(self):
        # Load Haar cascade classifiers for face detection
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_profileface.xml'
        )
        
        # Initialize HOG descriptor for body detection
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    
    def detect_people(self, frame):
        """
        Detect people in a frame using face and body detection.
        
        Args:
            frame: OpenCV image frame (BGR format)
            
        Returns:
            tuple: (people_count, detections_list)
            detections_list: List of dicts with x, y, w, h, label
        """
        if frame is None:
            return 0, []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = []
        
        # Detect faces (frontal and profile)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        profiles = self.profile_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        
        # Combine and deduplicate detections
        all_faces = list(faces) + list(profiles)
        unique_detections = self._remove_duplicates(all_faces)
        
        # Convert to detection dicts
        for i, (x, y, w, h) in enumerate(unique_detections):
            detections.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'label': f'#{i+1}'
            })
        
        people_count = len(detections)
        
        # If no faces found, try HOG body detection
        if people_count == 0:
            body_detections = self._detect_bodies_coords(frame)
            detections = body_detections
            people_count = len(detections)
        
        return people_count, detections
    
    def _detect_bodies_coords(self, frame):
        """Detect full bodies and return coordinates."""
        small_frame = cv2.resize(frame, (320, 240))
        bodies, weights = self.hog.detectMultiScale(
            small_frame, winStride=(8, 8), padding=(4, 4), scale=1.05
        )
        
        scale_x = frame.shape[1] / 320
        scale_y = frame.shape[0] / 240
        
        detections = []
        for i, (x, y, w, h) in enumerate(bodies):
            detections.append({
                'x': int(x * scale_x),
                'y': int(y * scale_y),
                'w': int(w * scale_x),
                'h': int(h * scale_y),
                'label': f'#{i+1}'
            })
        
        return detections
    
    def _detect_bodies(self, frame):
        """Detect full bodies using HOG descriptor."""
        small_frame = cv2.resize(frame, (320, 240))
        bodies, weights = self.hog.detectMultiScale(
            small_frame, winStride=(8, 8), padding=(4, 4), scale=1.05
        )
        
        scale_x = frame.shape[1] / 320
        scale_y = frame.shape[0] / 240
        
        for (x, y, w, h) in bodies:
            x = int(x * scale_x)
            y = int(y * scale_y)
            w = int(w * scale_x)
            h = int(h * scale_y)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (52, 199, 89), 2)
        
        return len(bodies)
        return len(bodies)
    
    def _draw_face_detections(self, frame, detections):
        """Draw rectangles around detected faces."""
        for i, (x, y, w, h) in enumerate(detections):
            cv2.rectangle(frame, (x, y), (x+w, y+h), (52, 199, 89), 2)
            cv2.putText(
                frame, f'#{i+1}', (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (52, 199, 89), 2
            )
    
    def _draw_overlay(self, frame, people_count):
        """Draw information overlay on frame."""
        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (200, 70), (255, 255, 255), -1)
        frame[:] = cv2.addWeighted(overlay, 0.8, frame, 0.2, 0)
        
        # Determine color based on count
        if people_count < WARNING_THRESHOLD:
            color = (52, 199, 89)  # Green
        elif people_count < CRITICAL_THRESHOLD:
            color = (255, 149, 0)  # Orange
        else:
            color = (255, 59, 48)  # Red
        
        # Draw count text
        cv2.putText(
            frame, f'People: {people_count}', (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color[::-1], 2
        )
        
        # Draw density text
        density = min(100, people_count * 20)
        cv2.putText(
            frame, f'Density: {density}%', (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2
        )
    
    def _remove_duplicates(self, detections, overlap_threshold=0.3):
        """Remove overlapping detections to avoid double counting."""
        if len(detections) == 0:
            return []
        
        detections = [list(d) for d in detections]
        unique = []
        
        for det in detections:
            is_duplicate = False
            for existing in unique:
                # Calculate intersection
                x1 = max(det[0], existing[0])
                y1 = max(det[1], existing[1])
                x2 = min(det[0] + det[2], existing[0] + existing[2])
                y2 = min(det[1] + det[3], existing[1] + existing[3])
                
                if x1 < x2 and y1 < y2:
                    intersection = (x2 - x1) * (y2 - y1)
                    min_area = min(det[2] * det[3], existing[2] * existing[3])
                    if intersection / min_area > overlap_threshold:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique.append(det)
        
        return unique


# Singleton instance
detector = PersonDetector()

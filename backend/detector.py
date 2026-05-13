"""
Crowd Ease - Person Detection Module
AI-powered person detection using YOLOv8 (You Only Look Once v8)
Falls back to OpenCV HOG if ultralytics is not installed.
"""

import cv2

# Try to import YOLOv8 from ultralytics
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ YOLOv8 model loaded for person detection")
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ ultralytics not installed, falling back to HOG detector")


class PersonDetector:
    """Detects people in video frames using YOLOv8 or HOG fallback."""

    # COCO class ID for 'person'
    PERSON_CLASS_ID = 0

    def __init__(self):
        self.yolo_model = None

        if YOLO_AVAILABLE:
            try:
                # Use YOLOv8 nano for speed on laptop — download on first run
                self.yolo_model = YOLO('yolov8n.pt')
                print("✅ YOLOv8n (nano) model ready")
            except Exception as e:
                print(f"⚠️ YOLOv8 init failed: {e} — using HOG fallback")

        # HOG fallback
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        # Confidence threshold for YOLO detections
        self.confidence_threshold = 0.35

    def detect_people(self, frame):
        """
        Detect people in a frame using YOLOv8 or HOG fallback.

        Args:
            frame: OpenCV image frame (BGR format)

        Returns:
            tuple: (people_count, detections_list)
            detections_list: List of dicts with x, y, w, h, label, confidence
        """
        if frame is None:
            return 0, []

        if self.yolo_model is not None:
            return self._detect_yolo(frame)
        else:
            return self._detect_hog(frame)

    def _detect_yolo(self, frame):
        """Detect people using YOLOv8."""
        try:
            # Run inference — verbose=False suppresses console output
            results = self.yolo_model(frame, verbose=False, classes=[self.PERSON_CLASS_ID])

            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for box in boxes:
                    conf = float(box.conf[0])
                    if conf < self.confidence_threshold:
                        continue

                    # Get bounding box coordinates (xyxy format → xywh)
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    w = x2 - x1
                    h = y2 - y1

                    detections.append({
                        'x': int(x1), 'y': int(y1),
                        'w': int(w), 'h': int(h),
                        'label': f'#{len(detections) + 1}',
                        'confidence': round(conf, 2)
                    })

            return len(detections), detections

        except Exception as e:
            print(f"YOLOv8 detection error: {e}")
            return self._detect_hog(frame)

    def _detect_hog(self, frame):
        """Detect people using HOG descriptor (fallback)."""
        small_frame = cv2.resize(frame, (640, 480))
        bodies, weights = self.hog.detectMultiScale(
            small_frame, winStride=(8, 8), padding=(4, 4), scale=1.05
        )

        scale_x = frame.shape[1] / 640
        scale_y = frame.shape[0] / 480

        detections = []
        for i, (x, y, w, h) in enumerate(bodies):
            detections.append({
                'x': int(x * scale_x),
                'y': int(y * scale_y),
                'w': int(w * scale_x),
                'h': int(h * scale_y),
                'label': f'#{i + 1}',
                'confidence': round(float(weights[i]) if i < len(weights) else 0.5, 2)
            })

        return len(detections), detections

    def _remove_duplicates(self, detections, overlap_threshold=0.3):
        """Remove overlapping detections to avoid double counting."""
        if len(detections) == 0:
            return []

        detections = [list(d) for d in detections]
        unique = []

        for det in detections:
            is_duplicate = False
            for existing in unique:
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

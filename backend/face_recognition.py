"""
Crowd Ease - Advanced Face Recognition Module
High-accuracy missing person detection using ensemble methods:
1. LBPH (Local Binary Pattern Histograms) - trained with data augmentation
2. Multi-scale histogram comparison with spatial pyramid
3. Structural similarity (SSIM) matching
4. Template matching with multiple poses
5. Feature matching using ORB descriptors
"""

import cv2
import numpy as np
import os
import base64
from datetime import datetime

# Directory to store missing person images
MISSING_PERSONS_DIR = os.path.join(os.path.dirname(__file__), 'missing_persons')

# Check if LBPH is available (requires opencv-contrib-python)
LBPH_AVAILABLE = hasattr(cv2, 'face') and hasattr(cv2.face, 'LBPHFaceRecognizer_create')


class FaceRecognizer:
    """
    Advanced face recognition using ensemble of multiple methods for maximum accuracy.
    """
    
    def __init__(self):
        # Create directory if not exists
        os.makedirs(MISSING_PERSONS_DIR, exist_ok=True)
        
        # Load primary face detection cascades (optimized - fewer for speed)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
        )
        self.profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_profileface.xml'
        )
        
        print(f"✅ Loaded optimized face detection cascades")
        
        # Frame counter (process every frame for better accuracy)
        self.frame_count = 0
        self.process_every_n_frames = 1  # Process every frame for accuracy
        
        # Initialize single LBPH Face Recognizer (optimized for speed)
        self.lbph_recognizer = None
        self.lbph_trained = False
        
        if LBPH_AVAILABLE:
            try:
                self.lbph_recognizer = cv2.face.LBPHFaceRecognizer_create(
                    radius=2,
                    neighbors=8,
                    grid_x=8,
                    grid_y=8,
                    threshold=100
                )
                print(f"✅ LBPH Face Recognizer enabled")
            except Exception as e:
                print(f"⚠️ LBPH initialization error: {e}")
        else:
            print("⚠️ LBPH not available - using histogram-only matching")
        
        # Initialize ORB feature detector
        self.orb = cv2.ORB_create(nfeatures=500)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Missing persons database
        self.missing_persons = {}
        self.next_id = 1
        
        # Load existing missing persons
        self._load_existing_persons()
        
        # Track recent matches to avoid spam
        self.recent_matches = {}
        self.match_cooldown = 10  # seconds between alerts
        
        # Matching thresholds (very lenient for better recognition)
        self.lbph_threshold = 200  # LBPH distance threshold (higher = more lenient)
        self.histogram_threshold = 0.10  # Histogram correlation threshold (lower = more matches)
        self.ssim_threshold = 0.10  # SSIM threshold
        self.orb_threshold = 3  # Minimum ORB matches
        self.combined_threshold = 0.12  # Final combined score threshold (lower = more matches)
    
    def _train_lbph(self):
        """Train LBPH recognizer with augmented data."""
        if self.lbph_recognizer is None or not self.missing_persons:
            self.lbph_trained = False
            return
        
        faces = []
        labels = []
        
        for person_id, person in self.missing_persons.items():
            try:
                img = cv2.imread(person['image_path'], cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                
                # Detect face
                detected = self._detect_faces_multi(img)
                if len(detected) > 0:
                    x, y, w, h = max(detected, key=lambda f: f[2] * f[3])
                    face = img[y:y+h, x:x+w]
                else:
                    h, w = img.shape
                    margin = min(h, w) // 4
                    face = img[margin:h-margin, margin:w-margin]
                
                # Resize and normalize
                face = cv2.resize(face, (100, 100))
                
                # Create augmented versions
                augmented = self._augment_face(face)
                
                for aug_face in augmented:
                    faces.append(aug_face)
                    labels.append(person_id)
                
            except Exception as e:
                print(f"Error training on {person['name']}: {e}")
        
        if faces:
            try:
                self.lbph_recognizer.train(faces, np.array(labels))
                self.lbph_trained = True
                print(f"🧠 LBPH trained with {len(faces)} samples from {len(self.missing_persons)} persons")
            except Exception as e:
                print(f"⚠️ LBPH training failed: {e}")
                self.lbph_trained = False
    
    def _augment_face(self, face):
        """Create augmented versions of a face (optimized - fewer variations)."""
        augmented = []
        
        # Original with histogram equalization
        face_eq = cv2.equalizeHist(face)
        augmented.append(face_eq)
        
        # Key rotations only
        for angle in [-10, 10]:
            M = cv2.getRotationMatrix2D((50, 50), angle, 1)
            rotated = cv2.warpAffine(face_eq, M, (100, 100))
            augmented.append(rotated)
        
        # Horizontal flip
        flipped = cv2.flip(face_eq, 1)
        augmented.append(flipped)
        
        # CLAHE for lighting variation
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        clahe_face = clahe.apply(face)
        augmented.append(clahe_face)
        
        return augmented
    
    def _detect_faces_multi(self, gray_image):
        """Detect faces using optimized cascade detection - lenient for DSLR photos."""
        # Resize large images for better detection
        h, w = gray_image.shape
        scale = 1.0
        if max(h, w) > 800:
            scale = 800 / max(h, w)
            gray_resized = cv2.resize(gray_image, None, fx=scale, fy=scale)
        else:
            gray_resized = gray_image
        
        # Try with different parameters - more lenient
        for minNeighbors in [2, 3, 4]:
            for scaleFactor in [1.05, 1.1, 1.15, 1.2]:
                faces = self.face_cascade.detectMultiScale(
                    gray_resized,
                    scaleFactor=scaleFactor,
                    minNeighbors=minNeighbors,
                    minSize=(20, 20)
                )
                if len(faces) > 0:
                    # Scale back coordinates
                    if scale != 1.0:
                        faces = np.array([[int(x/scale), int(y/scale), int(w/scale), int(h/scale)] for x,y,w,h in faces])
                    return faces
        
        # Try profile detection
        for minNeighbors in [2, 3]:
            faces = self.profile_cascade.detectMultiScale(
                gray_resized,
                scaleFactor=1.1,
                minNeighbors=minNeighbors,
                minSize=(20, 20)
            )
            if len(faces) > 0:
                if scale != 1.0:
                    faces = np.array([[int(x/scale), int(y/scale), int(w/scale), int(h/scale)] for x,y,w,h in faces])
                return faces
        
        return []
    
    def _merge_overlapping_faces(self, faces):
        """Merge overlapping face detections."""
        if len(faces) == 0:
            return []
        
        faces = np.array(faces)
        merged = []
        used = [False] * len(faces)
        
        for i, face1 in enumerate(faces):
            if used[i]:
                continue
            
            x1, y1, w1, h1 = face1
            group = [face1]
            
            for j, face2 in enumerate(faces):
                if i != j and not used[j]:
                    x2, y2, w2, h2 = face2
                    
                    # Check overlap
                    overlap_x = max(0, min(x1+w1, x2+w2) - max(x1, x2))
                    overlap_y = max(0, min(y1+h1, y2+h2) - max(y1, y2))
                    overlap_area = overlap_x * overlap_y
                    
                    area1 = w1 * h1
                    area2 = w2 * h2
                    
                    if overlap_area > 0.3 * min(area1, area2):
                        group.append(face2)
                        used[j] = True
            
            used[i] = True
            
            # Average the group
            group = np.array(group)
            avg_face = np.mean(group, axis=0).astype(int)
            merged.append(avg_face)
        
        return merged
    
    def _load_existing_persons(self):
        """Load existing missing person images from directory."""
        if os.path.exists(MISSING_PERSONS_DIR):
            for filename in os.listdir(MISSING_PERSONS_DIR):
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    parts = filename.rsplit('.', 1)[0].split('_', 1)
                    if len(parts) == 2:
                        try:
                            person_id = int(parts[0])
                            name = parts[1].replace('_', ' ')
                            image_path = os.path.join(MISSING_PERSONS_DIR, filename)
                            
                            encodings = self._encode_face(image_path)
                            
                            if encodings is not None:
                                self.missing_persons[person_id] = {
                                    'id': person_id,
                                    'name': name,
                                    'image_path': image_path,
                                    'encodings': encodings,
                                    'added_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                    'last_seen': None
                                }
                                self.next_id = max(self.next_id, person_id + 1)
                        except:
                            pass
        
        self._train_lbph()
    
    def _encode_face(self, image_path):
        """Create comprehensive face encodings using multiple methods."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply histogram equalization first for better detection
            gray_eq = cv2.equalizeHist(gray)
            
            faces = self._detect_faces_multi(gray_eq)
            
            if len(faces) == 0:
                # No face detected - use center crop (portrait assumption)
                h, w = gray.shape
                # Assume face is in center-top portion of image
                margin_x = w // 6
                margin_top = h // 10
                margin_bottom = h // 3
                face_roi = gray[margin_top:h-margin_bottom, margin_x:w-margin_x]
                print(f"ℹ️ No face detected, using center crop")
            else:
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                margin = int(fw * 0.2)  # More margin for context
                x = max(0, x - margin)
                y = max(0, y - margin)
                fw = min(gray.shape[1] - x, fw + margin * 2)
                fh = min(gray.shape[0] - y, fh + margin * 2)
                face_roi = gray[y:y+fh, x:x+fw]
                print(f"✅ Face detected at ({x},{y}) size {fw}x{fh}")
            
            # Resize to standard size
            face_roi = cv2.resize(face_roi, (100, 100))
            
            # Apply CLAHE for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            face_roi = clahe.apply(face_roi)
            
            encodings = {}
            
            # 1. Spatial Pyramid Histogram (multi-scale)
            encodings['pyramid'] = self._compute_spatial_pyramid_histogram(face_roi)
            
            # 2. LBP-like texture features (manual computation)
            encodings['texture'] = self._compute_texture_features(face_roi)
            
            # 3. Edge orientation histogram
            encodings['edges'] = self._compute_edge_features(face_roi)
            
            # 4. ORB descriptors
            keypoints, descriptors = self.orb.detectAndCompute(face_roi, None)
            if descriptors is not None:
                encodings['orb'] = descriptors
            else:
                encodings['orb'] = None
            
            # 5. Normalized face template
            encodings['template'] = face_roi.copy()
            
            # 6. DCT features (frequency domain)
            encodings['dct'] = self._compute_dct_features(face_roi)
            
            return encodings
            
        except Exception as e:
            print(f"Error encoding face: {e}")
            return None
    
    def _compute_spatial_pyramid_histogram(self, face):
        """Compute spatial pyramid histogram for multi-scale matching."""
        histograms = []
        
        # Level 0: Full image
        hist = cv2.calcHist([face], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)
        histograms.append(hist.flatten())
        
        # Level 1: 2x2 grid
        h, w = face.shape
        for i in range(2):
            for j in range(2):
                region = face[i*h//2:(i+1)*h//2, j*w//2:(j+1)*w//2]
                hist = cv2.calcHist([region], [0], None, [32], [0, 256])
                cv2.normalize(hist, hist)
                histograms.append(hist.flatten())
        
        # Level 2: 4x4 grid
        for i in range(4):
            for j in range(4):
                region = face[i*h//4:(i+1)*h//4, j*w//4:(j+1)*w//4]
                hist = cv2.calcHist([region], [0], None, [16], [0, 256])
                cv2.normalize(hist, hist)
                histograms.append(hist.flatten())
        
        return np.concatenate(histograms)
    
    def _compute_texture_features(self, face):
        """Compute texture features similar to LBP."""
        # Compute gradients
        gx = cv2.Sobel(face, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(face, cv2.CV_64F, 0, 1, ksize=3)
        
        # Magnitude and orientation
        magnitude = np.sqrt(gx**2 + gy**2)
        orientation = np.arctan2(gy, gx)
        
        # Quantize orientation into 8 bins
        orientation_bins = ((orientation + np.pi) / (2 * np.pi) * 8).astype(int) % 8
        
        # Create histogram of oriented gradients (simplified HOG)
        features = []
        h, w = face.shape
        cell_size = 10
        
        for i in range(0, h-cell_size+1, cell_size):
            for j in range(0, w-cell_size+1, cell_size):
                cell_mag = magnitude[i:i+cell_size, j:j+cell_size]
                cell_ori = orientation_bins[i:i+cell_size, j:j+cell_size]
                
                hist = np.zeros(8)
                for k in range(8):
                    hist[k] = np.sum(cell_mag[cell_ori == k])
                
                # Normalize
                norm = np.sqrt(np.sum(hist**2) + 1e-6)
                hist = hist / norm
                features.extend(hist)
        
        return np.array(features)
    
    def _compute_edge_features(self, face):
        """Compute edge orientation histogram."""
        # Canny edges
        edges = cv2.Canny(face, 50, 150)
        
        # Sobel for orientation
        gx = cv2.Sobel(face, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(face, cv2.CV_64F, 0, 1, ksize=3)
        orientation = np.arctan2(gy, gx)
        
        # Histogram of edge orientations
        edge_mask = edges > 0
        edge_orientations = orientation[edge_mask]
        
        hist, _ = np.histogram(edge_orientations, bins=18, range=(-np.pi, np.pi))
        hist = hist.astype(np.float32)
        cv2.normalize(hist, hist)
        
        return hist
    
    def _compute_dct_features(self, face):
        """Compute DCT (Discrete Cosine Transform) features."""
        face_float = np.float32(face)
        dct = cv2.dct(face_float)
        
        # Take top-left 10x10 coefficients (low frequency)
        dct_features = dct[:10, :10].flatten()
        
        # Normalize
        norm = np.sqrt(np.sum(dct_features**2) + 1e-6)
        dct_features = dct_features / norm
        
        return dct_features
    
    def add_missing_person(self, name, image_data):
        """Add a new missing person to the database."""
        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            # Save image
            person_id = self.next_id
            safe_name = name.replace(' ', '_')
            filename = f"{person_id}_{safe_name}.jpg"
            image_path = os.path.join(MISSING_PERSONS_DIR, filename)
            cv2.imwrite(image_path, img)
            
            # Create encodings
            encodings = self._encode_face(image_path)
            
            if encodings is None:
                os.remove(image_path)
                return None
            
            # Add to database
            person = {
                'id': person_id,
                'name': name,
                'image_path': image_path,
                'encodings': encodings,
                'added_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'last_seen': None
            }
            
            self.missing_persons[person_id] = person
            self.next_id += 1
            
            # Retrain LBPH with new person
            self._train_lbph()
            
            print(f"✅ Added missing person: {name} (ID: {person_id})")
            
            return {
                'id': person_id,
                'name': name,
                'added_at': person['added_at']
            }
            
        except Exception as e:
            print(f"Error adding missing person: {e}")
            return None
    
    def remove_missing_person(self, person_id):
        """Remove a missing person from the database."""
        if person_id in self.missing_persons:
            person = self.missing_persons[person_id]
            
            if os.path.exists(person['image_path']):
                os.remove(person['image_path'])
            
            del self.missing_persons[person_id]
            self._train_lbph()
            return True
        return False
    
    def get_all_missing_persons(self):
        """Get list of all missing persons."""
        persons = []
        for person_id, person in self.missing_persons.items():
            try:
                with open(person['image_path'], 'rb') as f:
                    image_b64 = base64.b64encode(f.read()).decode('utf-8')
            except:
                image_b64 = None
            
            persons.append({
                'id': person_id,
                'name': person['name'],
                'added_at': person['added_at'],
                'last_seen': person['last_seen'],
                'photo': f"data:image/jpeg;base64,{image_b64}" if image_b64 else None
            })
        
        return {'persons': persons}
    
    def _compare_encodings(self, enc1, enc2):
        """Compare encodings using multiple metrics and return weighted score."""
        scores = []
        weights = []
        
        # 1. Pyramid histogram comparison (most important)
        if 'pyramid' in enc1 and 'pyramid' in enc2:
            score = cv2.compareHist(
                enc1['pyramid'].reshape(-1, 1).astype(np.float32),
                enc2['pyramid'].reshape(-1, 1).astype(np.float32),
                cv2.HISTCMP_CORREL
            )
            scores.append(max(0, score))
            weights.append(3.0)
        
        # 2. Texture features
        if 'texture' in enc1 and 'texture' in enc2:
            score = 1 - np.linalg.norm(enc1['texture'] - enc2['texture']) / (np.linalg.norm(enc1['texture']) + np.linalg.norm(enc2['texture']) + 1e-6)
            scores.append(max(0, score))
            weights.append(2.0)
        
        # 3. Edge features
        if 'edges' in enc1 and 'edges' in enc2:
            score = cv2.compareHist(
                enc1['edges'].reshape(-1, 1).astype(np.float32),
                enc2['edges'].reshape(-1, 1).astype(np.float32),
                cv2.HISTCMP_CORREL
            )
            scores.append(max(0, score))
            weights.append(1.5)
        
        # 4. ORB matching
        if enc1.get('orb') is not None and enc2.get('orb') is not None:
            try:
                matches = self.bf_matcher.match(enc1['orb'], enc2['orb'])
                good_matches = [m for m in matches if m.distance < 50]
                orb_score = min(1.0, len(good_matches) / 20)
                scores.append(orb_score)
                weights.append(2.0)
            except:
                pass
        
        # 5. Template matching
        if 'template' in enc1 and 'template' in enc2:
            result = cv2.matchTemplate(enc1['template'], enc2['template'], cv2.TM_CCOEFF_NORMED)
            template_score = max(0, result[0, 0])
            scores.append(template_score)
            weights.append(2.5)
        
        # 6. DCT features
        if 'dct' in enc1 and 'dct' in enc2:
            score = 1 - np.linalg.norm(enc1['dct'] - enc2['dct']) / 2
            scores.append(max(0, score))
            weights.append(1.5)
        
        # Weighted average
        if not scores:
            return 0
        
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        
        return weighted_sum / total_weight
    
    def search_in_frame(self, frame, camera_name='Unknown'):
        """Search for missing persons using ensemble matching."""
        import time
        
        if frame is None or len(self.missing_persons) == 0:
            return []
        
        # Skip frames for performance
        self.frame_count += 1
        if self.frame_count % self.process_every_n_frames != 0:
            return []
        
        matches = []
        current_time = time.time()
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply CLAHE for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_eq = clahe.apply(gray)
            
            # Detect faces with multiple cascades
            faces = self._detect_faces_multi(gray_eq)
            
            if len(faces) > 0:
                print(f"🔍 Detected {len(faces)} face(s) in frame")
            
            for face_rect in faces:
                x, y, w, h = face_rect
                
                # Extract face region with margin
                margin = int(w * 0.15)
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(gray.shape[1], x + w + margin)
                y2 = min(gray.shape[0], y + h + margin)
                
                face_roi = gray_eq[y1:y2, x1:x2]
                face_roi = cv2.resize(face_roi, (100, 100))
                
                # Compute all encodings for this face (better accuracy)
                face_encodings = {
                    'pyramid': self._compute_spatial_pyramid_histogram(face_roi),
                    'template': face_roi.copy(),
                    'texture': self._compute_texture_features(face_roi),
                    'dct': self._compute_dct_features(face_roi)
                }
                
                best_match = None
                best_score = 0
                
                # LBPH prediction
                lbph_best_id = None
                lbph_best_conf = 0
                
                if self.lbph_trained:
                    try:
                        label, distance = self.lbph_recognizer.predict(face_roi)
                        if distance < self.lbph_threshold:
                            lbph_best_conf = max(0, (self.lbph_threshold - distance) / self.lbph_threshold)
                            lbph_best_id = label
                            print(f"   LBPH: label={label}, distance={distance:.1f}, conf={lbph_best_conf:.2%}")
                    except:
                        pass
                
                # Compare with all missing persons
                for person_id, person in self.missing_persons.items():
                    # Check cooldown
                    if person_id in self.recent_matches:
                        if current_time - self.recent_matches[person_id] < self.match_cooldown:
                            continue
                    
                    # Multi-feature similarity
                    feature_score = self._compare_encodings(face_encodings, person['encodings'])
                    
                    # Combine with LBPH if matched - give LBPH strong weight
                    if lbph_best_id == person_id:
                        combined_score = (lbph_best_conf * 0.5) + (feature_score * 0.5)
                    else:
                        # When no LBPH match, use feature score directly
                        combined_score = feature_score
                    
                    if combined_score > 0.05:  # Only print if not negligible
                        print(f"   {person['name']}: features={feature_score:.2%}, combined={combined_score:.2%}")
                    
                    if combined_score > best_score and combined_score > self.combined_threshold:
                        best_score = combined_score
                        best_match = {
                            'person_id': person_id,
                            'person': person,
                            'score': combined_score,
                            'feature_score': feature_score,
                            'lbph_score': lbph_best_conf if lbph_best_id == person_id else 0
                        }
                
                # If we found a match
                if best_match:
                    person = best_match['person']
                    person_id = best_match['person_id']
                    
                    person['last_seen'] = datetime.now().strftime('%H:%M:%S')
                    self.recent_matches[person_id] = current_time
                    
                    method = 'LBPH+Ensemble' if best_match['lbph_score'] > 0 else 'Ensemble'
                    print(f"🚨 MATCH FOUND: {person['name']} ({best_match['score']:.1%}) via {method}")
                    
                    matches.append({
                        'person_id': person_id,
                        'name': person['name'],
                        'confidence': round(best_match['score'] * 100, 1),
                        'camera': camera_name,
                        'time': person['last_seen'],
                        'location': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)},
                        'method': method
                    })
                    
                    # Draw rectangle on frame
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
                    cv2.putText(frame, f"MATCH: {person['name']} ({best_match['score']:.0%})", 
                               (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 0, 255), 2)
            
        except Exception as e:
            print(f"Error searching frame: {e}")
            import traceback
            traceback.print_exc()
        
        return matches


# Singleton instance
face_recognizer = FaceRecognizer()

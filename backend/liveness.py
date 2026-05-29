import cv2
import numpy as np
import mediapipe as mp
import time
import os
from database import get_settings

# MediaPipe tasks imports
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Initialize Face Landmarker
model_path = os.path.join(os.path.dirname(__file__), 'face_landmarker.task')
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.FaceLandmarkerOptions(base_options=base_options,
                                       output_face_blendshapes=True,
                                       output_facial_transformation_matrixes=True,
                                       num_faces=1)
detector = vision.FaceLandmarker.create_from_options(options)

def get_thresholds():
    settings = get_settings()
    return {
        'blur_variance': float(settings.get('liveness_blur_variance', 50.0)),
        'depth_z_std': float(settings.get('liveness_depth_z_std', 0.02))
    }

def evaluate_challenge(detection_result, challenge_type):
    """
    Evaluates if the user has performed the requested challenge.
    Returns True if passed, False otherwise.
    """
    if not detection_result.face_landmarks:
        return False
        
    landmarks = detection_result.face_landmarks[0]
    
    # Evaluate expressions using blendshapes
    if challenge_type in ['smile', 'mouth_open', 'blink']:
        if not detection_result.face_blendshapes:
            return False
        blendshapes = detection_result.face_blendshapes[0]
        
        # Helper to get score by category name
        def get_score(name):
            for b in blendshapes:
                if b.category_name == name:
                    return b.score
            return 0.0
            
        if challenge_type == 'smile':
            # Both smile blendshapes should be active
            return get_score('mouthSmileLeft') > 0.5 and get_score('mouthSmileRight') > 0.5
            
        elif challenge_type == 'mouth_open':
            return get_score('jawOpen') > 0.3
            
        elif challenge_type == 'blink':
            # Check if eyes are closed
            return get_score('eyeBlinkLeft') > 0.5 and get_score('eyeBlinkRight') > 0.5

    # Evaluate head turn using 3D pose (Transformation Matrix)
    elif challenge_type in ['turn_left', 'turn_right']:
        if not detection_result.facial_transformation_matrixes:
            return False
        matrix = detection_result.facial_transformation_matrixes[0]
        # Extract yaw from the rotation matrix
        # matrix is 4x4. Elements (0,0), (1,0), (2,0) give the X axis.
        # R31 = matrix[0, 2] = sin(yaw) approx.
        yaw = np.arctan2(matrix[0, 2], matrix[2, 2])
        # Because the frontend camera is mirrored, physical left/right are flipped in the un-mirrored image
        if challenge_type == 'turn_left':
            return yaw > 0.25
        elif challenge_type == 'turn_right':
            return yaw < -0.25
            
    return False

def analyze_texture(image):
    """
    Checks for texture anomalies common in spoofing (e.g., blurry screens).
    Uses Laplacian variance to check focus/blur.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    thresholds = get_thresholds()
    is_live = variance > thresholds['blur_variance']
    
    return is_live, variance

def analyze_depth(landmarks):
    """
    Uses MediaPipe's Z-coordinates to estimate if the face is 3D or flat.
    A flat photo will have very little depth variation compared to a real 3D face.
    """
    z_coords = [landmark.z for landmark in landmarks]
    z_std = np.std(z_coords)
    
    thresholds = get_thresholds()
    is_live = z_std > thresholds['depth_z_std']
    
    return is_live, z_std

def verify(frame, challenge_type=None):
    """
    Main liveness verification function.
    Returns (True, "Live") if successful, (False, "Reason") otherwise.
    """
    try:
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 1. Texture Analysis (detect screens/blur)
        texture_live, variance = analyze_texture(frame)
        if not texture_live:
            return False, f"Texture validation failed (Blur variance: {variance:.1f})"
            
        # 2. Depth / 3D Analysis using Face Mesh
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = detector.detect(mp_image)
        
        if not detection_result.face_landmarks:
            return False, "No face detected for liveness check"
            
        landmarks = detection_result.face_landmarks[0]
        
        depth_live, z_std = analyze_depth(landmarks)
        if not depth_live:
            return False, f"Depth validation failed (Flat surface detected, Z-std: {z_std:.4f})"
            
        if challenge_type:
            if not evaluate_challenge(detection_result, challenge_type):
                return False, f"Challenge '{challenge_type}' not met"
                
        return True, "Live human verified"
        
    except Exception as e:
        print(f"Liveness error: {str(e)}")
        return False, f"Liveness check error: {str(e)}"

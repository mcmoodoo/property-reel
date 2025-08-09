"""Motion analysis utilities for camera movement detection."""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MotionAnalyzer:
    """Analyze camera motion between frames using optical flow."""
    
    def __init__(
        self,
        flow_method: str = 'farneback',
        feature_method: str = 'orb',
        min_features: int = 100
    ):
        """
        Initialize motion analyzer.
        
        Args:
            flow_method: Optical flow method ('farneback' or 'lucas_kanade')
            feature_method: Feature detection method ('orb', 'sift', 'fast')
            min_features: Minimum number of features to track
        """
        self.flow_method = flow_method
        self.feature_method = feature_method
        self.min_features = min_features
        
        # Initialize feature detector
        if feature_method == 'orb':
            self.detector = cv2.ORB_create(nfeatures=500)
        elif feature_method == 'sift':
            self.detector = cv2.SIFT_create(nfeatures=500)
        elif feature_method == 'fast':
            self.detector = cv2.FastFeatureDetector_create()
        else:
            raise ValueError(f"Unknown feature method: {feature_method}")
        
        # Lucas-Kanade parameters
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Farneback optical flow parameters
        self.farneback_params = dict(
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0
        )
        
        logger.info(f"Motion analyzer initialized with {flow_method} flow and {feature_method} features")
    
    def compute_optical_flow(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Compute dense optical flow between two frames.
        
        Args:
            frame1: First frame (BGR)
            frame2: Second frame (BGR)
            
        Returns:
            Tuple of (flow field, motion statistics)
        """
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        
        if self.flow_method == 'farneback':
            # Compute dense optical flow
            flow = cv2.calcOpticalFlowFarneback(
                gray1, gray2, None, **self.farneback_params
            )
        else:
            # Use sparse optical flow with good features to track
            corners = cv2.goodFeaturesToTrack(
                gray1,
                maxCorners=200,
                qualityLevel=0.01,
                minDistance=10
            )
            
            if corners is not None and len(corners) > 10:
                # Track features
                next_corners, status, _ = cv2.calcOpticalFlowPyrLK(
                    gray1, gray2, corners, None, **self.lk_params
                )
                
                # Filter good points
                good_old = corners[status == 1]
                good_new = next_corners[status == 1]
                
                # Convert sparse flow to dense approximation
                flow = self._sparse_to_dense_flow(
                    good_old, good_new, frame1.shape[:2]
                )
            else:
                # Fallback to zero flow
                flow = np.zeros((frame1.shape[0], frame1.shape[1], 2))
        
        # Calculate motion statistics
        stats = self._calculate_flow_statistics(flow)
        
        return flow, stats
    
    def _sparse_to_dense_flow(
        self,
        pts1: np.ndarray,
        pts2: np.ndarray,
        shape: Tuple[int, int]
    ) -> np.ndarray:
        """
        Convert sparse feature tracks to dense flow field approximation.
        
        Args:
            pts1: Points in first frame
            pts2: Points in second frame
            shape: Frame shape (height, width)
            
        Returns:
            Dense flow field
        """
        h, w = shape
        flow = np.zeros((h, w, 2), dtype=np.float32)
        
        if len(pts1) < 4:
            return flow
        
        # Calculate homography for global motion
        try:
            H, _ = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
            
            if H is not None:
                # Create grid of points
                xx, yy = np.meshgrid(np.arange(w), np.arange(h))
                pts_grid = np.stack([xx, yy, np.ones_like(xx)], axis=-1)
                
                # Apply homography
                pts_transformed = pts_grid @ H.T
                pts_transformed = pts_transformed[..., :2] / pts_transformed[..., 2:3]
                
                # Calculate flow
                flow = pts_transformed - pts_grid[..., :2]
        except:
            logger.warning("Failed to compute homography for sparse flow")
        
        return flow
    
    def _calculate_flow_statistics(self, flow: np.ndarray) -> Dict[str, float]:
        """
        Calculate statistics from optical flow field.
        
        Args:
            flow: Optical flow field (h, w, 2)
            
        Returns:
            Dictionary of motion statistics
        """
        # Calculate magnitude and angle
        magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
        angle = np.arctan2(flow[..., 1], flow[..., 0])
        
        # Basic statistics
        stats = {
            'mean_magnitude': float(np.mean(magnitude)),
            'std_magnitude': float(np.std(magnitude)),
            'max_magnitude': float(np.max(magnitude)),
            'median_magnitude': float(np.median(magnitude)),
        }
        
        # Motion direction analysis
        if stats['mean_magnitude'] > 0.5:  # Only if significant motion
            # Histogram of angles to detect dominant direction
            angle_hist, _ = np.histogram(angle[magnitude > 1], bins=8, range=(-np.pi, np.pi))
            dominant_direction_idx = np.argmax(angle_hist)
            stats['dominant_direction'] = float(dominant_direction_idx * np.pi / 4 - np.pi)
            stats['direction_consistency'] = float(np.max(angle_hist) / np.sum(angle_hist))
        else:
            stats['dominant_direction'] = 0.0
            stats['direction_consistency'] = 1.0
        
        # Detect motion patterns
        stats.update(self._detect_motion_patterns(flow, magnitude))
        
        return stats
    
    def _detect_motion_patterns(
        self,
        flow: np.ndarray,
        magnitude: np.ndarray
    ) -> Dict[str, float]:
        """
        Detect specific camera motion patterns.
        
        Args:
            flow: Optical flow field
            magnitude: Flow magnitude
            
        Returns:
            Dictionary of motion pattern scores
        """
        h, w = flow.shape[:2]
        patterns = {}
        
        # Detect zoom (radial flow)
        center_x, center_y = w // 2, h // 2
        xx, yy = np.meshgrid(np.arange(w) - center_x, np.arange(h) - center_y)
        radial_component = (flow[..., 0] * xx + flow[..., 1] * yy) / (np.sqrt(xx**2 + yy**2) + 1e-6)
        patterns['zoom_score'] = float(np.abs(np.mean(radial_component[magnitude > 1])) if np.any(magnitude > 1) else 0)
        
        # Detect rotation (tangential flow)
        tangential_component = (-flow[..., 0] * yy + flow[..., 1] * xx) / (np.sqrt(xx**2 + yy**2) + 1e-6)
        patterns['rotation_score'] = float(np.abs(np.mean(tangential_component[magnitude > 1])) if np.any(magnitude > 1) else 0)
        
        # Detect pan (horizontal uniform flow)
        patterns['pan_score'] = float(np.abs(np.mean(flow[..., 0])))
        
        # Detect tilt (vertical uniform flow)
        patterns['tilt_score'] = float(np.abs(np.mean(flow[..., 1])))
        
        # Detect shake (high frequency motion)
        if magnitude.size > 0:
            patterns['shake_score'] = float(np.std(magnitude) / (np.mean(magnitude) + 1e-6))
        else:
            patterns['shake_score'] = 0.0
        
        return patterns
    
    def analyze_motion_sequence(
        self,
        frames: List[np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Analyze motion across a sequence of frames.
        
        Args:
            frames: List of frames (BGR)
            
        Returns:
            Dictionary of motion metrics over time
        """
        if len(frames) < 2:
            return {}
        
        metrics = {
            'magnitude': [],
            'direction_consistency': [],
            'shake': [],
            'zoom': [],
            'pan': [],
            'tilt': [],
            'rotation': []
        }
        
        for i in range(len(frames) - 1):
            _, stats = self.compute_optical_flow(frames[i], frames[i + 1])
            
            metrics['magnitude'].append(stats['mean_magnitude'])
            metrics['direction_consistency'].append(stats.get('direction_consistency', 1.0))
            metrics['shake'].append(stats.get('shake_score', 0.0))
            metrics['zoom'].append(stats.get('zoom_score', 0.0))
            metrics['pan'].append(stats.get('pan_score', 0.0))
            metrics['tilt'].append(stats.get('tilt_score', 0.0))
            metrics['rotation'].append(stats.get('rotation_score', 0.0))
        
        # Convert to numpy arrays
        for key in metrics:
            metrics[key] = np.array(metrics[key])
        
        return metrics
    
    def calculate_motion_smoothness(
        self,
        motion_sequence: np.ndarray
    ) -> float:
        """
        Calculate smoothness score for motion sequence.
        
        Args:
            motion_sequence: Array of motion values over time
            
        Returns:
            Smoothness score (0-1, higher is smoother)
        """
        if len(motion_sequence) < 3:
            return 1.0
        
        # Calculate jerk (third derivative of position)
        velocity = np.diff(motion_sequence)
        acceleration = np.diff(velocity)
        jerk = np.diff(acceleration)
        
        # Normalize by motion magnitude
        motion_range = np.ptp(motion_sequence)
        if motion_range > 0:
            normalized_jerk = np.mean(np.abs(jerk)) / motion_range
            smoothness = 1.0 / (1.0 + normalized_jerk * 10)  # Scale factor
        else:
            smoothness = 1.0
        
        return float(np.clip(smoothness, 0, 1))
    
    def detect_motion_reversal(
        self,
        motion_sequence: np.ndarray,
        threshold: float = 0.1
    ) -> List[int]:
        """
        Detect points where motion direction reverses.
        
        Args:
            motion_sequence: Array of motion values
            threshold: Minimum change to consider as reversal
            
        Returns:
            List of frame indices where reversals occur
        """
        if len(motion_sequence) < 2:
            return []
        
        # Calculate velocity
        velocity = np.diff(motion_sequence)
        
        # Find sign changes in velocity
        sign_changes = np.where(np.diff(np.sign(velocity)))[0]
        
        # Filter by threshold
        reversals = []
        for idx in sign_changes:
            if idx > 0 and idx < len(velocity) - 1:
                change_magnitude = abs(velocity[idx] - velocity[idx + 1])
                if change_magnitude > threshold:
                    reversals.append(idx + 1)  # Adjust for diff offset
        
        return reversals
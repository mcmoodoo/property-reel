"""Shot boundary detection for video segmentation."""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ShotBoundaryDetector:
    """Detect shot boundaries and transitions in video."""
    
    def __init__(
        self,
        histogram_threshold: float = 0.4,
        edge_threshold: float = 0.3,
        motion_threshold: float = 10.0,
        min_shot_length: float = 1.0,
        fps: float = 3.0
    ):
        """
        Initialize shot boundary detector.
        
        Args:
            histogram_threshold: Threshold for histogram difference
            edge_threshold: Threshold for edge change ratio
            motion_threshold: Threshold for motion magnitude change
            min_shot_length: Minimum shot length in seconds
            fps: Frame rate of extracted frames
        """
        self.histogram_threshold = histogram_threshold
        self.edge_threshold = edge_threshold
        self.motion_threshold = motion_threshold
        self.min_shot_length = min_shot_length
        self.fps = fps
        self.min_shot_frames = int(min_shot_length * fps)
        
        logger.info(f"Shot boundary detector initialized with thresholds: "
                   f"hist={histogram_threshold:.2f}, edge={edge_threshold:.2f}, "
                   f"motion={motion_threshold:.1f}")
    
    def detect_boundaries(
        self,
        frame_paths: List[Path],
        use_motion: bool = True
    ) -> List[Tuple[int, float, str]]:
        """
        Detect shot boundaries in frame sequence.
        
        Args:
            frame_paths: List of frame paths
            use_motion: Whether to use motion analysis
            
        Returns:
            List of (frame_index, confidence, transition_type) tuples
        """
        if len(frame_paths) < 2:
            return []
        
        boundaries = []
        
        # Initialize metrics storage
        histogram_diffs = []
        edge_ratios = []
        motion_changes = [] if use_motion else None
        
        prev_frame = None
        prev_hist = None
        prev_edges = None
        prev_flow = None
        
        logger.info(f"Analyzing {len(frame_paths)} frames for shot boundaries")
        
        for i, frame_path in enumerate(frame_paths):
            frame = cv2.imread(str(frame_path))
            if frame is None:
                continue
            
            # Resize for faster processing
            height, width = frame.shape[:2]
            if width > 320:
                scale = 320 / width
                new_height = int(height * scale)
                frame_small = cv2.resize(frame, (320, new_height))
            else:
                frame_small = frame
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
            
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
            hist = hist.flatten() / hist.sum()
            
            # Calculate edges
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if prev_frame is not None:
                # Histogram difference
                hist_diff = self._histogram_distance(prev_hist, hist)
                histogram_diffs.append(hist_diff)
                
                # Edge change ratio
                edge_ratio = abs(edge_density - prev_edges) / (prev_edges + 1e-6)
                edge_ratios.append(edge_ratio)
                
                # Motion analysis
                if use_motion:
                    flow = cv2.calcOpticalFlowFarneback(
                        cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY),
                        gray,
                        None,
                        pyr_scale=0.5,
                        levels=1,
                        winsize=15,
                        iterations=1,
                        poly_n=5,
                        poly_sigma=1.2,
                        flags=0
                    )
                    
                    if prev_flow is not None:
                        # Calculate motion change
                        motion_change = np.mean(np.abs(flow - prev_flow))
                        motion_changes.append(motion_change)
                    
                    prev_flow = flow
            
            prev_frame = frame_small
            prev_hist = hist
            prev_edges = edge_density
        
        # Detect boundaries from metrics
        boundaries = self._find_boundaries(
            histogram_diffs,
            edge_ratios,
            motion_changes
        )
        
        # Filter boundaries by minimum shot length
        filtered_boundaries = self._filter_boundaries(boundaries)
        
        logger.info(f"Detected {len(filtered_boundaries)} shot boundaries")
        
        return filtered_boundaries
    
    def _histogram_distance(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """
        Calculate distance between two histograms.
        
        Args:
            hist1: First histogram
            hist2: Second histogram
            
        Returns:
            Distance value
        """
        # Use chi-square distance
        chi_square = np.sum((hist1 - hist2)**2 / (hist1 + hist2 + 1e-6))
        return chi_square / 2.0  # Normalize to 0-1 range
    
    def _find_boundaries(
        self,
        histogram_diffs: List[float],
        edge_ratios: List[float],
        motion_changes: Optional[List[float]]
    ) -> List[Tuple[int, float, str]]:
        """
        Find boundaries from metrics.
        
        Args:
            histogram_diffs: List of histogram differences
            edge_ratios: List of edge change ratios
            motion_changes: List of motion changes (optional)
            
        Returns:
            List of boundary detections
        """
        boundaries = []
        
        # Convert to numpy arrays
        hist_arr = np.array(histogram_diffs)
        edge_arr = np.array(edge_ratios)
        
        # Adaptive thresholds based on statistics
        hist_mean = np.mean(hist_arr)
        hist_std = np.std(hist_arr)
        adaptive_hist_threshold = hist_mean + 2 * hist_std
        
        edge_mean = np.mean(edge_arr)
        edge_std = np.std(edge_arr)
        adaptive_edge_threshold = edge_mean + 2 * edge_std
        
        # Use the more conservative threshold
        hist_threshold = max(self.histogram_threshold, adaptive_hist_threshold)
        edge_threshold = max(self.edge_threshold, adaptive_edge_threshold)
        
        for i in range(len(histogram_diffs)):
            confidence = 0.0
            transition_type = None
            
            # Check histogram difference
            if hist_arr[i] > hist_threshold:
                confidence += 0.5
                transition_type = "cut"
            
            # Check edge ratio
            if edge_arr[i] > edge_threshold:
                confidence += 0.3
                if transition_type is None:
                    transition_type = "cut"
            
            # Check motion change
            if motion_changes and i < len(motion_changes):
                motion_val = motion_changes[i]
                if motion_val > self.motion_threshold:
                    confidence += 0.2
                    if transition_type is None:
                        transition_type = "motion_break"
            
            # Detect gradual transitions
            if i >= 2 and i < len(histogram_diffs) - 2:
                # Check for sustained change over multiple frames
                window_hist = hist_arr[i-2:i+3]
                window_edge = edge_arr[i-2:i+3]
                
                if np.mean(window_hist) > hist_threshold * 0.7:
                    transition_type = "dissolve"
                    confidence = min(confidence + 0.1, 1.0)
            
            # Add boundary if confidence is high enough
            if confidence >= 0.4:
                boundaries.append((i + 1, confidence, transition_type or "unknown"))
        
        return boundaries
    
    def _filter_boundaries(
        self,
        boundaries: List[Tuple[int, float, str]]
    ) -> List[Tuple[int, float, str]]:
        """
        Filter boundaries by minimum shot length.
        
        Args:
            boundaries: List of detected boundaries
            
        Returns:
            Filtered list of boundaries
        """
        if not boundaries:
            return boundaries
        
        filtered = []
        last_boundary = 0
        
        for frame_idx, confidence, trans_type in boundaries:
            if frame_idx - last_boundary >= self.min_shot_frames:
                filtered.append((frame_idx, confidence, trans_type))
                last_boundary = frame_idx
            else:
                logger.debug(f"Filtered out boundary at frame {frame_idx} "
                           f"(too close to previous: {frame_idx - last_boundary} frames)")
        
        return filtered
    
    def segment_into_shots(
        self,
        frame_paths: List[Path],
        boundaries: List[Tuple[int, float, str]]
    ) -> List[Dict[str, any]]:
        """
        Segment frames into shots based on boundaries.
        
        Args:
            frame_paths: List of frame paths
            boundaries: List of detected boundaries
            
        Returns:
            List of shot dictionaries
        """
        shots = []
        start_idx = 0
        
        for boundary_idx, confidence, trans_type in boundaries:
            if boundary_idx > start_idx:
                shot = {
                    'start_frame': start_idx,
                    'end_frame': boundary_idx - 1,
                    'start_time': start_idx / self.fps,
                    'end_time': (boundary_idx - 1) / self.fps,
                    'duration': (boundary_idx - start_idx) / self.fps,
                    'num_frames': boundary_idx - start_idx,
                    'transition_before': trans_type if start_idx > 0 else None,
                    'confidence': confidence if start_idx > 0 else 1.0
                }
                shots.append(shot)
                start_idx = boundary_idx
        
        # Add last shot
        if start_idx < len(frame_paths):
            shot = {
                'start_frame': start_idx,
                'end_frame': len(frame_paths) - 1,
                'start_time': start_idx / self.fps,
                'end_time': (len(frame_paths) - 1) / self.fps,
                'duration': (len(frame_paths) - start_idx) / self.fps,
                'num_frames': len(frame_paths) - start_idx,
                'transition_before': boundaries[-1][2] if boundaries else None,
                'confidence': boundaries[-1][1] if boundaries else 1.0
            }
            shots.append(shot)
        
        logger.info(f"Segmented into {len(shots)} shots")
        for i, shot in enumerate(shots):
            logger.debug(f"  Shot {i+1}: frames {shot['start_frame']}-{shot['end_frame']} "
                        f"({shot['duration']:.1f}s)")
        
        return shots
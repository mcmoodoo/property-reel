"""Temporal processing: smoothing and peak detection."""

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
import logging
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)


class TemporalProcessor:
    """Handle temporal smoothing and peak detection."""
    
    def __init__(
        self,
        smooth_window_seconds: float = 2.0,
        min_peak_distance_seconds: float = 4.0,
        fps: float = 3.0,
        motion_aware: bool = True,
        static_window_seconds: float = 3.0,
        dynamic_window_seconds: float = 1.5,
        motion_threshold: float = 2.0
    ):
        """
        Initialize temporal processor.
        
        Args:
            smooth_window_seconds: Default window size for smoothing in seconds
            min_peak_distance_seconds: Minimum distance between peaks in seconds
            fps: Frame rate of extracted frames
            motion_aware: Whether to use motion-aware smoothing
            static_window_seconds: Window size for static shots
            dynamic_window_seconds: Window size for dynamic shots
            motion_threshold: Threshold to distinguish static from dynamic
        """
        self.smooth_window_seconds = smooth_window_seconds
        self.min_peak_distance_seconds = min_peak_distance_seconds
        self.fps = fps
        self.motion_aware = motion_aware
        self.static_window_seconds = static_window_seconds
        self.dynamic_window_seconds = dynamic_window_seconds
        self.motion_threshold = motion_threshold
        
        # Convert to frame counts
        self.smooth_window_frames = int(smooth_window_seconds * fps)
        self.min_peak_distance_frames = int(min_peak_distance_seconds * fps)
        self.static_window_frames = int(static_window_seconds * fps)
        self.dynamic_window_frames = int(dynamic_window_seconds * fps)
        
        logger.info(f"Temporal processor initialized: "
                   f"smooth_window={self.smooth_window_frames} frames, "
                   f"min_peak_distance={self.min_peak_distance_frames} frames, "
                   f"motion_aware={motion_aware}")
    
    def smooth_scores(
        self, 
        scores: np.ndarray,
        motion_scores: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Apply temporal smoothing to scores.
        
        Args:
            scores: Array of per-frame scores
            motion_scores: Optional array of motion magnitudes for adaptive smoothing
            
        Returns:
            Smoothed scores
        """
        if len(scores) < self.dynamic_window_frames:
            logger.warning(f"Video too short for smoothing window "
                          f"({len(scores)} < {self.dynamic_window_frames} frames)")
            return scores
        
        if self.motion_aware and motion_scores is not None:
            # Motion-aware adaptive smoothing
            smoothed = self._adaptive_smooth(scores, motion_scores)
        else:
            # Standard uniform smoothing
            smoothed = uniform_filter1d(
                scores, 
                size=self.smooth_window_frames,
                mode='reflect'  # Handle edges by reflection
            )
        
        logger.info(f"Applied smoothing (motion_aware={self.motion_aware and motion_scores is not None})")
        logger.debug(f"Smoothing effect: std before={scores.std():.3f}, after={smoothed.std():.3f}")
        
        return smoothed
    
    def _adaptive_smooth(
        self,
        scores: np.ndarray,
        motion_scores: np.ndarray
    ) -> np.ndarray:
        """
        Apply adaptive smoothing based on motion.
        
        Args:
            scores: Array of scores
            motion_scores: Array of motion magnitudes
            
        Returns:
            Adaptively smoothed scores
        """
        smoothed = np.zeros_like(scores)
        
        for i in range(len(scores)):
            # Determine window size based on local motion
            if i < len(motion_scores):
                motion_level = motion_scores[i]
            else:
                motion_level = 0
            
            # Adaptive window size
            if motion_level < self.motion_threshold:
                # Static shot: use larger window
                window_size = self.static_window_frames
            else:
                # Dynamic shot: use smaller window
                window_size = self.dynamic_window_frames
            
            # Apply smoothing with adaptive window
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(scores), i + window_size // 2 + 1)
            smoothed[i] = np.mean(scores[start_idx:end_idx])
        
        return smoothed
    
    def find_peaks(
        self, 
        scores: np.ndarray,
        top_k: int = 5,
        min_prominence: Optional[float] = None
    ) -> List[Tuple[int, float]]:
        """
        Find peak moments in scores.
        
        Args:
            scores: Array of scores (preferably smoothed)
            top_k: Number of top peaks to return
            min_prominence: Minimum prominence for peaks (auto if None)
            
        Returns:
            List of (frame_index, score) tuples for peaks
        """
        if len(scores) == 0:
            return []
        
        # Auto-calculate prominence if not specified
        if min_prominence is None:
            min_prominence = scores.std() * 0.5
            logger.debug(f"Auto-calculated min_prominence: {min_prominence:.3f}")
        
        # Find peaks using scipy
        peak_indices, properties = signal.find_peaks(
            scores,
            distance=self.min_peak_distance_frames,
            prominence=min_prominence,
            height=np.percentile(scores, 25)  # At least in top 75%
        )
        
        if len(peak_indices) == 0:
            logger.warning("No peaks found, using maximum values instead")
            # Fallback: use argmax with minimum separation
            peak_indices = self._fallback_peak_finding(scores, top_k)
        
        # Get peak scores
        peak_scores = scores[peak_indices]
        
        # Sort by score and take top K
        sorted_indices = np.argsort(peak_scores)[::-1][:top_k]
        top_peaks = peak_indices[sorted_indices]
        
        # Create result list (sorted by time, not score)
        peaks = [(int(idx), float(scores[idx])) for idx in sorted(top_peaks)]
        
        logger.info(f"Found {len(peaks)} peaks out of {len(peak_indices)} candidates")
        for i, (idx, score) in enumerate(peaks):
            time_sec = idx / self.fps
            logger.debug(f"  Peak {i+1}: frame {idx} (t={time_sec:.1f}s), score={score:.3f}")
        
        return peaks
    
    def _fallback_peak_finding(self, scores: np.ndarray, top_k: int) -> np.ndarray:
        """
        Fallback method for finding peaks when scipy fails.
        
        Args:
            scores: Array of scores
            top_k: Number of peaks to find
            
        Returns:
            Array of peak indices
        """
        peaks = []
        remaining_scores = scores.copy()
        
        for _ in range(min(top_k, len(scores))):
            # Find maximum
            peak_idx = np.argmax(remaining_scores)
            peaks.append(peak_idx)
            
            # Suppress nearby values
            start = max(0, peak_idx - self.min_peak_distance_frames)
            end = min(len(scores), peak_idx + self.min_peak_distance_frames + 1)
            remaining_scores[start:end] = -np.inf
            
            # Check if any valid scores remain
            if np.all(np.isinf(remaining_scores)):
                break
        
        return np.array(peaks)
    
    def process(
        self, 
        scores: np.ndarray, 
        top_k: int = 5,
        motion_scores: Optional[np.ndarray] = None,
        shot_boundaries: Optional[List[int]] = None
    ) -> Tuple[np.ndarray, List[Tuple[int, float]]]:
        """
        Full temporal processing pipeline.
        
        Args:
            scores: Raw per-frame scores
            top_k: Number of clips to extract
            motion_scores: Optional motion scores for adaptive processing
            shot_boundaries: Optional list of shot boundary frame indices
            
        Returns:
            Tuple of (smoothed_scores, peaks)
        """
        # Apply smoothing
        smoothed = self.smooth_scores(scores, motion_scores)
        
        # Find peaks with shot awareness
        if shot_boundaries:
            peaks = self._find_peaks_with_shots(smoothed, top_k, shot_boundaries)
        else:
            peaks = self.find_peaks(smoothed, top_k)
        
        return smoothed, peaks
    
    def _find_peaks_with_shots(
        self,
        scores: np.ndarray,
        top_k: int,
        shot_boundaries: List[int]
    ) -> List[Tuple[int, float]]:
        """
        Find peaks while respecting shot boundaries.
        
        Args:
            scores: Array of scores
            top_k: Number of peaks to find
            shot_boundaries: List of shot boundary indices
            
        Returns:
            List of (frame_index, score) tuples
        """
        all_peaks = []
        
        # Add start and end boundaries
        boundaries = [0] + shot_boundaries + [len(scores)]
        
        # Find peaks within each shot
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            if end - start < self.min_peak_distance_frames:
                # Shot too short, use maximum
                if end > start:
                    max_idx = start + np.argmax(scores[start:end])
                    all_peaks.append((max_idx, scores[max_idx]))
            else:
                # Find peaks within shot
                shot_scores = scores[start:end]
                shot_peaks, _ = signal.find_peaks(
                    shot_scores,
                    distance=self.min_peak_distance_frames,
                    prominence=np.std(shot_scores) * 0.3
                )
                
                for peak_idx in shot_peaks:
                    global_idx = start + peak_idx
                    all_peaks.append((global_idx, scores[global_idx]))
        
        # Sort by score and take top K
        all_peaks.sort(key=lambda x: x[1], reverse=True)
        top_peaks = all_peaks[:top_k]
        
        # Sort by time for output
        top_peaks.sort(key=lambda x: x[0])
        
        logger.info(f"Found {len(top_peaks)} peaks across {len(boundaries)-1} shots")
        
        return top_peaks
    
    def get_peak_timestamps(self, peaks: List[Tuple[int, float]]) -> List[float]:
        """
        Convert peak frame indices to timestamps.
        
        Args:
            peaks: List of (frame_index, score) tuples
            
        Returns:
            List of timestamps in seconds
        """
        timestamps = [idx / self.fps for idx, _ in peaks]
        return timestamps
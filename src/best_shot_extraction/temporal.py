"""Temporal processing: smoothing and peak detection."""

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class TemporalProcessor:
    """Handle temporal smoothing and peak detection."""
    
    def __init__(
        self,
        smooth_window_seconds: float = 2.0,
        min_peak_distance_seconds: float = 4.0,
        fps: float = 3.0
    ):
        """
        Initialize temporal processor.
        
        Args:
            smooth_window_seconds: Window size for smoothing in seconds
            min_peak_distance_seconds: Minimum distance between peaks in seconds
            fps: Frame rate of extracted frames
        """
        self.smooth_window_seconds = smooth_window_seconds
        self.min_peak_distance_seconds = min_peak_distance_seconds
        self.fps = fps
        
        # Convert to frame counts
        self.smooth_window_frames = int(smooth_window_seconds * fps)
        self.min_peak_distance_frames = int(min_peak_distance_seconds * fps)
        
        logger.info(f"Temporal processor initialized: "
                   f"smooth_window={self.smooth_window_frames} frames, "
                   f"min_peak_distance={self.min_peak_distance_frames} frames")
    
    def smooth_scores(self, scores: np.ndarray) -> np.ndarray:
        """
        Apply temporal smoothing to scores.
        
        Args:
            scores: Array of per-frame scores
            
        Returns:
            Smoothed scores
        """
        if len(scores) < self.smooth_window_frames:
            logger.warning(f"Video too short for smoothing window "
                          f"({len(scores)} < {self.smooth_window_frames} frames)")
            return scores
        
        # Use uniform filter for moving average
        smoothed = uniform_filter1d(
            scores, 
            size=self.smooth_window_frames,
            mode='reflect'  # Handle edges by reflection
        )
        
        logger.info(f"Applied smoothing with window={self.smooth_window_frames} frames")
        logger.debug(f"Smoothing effect: std before={scores.std():.3f}, after={smoothed.std():.3f}")
        
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
        top_k: int = 5
    ) -> Tuple[np.ndarray, List[Tuple[int, float]]]:
        """
        Full temporal processing pipeline.
        
        Args:
            scores: Raw per-frame scores
            top_k: Number of clips to extract
            
        Returns:
            Tuple of (smoothed_scores, peaks)
        """
        # Apply smoothing
        smoothed = self.smooth_scores(scores)
        
        # Find peaks
        peaks = self.find_peaks(smoothed, top_k)
        
        return smoothed, peaks
    
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
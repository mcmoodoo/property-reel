"""Sharpness scoring using Laplacian variance."""

import cv2
import numpy as np
from pathlib import Path
import logging

from .base import BaseScorer

logger = logging.getLogger(__name__)


class SharpnessScorer(BaseScorer):
    """Score frames based on sharpness using variance of Laplacian."""
    
    def __init__(self, weight: float = 0.3):
        super().__init__(weight)
        self.scores_cache = []
        
    def score_frame(self, frame_path: Path) -> float:
        """
        Calculate sharpness score for a frame.
        
        Uses variance of Laplacian - higher variance indicates sharper image.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Sharpness score (not normalized)
        """
        # Read image in grayscale
        img = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            raise ValueError(f"Failed to read image: {frame_path}")
        
        # Calculate Laplacian
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        
        # Calculate variance
        variance = laplacian.var()
        
        # Store for later normalization
        self.scores_cache.append(variance)
        
        return variance
    
    def score_frames(self, frames):
        """Score frames and normalize."""
        # Get raw scores
        raw_scores = super().score_frames(frames)
        
        # Normalize to 0-1 range
        normalized = self.normalize_scores(raw_scores)
        
        # Clear cache
        self.scores_cache = []
        
        return normalized
    
    def is_blurry(self, frame_path: Path, threshold: float = 100.0) -> bool:
        """
        Check if frame is blurry.
        
        Args:
            frame_path: Path to frame
            threshold: Variance threshold below which image is considered blurry
            
        Returns:
            True if image is blurry
        """
        score = self.score_frame(frame_path)
        return score < threshold
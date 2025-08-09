"""Exposure quality scoring using histogram analysis."""

import cv2
import numpy as np
from pathlib import Path
import logging

from .base import BaseScorer

logger = logging.getLogger(__name__)


class ExposureScorer(BaseScorer):
    """Score frames based on exposure quality."""
    
    def __init__(
        self, 
        weight: float = -0.2,  # Negative weight since it's a penalty
        overexposed_threshold: float = 0.99,
        underexposed_threshold: float = 0.01,
        bright_pixel_value: int = 250,
        dark_pixel_value: int = 5
    ):
        super().__init__(weight)
        self.overexposed_threshold = overexposed_threshold
        self.underexposed_threshold = underexposed_threshold
        self.bright_pixel_value = bright_pixel_value
        self.dark_pixel_value = dark_pixel_value
        
    def score_frame(self, frame_path: Path) -> float:
        """
        Calculate exposure penalty for a frame.
        
        Returns higher penalty for over/underexposed images.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Exposure penalty (0 = perfect, 1 = terrible)
        """
        # Read image
        img = cv2.imread(str(frame_path))
        
        if img is None:
            raise ValueError(f"Failed to read image: {frame_path}")
        
        # Convert to grayscale for histogram analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()  # Normalize
        
        # Calculate percentage of very bright pixels
        bright_pixels = hist[self.bright_pixel_value:].sum()
        
        # Calculate percentage of very dark pixels  
        dark_pixels = hist[:self.dark_pixel_value].sum()
        
        # Calculate penalties
        overexposure_penalty = 0.0
        if bright_pixels > self.overexposed_threshold:
            overexposure_penalty = (bright_pixels - self.overexposed_threshold) / (1 - self.overexposed_threshold)
            
        underexposure_penalty = 0.0
        if dark_pixels > self.underexposed_threshold:
            underexposure_penalty = (dark_pixels - self.underexposed_threshold) / (1 - self.underexposed_threshold)
        
        # Combined penalty (take the maximum)
        penalty = max(overexposure_penalty, underexposure_penalty)
        
        # Also check for low contrast (most pixels in narrow range)
        # Calculate standard deviation of pixel values
        mean_val = np.average(np.arange(256), weights=hist)
        std_val = np.sqrt(np.average((np.arange(256) - mean_val)**2, weights=hist))
        
        # Low contrast penalty if std dev is too low
        if std_val < 30:  # Very low contrast
            contrast_penalty = (30 - std_val) / 30
            penalty = max(penalty, contrast_penalty * 0.5)  # Weight contrast less
        
        return penalty
    
    def analyze_exposure(self, frame_path: Path) -> dict:
        """
        Detailed exposure analysis.
        
        Returns:
            Dictionary with exposure metrics
        """
        img = cv2.imread(str(frame_path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        
        bright_pixels = hist[self.bright_pixel_value:].sum()
        dark_pixels = hist[:self.dark_pixel_value].sum()
        
        mean_val = np.average(np.arange(256), weights=hist)
        std_val = np.sqrt(np.average((np.arange(256) - mean_val)**2, weights=hist))
        
        return {
            "mean_brightness": mean_val,
            "std_brightness": std_val,
            "bright_pixel_ratio": bright_pixels,
            "dark_pixel_ratio": dark_pixels,
            "is_overexposed": bright_pixels > self.overexposed_threshold,
            "is_underexposed": dark_pixels > self.underexposed_threshold,
            "penalty": self.score_frame(frame_path)
        }
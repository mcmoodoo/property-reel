"""Base scorer interface."""

from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
from typing import Union, List
import logging

logger = logging.getLogger(__name__)


class BaseScorer(ABC):
    """Abstract base class for frame scorers."""
    
    def __init__(self, weight: float = 1.0):
        """
        Initialize scorer.
        
        Args:
            weight: Weight for this scorer in composite scoring
        """
        self.weight = weight
        
    @abstractmethod
    def score_frame(self, frame_path: Path) -> float:
        """
        Score a single frame.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Score between 0 and 1
        """
        pass
    
    def score_frames(self, frames: Union[Path, List[Path]]) -> np.ndarray:
        """
        Score multiple frames.
        
        Args:
            frames: Directory containing frames or list of frame paths
            
        Returns:
            Array of scores
        """
        if isinstance(frames, Path):
            if frames.is_dir():
                frame_paths = sorted(frames.glob("frame_*.jpg"))
            else:
                raise ValueError(f"Invalid path: {frames}")
        else:
            frame_paths = frames
            
        scores = []
        for i, frame_path in enumerate(frame_paths):
            try:
                score = self.score_frame(frame_path)
                scores.append(score)
                
                if (i + 1) % 50 == 0:
                    logger.debug(f"Scored {i + 1}/{len(frame_paths)} frames")
                    
            except Exception as e:
                logger.warning(f"Failed to score {frame_path}: {e}")
                scores.append(0.0)  # Default to low score on error
                
        return np.array(scores)
    
    def normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """
        Normalize scores to 0-1 range.
        
        Args:
            scores: Raw scores
            
        Returns:
            Normalized scores
        """
        if len(scores) == 0:
            return scores
            
        min_score = scores.min()
        max_score = scores.max()
        
        if max_score - min_score < 1e-6:
            # All scores are similar
            return np.ones_like(scores) * 0.5
            
        normalized = (scores - min_score) / (max_score - min_score)
        return normalized
"""Composite scorer that combines multiple scoring methods."""

import numpy as np
from pathlib import Path
import logging
from typing import Dict, Optional, List, Union

from .base import BaseScorer
from .sharpness import SharpnessScorer
from .exposure import ExposureScorer
from .aesthetics import AestheticsScorer
from .saliency import SaliencyScorer, VideoTypeScorer

logger = logging.getLogger(__name__)


class CompositeScorer:
    """Combine multiple scorers with configurable weights."""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        video_type: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Initialize composite scorer.
        
        Args:
            weights: Dictionary of scorer weights
            video_type: Type of video for specialized scoring
            use_cache: Whether to use cached embeddings
        """
        # Default weights
        default_weights = {
            "sharpness": 0.3,
            "exposure": -0.2,  # Negative because it's a penalty
            "aesthetics": 0.4,
            "saliency": 0.1
        }
        
        self.weights = weights or default_weights
        
        # Initialize individual scorers
        self.scorers = {}
        
        if "sharpness" in self.weights:
            self.scorers["sharpness"] = SharpnessScorer(
                weight=self.weights["sharpness"]
            )
        
        if "exposure" in self.weights:
            self.scorers["exposure"] = ExposureScorer(
                weight=self.weights["exposure"]
            )
        
        if "aesthetics" in self.weights:
            self.scorers["aesthetics"] = AestheticsScorer(
                weight=self.weights["aesthetics"],
                use_cache=use_cache
            )
        
        if "saliency" in self.weights:
            if video_type:
                self.scorers["saliency"] = VideoTypeScorer(
                    video_type=video_type,
                    weight=self.weights["saliency"]
                )
            else:
                self.scorers["saliency"] = SaliencyScorer(
                    weight=self.weights["saliency"]
                )
        
        # Normalize weights to sum to 1 (considering absolute values)
        total_weight = sum(abs(w) for w in self.weights.values())
        if total_weight > 0:
            for key in self.weights:
                self.weights[key] /= total_weight
                if key in self.scorers:
                    self.scorers[key].weight = self.weights[key]
        
        logger.info(f"Initialized composite scorer with weights: {self.weights}")
    
    def score_frames(self, frames: Union[Path, List[Path]]) -> np.ndarray:
        """
        Score frames using all enabled scorers.
        
        Args:
            frames: Directory containing frames or list of frame paths
            
        Returns:
            Array of composite scores
        """
        if isinstance(frames, Path):
            frame_paths = sorted(frames.glob("frame_*.jpg"))
        else:
            frame_paths = frames
        
        num_frames = len(frame_paths)
        logger.info(f"Scoring {num_frames} frames with {len(self.scorers)} scorers")
        
        # Collect scores from each scorer
        all_scores = {}
        
        for name, scorer in self.scorers.items():
            logger.info(f"Running {name} scorer...")
            scores = scorer.score_frames(frame_paths)
            all_scores[name] = scores
            
            # Log statistics
            logger.info(f"  {name}: mean={scores.mean():.3f}, std={scores.std():.3f}, "
                       f"min={scores.min():.3f}, max={scores.max():.3f}")
        
        # Combine scores
        composite_scores = np.zeros(num_frames)
        
        for name, scores in all_scores.items():
            weight = self.scorers[name].weight
            composite_scores += weight * scores
        
        # Ensure scores are in 0-1 range
        composite_scores = np.clip(composite_scores, 0, 1)
        
        logger.info(f"Composite scores: mean={composite_scores.mean():.3f}, "
                   f"std={composite_scores.std():.3f}, "
                   f"min={composite_scores.min():.3f}, "
                   f"max={composite_scores.max():.3f}")
        
        return composite_scores
    
    def get_score_components(self, frame_path: Path) -> Dict[str, float]:
        """
        Get individual score components for a single frame.
        
        Args:
            frame_path: Path to frame
            
        Returns:
            Dictionary of score components
        """
        components = {}
        
        for name, scorer in self.scorers.items():
            score = scorer.score_frame(frame_path)
            components[name] = score
            
        # Add composite score
        composite = sum(
            self.scorers[name].weight * score 
            for name, score in components.items()
        )
        components["composite"] = np.clip(composite, 0, 1)
        
        return components
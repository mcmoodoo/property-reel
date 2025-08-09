"""Camera motion quality scorer."""

import numpy as np
import cv2
from pathlib import Path
import logging
from typing import List, Dict, Optional, Union
import pickle

from .base import BaseScorer
from ..utils.motion import MotionAnalyzer

logger = logging.getLogger(__name__)


class MotionScorer(BaseScorer):
    """Score frames based on camera motion quality."""
    
    def __init__(
        self,
        weight: float = 0.3,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None,
        smoothness_weight: float = 0.4,
        stability_weight: float = 0.3,
        consistency_weight: float = 0.3,
        penalize_reversals: bool = True,
        reversal_penalty: float = 0.5,
        max_shake_threshold: float = 2.0,
        optimal_motion_range: tuple = (0.5, 5.0)
    ):
        """
        Initialize motion scorer.
        
        Args:
            weight: Weight for this scorer in composite
            use_cache: Whether to use cached motion analysis
            cache_dir: Directory for caching motion data
            smoothness_weight: Weight for motion smoothness
            stability_weight: Weight for motion stability (lack of shake)
            consistency_weight: Weight for motion consistency
            penalize_reversals: Whether to penalize motion reversals
            reversal_penalty: Penalty factor for motion reversals
            max_shake_threshold: Maximum acceptable shake score
            optimal_motion_range: Range of optimal motion magnitude
        """
        super().__init__(weight)
        self.use_cache = use_cache
        self.cache_dir = cache_dir or Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # Scoring weights
        self.smoothness_weight = smoothness_weight
        self.stability_weight = stability_weight
        self.consistency_weight = consistency_weight
        
        # Penalty parameters
        self.penalize_reversals = penalize_reversals
        self.reversal_penalty = reversal_penalty
        self.max_shake_threshold = max_shake_threshold
        self.optimal_motion_range = optimal_motion_range
        
        # Normalize weights
        total_weight = smoothness_weight + stability_weight + consistency_weight
        self.smoothness_weight /= total_weight
        self.stability_weight /= total_weight
        self.consistency_weight /= total_weight
        
        # Initialize motion analyzer
        self.analyzer = MotionAnalyzer()
        
        logger.info(f"Motion scorer initialized with weights: "
                   f"smoothness={self.smoothness_weight:.2f}, "
                   f"stability={self.stability_weight:.2f}, "
                   f"consistency={self.consistency_weight:.2f}")
    
    def score_frames(self, frames: Union[Path, List[Path]]) -> np.ndarray:
        """
        Score frames based on motion quality.
        
        Args:
            frames: Directory containing frames or list of frame paths
            
        Returns:
            Array of motion quality scores
        """
        if isinstance(frames, Path):
            frame_paths = sorted(frames.glob("frame_*.jpg"))
        else:
            frame_paths = frames
        
        if len(frame_paths) < 2:
            logger.warning("Not enough frames for motion analysis")
            return np.ones(len(frame_paths))
        
        # Check cache
        cache_key = self._get_cache_key(frame_paths)
        cache_path = self.cache_dir / f"motion_{cache_key}.pkl"
        
        if self.use_cache and cache_path.exists():
            logger.info(f"Loading cached motion scores from {cache_path}")
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        
        logger.info(f"Analyzing motion for {len(frame_paths)} frames")
        
        # Load frames in batches to avoid memory issues
        batch_size = 30
        all_metrics = {
            'magnitude': [],
            'direction_consistency': [],
            'shake': [],
            'zoom': [],
            'pan': [],
            'tilt': [],
            'rotation': []
        }
        
        for i in range(0, len(frame_paths) - 1, batch_size):
            batch_end = min(i + batch_size + 1, len(frame_paths))
            batch_frames = []
            
            for j in range(i, batch_end):
                frame = cv2.imread(str(frame_paths[j]))
                if frame is not None:
                    # Resize for faster processing
                    height, width = frame.shape[:2]
                    if width > 640:
                        scale = 640 / width
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (640, new_height))
                    batch_frames.append(frame)
            
            if len(batch_frames) >= 2:
                batch_metrics = self.analyzer.analyze_motion_sequence(batch_frames)
                for key in all_metrics:
                    if key in batch_metrics:
                        all_metrics[key].extend(batch_metrics[key])
        
        # Convert to numpy arrays
        for key in all_metrics:
            all_metrics[key] = np.array(all_metrics[key])
        
        # Calculate scores
        scores = self._calculate_motion_scores(all_metrics, len(frame_paths))
        
        # Cache results
        if self.use_cache:
            with open(cache_path, 'wb') as f:
                pickle.dump(scores, f)
            logger.debug(f"Cached motion scores to {cache_path}")
        
        return scores
    
    def _calculate_motion_scores(
        self,
        metrics: Dict[str, np.ndarray],
        num_frames: int
    ) -> np.ndarray:
        """
        Calculate motion quality scores from metrics.
        
        Args:
            metrics: Dictionary of motion metrics
            num_frames: Total number of frames
            
        Returns:
            Array of motion scores
        """
        scores = np.ones(num_frames)
        
        if len(metrics['magnitude']) == 0:
            return scores
        
        # Ensure we have values for all frames (duplicate last value)
        motion_magnitude = np.concatenate([metrics['magnitude'], [metrics['magnitude'][-1]]])
        direction_consistency = np.concatenate([metrics['direction_consistency'], [metrics['direction_consistency'][-1]]])
        shake = np.concatenate([metrics['shake'], [metrics['shake'][-1]]])
        
        # Calculate component scores
        for i in range(num_frames):
            # Get motion metrics for this frame
            if i < len(motion_magnitude):
                mag = motion_magnitude[i]
                consistency = direction_consistency[i]
                shake_val = shake[i]
            else:
                mag = motion_magnitude[-1]
                consistency = direction_consistency[-1]
                shake_val = shake[-1]
            
            # Smoothness score (analyze local window)
            smoothness_score = 1.0
            if i >= 2 and i < len(motion_magnitude) - 2:
                window = motion_magnitude[max(0, i-2):min(len(motion_magnitude), i+3)]
                smoothness_score = self.analyzer.calculate_motion_smoothness(window)
            
            # Stability score (inverse of shake)
            stability_score = 1.0 / (1.0 + shake_val / self.max_shake_threshold)
            
            # Consistency score (direction consistency)
            consistency_score = consistency
            
            # Motion magnitude score (prefer optimal range)
            if mag < self.optimal_motion_range[0]:
                magnitude_score = mag / self.optimal_motion_range[0]
            elif mag > self.optimal_motion_range[1]:
                magnitude_score = self.optimal_motion_range[1] / mag
            else:
                magnitude_score = 1.0
            
            # Combine scores
            frame_score = (
                self.smoothness_weight * smoothness_score +
                self.stability_weight * stability_score +
                self.consistency_weight * consistency_score
            )
            
            # Apply magnitude modulation
            frame_score *= magnitude_score
            
            # Check for motion reversals
            if self.penalize_reversals and i >= 3 and i < len(motion_magnitude) - 1:
                window = motion_magnitude[i-3:i+2]
                reversals = self.analyzer.detect_motion_reversal(window, threshold=0.5)
                if len(reversals) > 0:
                    frame_score *= (1.0 - self.reversal_penalty)
                    logger.debug(f"Motion reversal detected at frame {i}")
            
            scores[i] = np.clip(frame_score, 0, 1)
        
        # Apply temporal smoothing to scores
        from scipy.ndimage import uniform_filter1d
        scores = uniform_filter1d(scores, size=5, mode='nearest')
        
        logger.info(f"Motion scores: mean={scores.mean():.3f}, std={scores.std():.3f}")
        
        return scores
    
    def _get_cache_key(self, frame_paths: List[Path]) -> str:
        """
        Generate cache key from frame paths.
        
        Args:
            frame_paths: List of frame paths
            
        Returns:
            Cache key string
        """
        # Use first, middle, and last frame names for key
        if len(frame_paths) >= 3:
            key_frames = [
                frame_paths[0].stem,
                frame_paths[len(frame_paths)//2].stem,
                frame_paths[-1].stem
            ]
        else:
            key_frames = [p.stem for p in frame_paths]
        
        return "_".join(key_frames)
    
    def analyze_clip_motion(
        self,
        frame_paths: List[Path],
        start_idx: int,
        end_idx: int
    ) -> Dict[str, float]:
        """
        Analyze motion quality for a specific clip.
        
        Args:
            frame_paths: List of all frame paths
            start_idx: Start frame index
            end_idx: End frame index
            
        Returns:
            Dictionary of motion analysis results
        """
        clip_frames = []
        for i in range(start_idx, min(end_idx + 1, len(frame_paths))):
            frame = cv2.imread(str(frame_paths[i]))
            if frame is not None:
                # Resize for faster processing
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (640, new_height))
                clip_frames.append(frame)
        
        if len(clip_frames) < 2:
            return {
                'motion_quality': 0.0,
                'has_reversal': False,
                'smoothness': 1.0,
                'stability': 1.0
            }
        
        # Analyze motion
        metrics = self.analyzer.analyze_motion_sequence(clip_frames)
        
        # Calculate overall quality
        smoothness = self.analyzer.calculate_motion_smoothness(metrics['magnitude'])
        stability = 1.0 / (1.0 + np.mean(metrics['shake']) / self.max_shake_threshold)
        consistency = np.mean(metrics['direction_consistency'])
        
        # Check for reversals
        reversals = self.analyzer.detect_motion_reversal(metrics['magnitude'])
        has_reversal = len(reversals) > 0
        
        # Overall quality
        quality = (
            self.smoothness_weight * smoothness +
            self.stability_weight * stability +
            self.consistency_weight * consistency
        )
        
        if has_reversal and self.penalize_reversals:
            quality *= (1.0 - self.reversal_penalty)
        
        return {
            'motion_quality': float(quality),
            'has_reversal': has_reversal,
            'smoothness': float(smoothness),
            'stability': float(stability),
            'consistency': float(consistency),
            'mean_magnitude': float(np.mean(metrics['magnitude'])),
            'shake_level': float(np.mean(metrics['shake']))
        }
    
    def score_frame(self, frame_path: Path) -> float:
        """
        Score a single frame (required by BaseScorer).
        
        Note: Motion scoring requires multiple frames, so this returns a default score.
        
        Args:
            frame_path: Path to frame
            
        Returns:
            Default score of 0.5 (motion cannot be assessed from single frame)
        """
        # Motion cannot be assessed from a single frame
        return 0.5
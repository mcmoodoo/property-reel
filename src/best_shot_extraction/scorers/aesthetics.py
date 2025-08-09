"""Aesthetic scoring using CLIP embeddings."""

import numpy as np
from pathlib import Path
import logging
import pickle
from typing import Optional

from .base import BaseScorer
from ..models import CLIPModelSingleton

logger = logging.getLogger(__name__)


class AestheticsScorer(BaseScorer):
    """Score frames based on aesthetic quality using CLIP."""
    
    def __init__(
        self, 
        weight: float = 0.4,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True
    ):
        super().__init__(weight)
        self.clip_model = CLIPModelSingleton()
        self.cache_dir = Path(cache_dir) if cache_dir else Path("cache")
        self.use_cache = use_cache
        self.cache_dir.mkdir(exist_ok=True)
        
    def _get_cache_path(self, frame_path: Path) -> Path:
        """Get cache file path for a frame."""
        cache_name = f"aesthetic_{frame_path.stem}.pkl"
        return self.cache_dir / cache_name
    
    def _load_from_cache(self, frame_path: Path) -> Optional[float]:
        """Try to load score from cache."""
        if not self.use_cache:
            return None
            
        cache_path = self._get_cache_path(frame_path)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_path}: {e}")
        return None
    
    def _save_to_cache(self, frame_path: Path, score: float):
        """Save score to cache."""
        if not self.use_cache:
            return
            
        cache_path = self._get_cache_path(frame_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(score, f)
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_path}: {e}")
    
    def score_frame(self, frame_path: Path) -> float:
        """
        Calculate aesthetic score for a frame.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Aesthetic score between 0 and 1
        """
        # Check cache
        cached_score = self._load_from_cache(frame_path)
        if cached_score is not None:
            return cached_score
        
        # Get CLIP embedding
        embedding = self.clip_model.encode_image(frame_path)
        
        # Calculate aesthetic score
        score = self.clip_model.get_aesthetic_score(embedding)
        
        # Save to cache
        self._save_to_cache(frame_path, score)
        
        return score
    
    def score_frames(self, frames):
        """Score multiple frames efficiently using batch processing."""
        if isinstance(frames, Path):
            frame_paths = sorted(frames.glob("frame_*.jpg"))
        else:
            frame_paths = frames
        
        scores = []
        uncached_indices = []
        uncached_paths = []
        
        # Check cache first
        for i, frame_path in enumerate(frame_paths):
            cached_score = self._load_from_cache(frame_path)
            if cached_score is not None:
                scores.append(cached_score)
            else:
                scores.append(0.0)  # Placeholder
                uncached_indices.append(i)
                uncached_paths.append(frame_path)
        
        # Process uncached frames in batches
        if uncached_paths:
            logger.info(f"Processing {len(uncached_paths)} uncached frames")
            
            # Get embeddings in batches
            batch_size = 4 if self.clip_model._device == "cpu" else 16
            embeddings = self.clip_model.encode_images_batch(uncached_paths, batch_size)
            
            # Calculate aesthetic scores
            for i, (idx, path, embedding) in enumerate(zip(uncached_indices, uncached_paths, embeddings)):
                score = self.clip_model.get_aesthetic_score(embedding)
                scores[idx] = score
                self._save_to_cache(path, score)
                
                if (i + 1) % 50 == 0:
                    logger.debug(f"Scored {i + 1}/{len(uncached_paths)} aesthetic frames")
        
        return np.array(scores)
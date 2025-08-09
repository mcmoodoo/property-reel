"""Diversity filtering to remove near-duplicate clips."""

import numpy as np
from pathlib import Path
import logging
from typing import List, Tuple, Optional
import pickle

from .models import CLIPModelSingleton

logger = logging.getLogger(__name__)


class DiversityFilter:
    """Filter clips to ensure diversity using CLIP embeddings."""
    
    def __init__(
        self,
        similarity_threshold: float = 0.12,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True
    ):
        """
        Initialize diversity filter.
        
        Args:
            similarity_threshold: Maximum cosine distance for clips to be considered different
            cache_dir: Directory for caching embeddings
            use_cache: Whether to use cached embeddings
        """
        self.similarity_threshold = similarity_threshold
        self.clip_model = CLIPModelSingleton()
        self.cache_dir = Path(cache_dir) if cache_dir else Path("cache")
        self.use_cache = use_cache
        self.cache_dir.mkdir(exist_ok=True)
        
        logger.info(f"Diversity filter initialized: threshold={similarity_threshold}")
    
    def _get_embedding_cache_path(self, frame_path: Path) -> Path:
        """Get cache path for frame embedding."""
        cache_name = f"embedding_{frame_path.stem}.pkl"
        return self.cache_dir / cache_name
    
    def _load_embedding_from_cache(self, frame_path: Path) -> Optional[np.ndarray]:
        """Load cached embedding if available."""
        if not self.use_cache:
            return None
            
        cache_path = self._get_embedding_cache_path(frame_path)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")
        return None
    
    def _save_embedding_to_cache(self, frame_path: Path, embedding: np.ndarray):
        """Save embedding to cache."""
        if not self.use_cache:
            return
            
        cache_path = self._get_embedding_cache_path(frame_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")
    
    def get_frame_embeddings(
        self,
        frame_paths: List[Path]
    ) -> np.ndarray:
        """
        Get CLIP embeddings for frames.
        
        Args:
            frame_paths: List of frame image paths
            
        Returns:
            Array of embeddings (N x embedding_dim)
        """
        embeddings = []
        uncached_indices = []
        uncached_paths = []
        
        # Check cache first
        for i, path in enumerate(frame_paths):
            cached = self._load_embedding_from_cache(path)
            if cached is not None:
                embeddings.append(cached)
            else:
                embeddings.append(None)
                uncached_indices.append(i)
                uncached_paths.append(path)
        
        # Compute uncached embeddings
        if uncached_paths:
            logger.info(f"Computing {len(uncached_paths)} uncached embeddings")
            batch_size = 4 if self.clip_model._device == "cpu" else 16
            new_embeddings = self.clip_model.encode_images_batch(uncached_paths, batch_size)
            
            # Fill in and cache
            for idx, path, emb in zip(uncached_indices, uncached_paths, new_embeddings):
                embeddings[idx] = emb
                self._save_embedding_to_cache(path, emb)
        
        return np.vstack(embeddings)
    
    def compute_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Compute pairwise cosine similarities.
        
        Args:
            embeddings: Array of embeddings (N x D)
            
        Returns:
            Similarity matrix (N x N)
        """
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-8)
        
        # Compute cosine similarity matrix
        similarity_matrix = normalized @ normalized.T
        
        # Convert to distance (1 - similarity)
        distance_matrix = 1 - similarity_matrix
        
        return distance_matrix
    
    def filter_diverse(
        self,
        peaks: List[Tuple[int, float]],
        frame_paths: List[Path],
        max_clips: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Filter peaks to ensure diversity.
        
        Args:
            peaks: List of (frame_index, score) tuples sorted by score
            frame_paths: List of all frame paths
            max_clips: Maximum number of clips to return
            
        Returns:
            Filtered list of diverse peaks
        """
        if len(peaks) <= 1:
            return peaks
        
        # Get frame paths for peaks
        peak_frame_paths = [frame_paths[idx] for idx, _ in peaks]
        
        # Get embeddings
        logger.info(f"Computing embeddings for {len(peak_frame_paths)} peak frames")
        embeddings = self.get_frame_embeddings(peak_frame_paths)
        
        # Compute distance matrix
        distance_matrix = self.compute_similarity_matrix(embeddings)
        
        # Greedy selection
        selected_indices = []
        selected_peaks = []
        
        # Sort peaks by score (descending)
        sorted_peak_indices = sorted(range(len(peaks)), key=lambda i: peaks[i][1], reverse=True)
        
        for i in sorted_peak_indices:
            # Check if this peak is diverse enough from all selected
            is_diverse = True
            
            for j in selected_indices:
                if distance_matrix[i, j] < self.similarity_threshold:
                    is_diverse = False
                    logger.debug(f"Peak {i} too similar to {j} "
                               f"(distance={distance_matrix[i, j]:.3f})")
                    break
            
            if is_diverse:
                selected_indices.append(i)
                selected_peaks.append(peaks[i])
                logger.debug(f"Selected peak {i} (frame {peaks[i][0]}, score={peaks[i][1]:.3f})")
                
                if max_clips and len(selected_peaks) >= max_clips:
                    break
        
        # Sort selected peaks by time (frame index)
        selected_peaks.sort(key=lambda x: x[0])
        
        logger.info(f"Filtered {len(peaks)} peaks to {len(selected_peaks)} diverse clips")
        
        # Log similarity statistics
        if len(selected_indices) > 1:
            selected_distances = []
            for i in range(len(selected_indices)):
                for j in range(i + 1, len(selected_indices)):
                    selected_distances.append(
                        distance_matrix[selected_indices[i], selected_indices[j]]
                    )
            logger.info(f"Average distance between selected clips: {np.mean(selected_distances):.3f}")
        
        return selected_peaks
    
    def analyze_diversity(
        self,
        peaks: List[Tuple[int, float]],
        frame_paths: List[Path]
    ) -> dict:
        """
        Analyze diversity of peaks without filtering.
        
        Args:
            peaks: List of (frame_index, score) tuples
            frame_paths: List of all frame paths
            
        Returns:
            Dictionary with diversity statistics
        """
        if len(peaks) <= 1:
            return {
                "num_clips": len(peaks),
                "min_distance": 0,
                "max_distance": 0,
                "mean_distance": 0,
                "num_similar_pairs": 0
            }
        
        # Get embeddings
        peak_frame_paths = [frame_paths[idx] for idx, _ in peaks]
        embeddings = self.get_frame_embeddings(peak_frame_paths)
        
        # Compute distances
        distance_matrix = self.compute_similarity_matrix(embeddings)
        
        # Extract upper triangle (excluding diagonal)
        upper_triangle_indices = np.triu_indices(len(peaks), k=1)
        pairwise_distances = distance_matrix[upper_triangle_indices]
        
        # Count similar pairs
        num_similar = np.sum(pairwise_distances < self.similarity_threshold)
        
        return {
            "num_clips": len(peaks),
            "min_distance": float(pairwise_distances.min()),
            "max_distance": float(pairwise_distances.max()),
            "mean_distance": float(pairwise_distances.mean()),
            "std_distance": float(pairwise_distances.std()),
            "num_similar_pairs": int(num_similar),
            "similarity_threshold": self.similarity_threshold
        }
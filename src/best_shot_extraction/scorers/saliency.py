"""Saliency/subject scoring using CLIP text-image similarity."""

import numpy as np
from pathlib import Path
import logging
from typing import Optional, List

from .base import BaseScorer
from ..models import CLIPModelSingleton

logger = logging.getLogger(__name__)


class SaliencyScorer(BaseScorer):
    """Score frames based on similarity to text prompts using CLIP."""
    
    def __init__(
        self, 
        weight: float = 0.1,
        prompts: Optional[List[str]] = None
    ):
        super().__init__(weight)
        self.clip_model = CLIPModelSingleton()
        
        # Default prompts for different video types
        self.prompts = prompts or [
            "a well-composed shot",
            "interesting subject in focus",
            "professional cinematography"
        ]
        
        # Pre-encode text prompts
        self._encode_prompts()
    
    def _encode_prompts(self):
        """Pre-encode text prompts for efficiency."""
        logger.info(f"Encoding {len(self.prompts)} text prompts")
        self.text_embeddings = []
        for prompt in self.prompts:
            embedding = self.clip_model.encode_text(prompt)
            self.text_embeddings.append(embedding)
    
    def set_prompts(self, prompts: List[str]):
        """
        Update text prompts for scoring.
        
        Args:
            prompts: List of text descriptions
        """
        self.prompts = prompts
        self._encode_prompts()
    
    def score_frame(self, frame_path: Path) -> float:
        """
        Calculate saliency score based on text similarity.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Saliency score between 0 and 1
        """
        # Get image embedding
        image_embedding = self.clip_model.encode_image(frame_path)
        
        # Calculate similarities with all prompts
        similarities = []
        for text_embedding in self.text_embeddings:
            sim = self.clip_model.compute_similarity(image_embedding, text_embedding)
            similarities.append(sim)
        
        # Take maximum similarity (best match to any prompt)
        max_similarity = max(similarities)
        
        # Convert to 0-1 range (CLIP similarities are typically -1 to 1)
        score = (max_similarity + 1) / 2
        score = np.clip(score, 0, 1)
        
        return float(score)
    
    def score_frames_with_prompt(self, frames, prompt: str) -> np.ndarray:
        """
        Score frames with a specific prompt.
        
        Args:
            frames: Directory or list of frame paths
            prompt: Text description to match
            
        Returns:
            Array of scores
        """
        # Temporarily set single prompt
        original_prompts = self.prompts
        self.set_prompts([prompt])
        
        # Score frames
        scores = self.score_frames(frames)
        
        # Restore original prompts
        self.prompts = original_prompts
        self._encode_prompts()
        
        return scores


class VideoTypeScorer(SaliencyScorer):
    """Specialized saliency scorer with presets for different video types."""
    
    VIDEO_TYPE_PROMPTS = {
        "aerial": [
            "aerial landscape photography",
            "drone shot with beautiful scenery",
            "bird's eye view of landscape",
            "sweeping aerial vista",
            "dramatic aerial perspective"
        ],
        "interior": [
            "well-lit interior space",
            "architectural interior photography", 
            "beautifully composed room",
            "professional real estate photo",
            "inviting indoor space"
        ],
        "portrait": [
            "professional portrait photography",
            "person in focus with good lighting",
            "engaging human subject",
            "well-composed portrait shot",
            "sharp focus on face"
        ],
        "action": [
            "dynamic action shot",
            "exciting moment captured",
            "sports photography",
            "movement and energy",
            "peak action moment"
        ],
        "nature": [
            "beautiful nature photography",
            "wildlife in natural habitat",
            "stunning natural landscape",
            "golden hour lighting in nature",
            "pristine wilderness scene"
        ]
    }
    
    def __init__(self, video_type: str = "general", weight: float = 0.2):
        """
        Initialize with video type specific prompts.
        
        Args:
            video_type: Type of video (aerial, interior, portrait, action, nature, general)
            weight: Scorer weight
        """
        prompts = self.VIDEO_TYPE_PROMPTS.get(video_type, None)
        super().__init__(weight=weight, prompts=prompts)
        self.video_type = video_type
        logger.info(f"Initialized {video_type} video scorer with {len(self.prompts)} prompts")
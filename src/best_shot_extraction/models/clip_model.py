"""Singleton CLIP model for efficient reuse across scorers."""

import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import numpy as np
from pathlib import Path
import logging
from typing import Optional, List, Union

logger = logging.getLogger(__name__)


class CLIPModelSingleton:
    """Singleton pattern for CLIP model to avoid multiple loads."""
    
    _instance = None
    _model = None
    _processor = None
    _device = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """Initialize CLIP model (only once)."""
        if self._model is None:
            logger.info(f"Loading CLIP model: {model_name}")
            
            # Detect device (CPU for this project)
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self._device}")
            
            # Load model and processor
            self._model = CLIPModel.from_pretrained(model_name)
            self._processor = CLIPProcessor.from_pretrained(model_name)
            
            # Move model to device
            self._model = self._model.to(self._device)
            self._model.eval()  # Set to evaluation mode
            
            logger.info("CLIP model loaded successfully")
    
    def encode_image(self, image_path: Union[Path, str]) -> np.ndarray:
        """
        Encode a single image to CLIP embedding.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Image embedding as numpy array
        """
        image = Image.open(image_path).convert("RGB")
        
        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        
        with torch.no_grad():
            image_features = self._model.get_image_features(**inputs)
            
        # Normalize and convert to numpy
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features.cpu().numpy().squeeze()
    
    def encode_images_batch(self, image_paths: List[Path], batch_size: int = 4) -> np.ndarray:
        """
        Encode multiple images in batches.
        
        Args:
            image_paths: List of image paths
            batch_size: Batch size for processing
            
        Returns:
            Array of embeddings
        """
        embeddings = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            batch_images = [Image.open(p).convert("RGB") for p in batch_paths]
            
            inputs = self._processor(images=batch_images, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            with torch.no_grad():
                batch_features = self._model.get_image_features(**inputs)
                
            # Normalize
            batch_features = batch_features / batch_features.norm(dim=-1, keepdim=True)
            embeddings.append(batch_features.cpu().numpy())
            
            if (i + batch_size) % 20 == 0:
                logger.debug(f"Encoded {min(i + batch_size, len(image_paths))}/{len(image_paths)} images")
        
        return np.vstack(embeddings)
    
    def encode_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Encode text to CLIP embedding.
        
        Args:
            text: Text or list of texts to encode
            
        Returns:
            Text embedding(s) as numpy array
        """
        inputs = self._processor(text=text, return_tensors="pt", padding=True)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        
        with torch.no_grad():
            text_features = self._model.get_text_features(**inputs)
            
        # Normalize
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().numpy().squeeze()
    
    def compute_similarity(self, image_embedding: np.ndarray, text_embedding: np.ndarray) -> float:
        """
        Compute cosine similarity between image and text embeddings.
        
        Args:
            image_embedding: Image embedding
            text_embedding: Text embedding
            
        Returns:
            Cosine similarity score
        """
        # Ensure 1D arrays
        image_embedding = image_embedding.flatten()
        text_embedding = text_embedding.flatten()
        
        # Compute cosine similarity
        similarity = np.dot(image_embedding, text_embedding)
        return float(similarity)
    
    def get_aesthetic_score(self, image_embedding: np.ndarray) -> float:
        """
        Estimate aesthetic score from CLIP embedding.
        
        This is a simplified version - in production you'd use a trained aesthetic predictor.
        
        Args:
            image_embedding: CLIP image embedding
            
        Returns:
            Aesthetic score between 0 and 1
        """
        # Simple heuristic: compare to aesthetic text prompts
        aesthetic_prompts = [
            "a beautiful photograph",
            "professional photography", 
            "high quality image",
            "aesthetically pleasing composition",
            "award winning photograph"
        ]
        
        ugly_prompts = [
            "blurry photo",
            "low quality image",
            "bad photograph",
            "amateur snapshot",
            "poorly composed image"
        ]
        
        # Encode prompts
        good_embeddings = self.encode_text(aesthetic_prompts)
        bad_embeddings = self.encode_text(ugly_prompts)
        
        # Calculate similarities
        good_similarities = [self.compute_similarity(image_embedding, emb) for emb in good_embeddings]
        bad_similarities = [self.compute_similarity(image_embedding, emb) for emb in bad_embeddings]
        
        # Combine scores
        good_score = np.mean(good_similarities)
        bad_score = np.mean(bad_similarities)
        
        # Convert to 0-1 range (sigmoid-like)
        score = (good_score - bad_score + 1) / 2
        score = np.clip(score, 0, 1)
        
        return float(score)
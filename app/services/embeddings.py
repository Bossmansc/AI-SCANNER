import logging
import numpy as np
from typing import List, Optional
import threading
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings using sentence-transformers."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingService, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the embedding model (singleton)."""
        from app.config import settings
        
        try:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded. Dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Could not initialize embedding model: {str(e)}")
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            numpy array of embeddings with shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])
        
        try:
            # Clean texts
            clean_texts = [text.strip() for text in texts if text.strip()]
            if not clean_texts:
                return np.array([])
            
            # Generate embeddings
            embeddings = self.model.encode(
                clean_texts,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True
            )
            
            # Ensure 2D array
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)
            
            logger.debug(f"Generated embeddings for {len(clean_texts)} texts")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise RuntimeError(f"Failed to generate embeddings: {str(e)}")
    
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            numpy array of embedding with shape (1, embedding_dim)
        """
        return self.embed_texts([text])
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self.embedding_dim

# Global instance
embedding_service = EmbeddingService()
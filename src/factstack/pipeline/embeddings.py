"""Embedding generation for FactStack."""

from typing import List, Optional
import hashlib

from factstack.config import EmbeddingConfig


class EmbeddingGenerator:
    """Generates embeddings for text chunks."""
    
    def __init__(self, config: EmbeddingConfig, llm=None):
        """Initialize embedding generator.
        
        Args:
            config: Embedding configuration
            llm: Optional LLM instance for generating embeddings
        """
        self.config = config
        self.llm = llm
        self._dimension = config.dimension
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension
    
    def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Try using LLM's embedding capability
        if self.llm is not None:
            try:
                return self.llm.get_embeddings(texts)
            except NotImplementedError:
                pass  # Expected when LLM doesn't support embeddings
            except Exception as e:
                import logging
                logging.warning(f"LLM embedding generation failed: {e}, using fallback")
        
        # Fallback to simple hash-based embeddings
        return self._generate_hash_embeddings(texts)
    
    def _generate_hash_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic hash-based pseudo-embeddings.
        
        This is NOT a semantic embedding, just for testing purposes.
        """
        embeddings = []
        for text in texts:
            # Create multiple hashes to fill the dimension
            hashes = []
            for i in range(self._dimension // 32 + 1):
                h = hashlib.sha256(f"{text}:{i}".encode()).digest()
                hashes.extend([float(b) / 255.0 - 0.5 for b in h])
            
            embedding = hashes[:self._dimension]
            
            # Normalize
            norm = sum(x * x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        
        return embeddings
    
    def generate_single(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        embeddings = self.generate([text])
        return embeddings[0] if embeddings else []

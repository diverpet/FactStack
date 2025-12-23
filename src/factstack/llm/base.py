"""Base LLM interface for FactStack."""

from abc import ABC, abstractmethod
from typing import List, Optional

from factstack.llm.schemas import AnswerResponse, ChunkInfo


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""
    
    @abstractmethod
    def generate_answer(
        self,
        question: str,
        chunks: List[ChunkInfo],
        system_prompt: str,
        answer_template: str,
    ) -> AnswerResponse:
        """Generate an answer based on retrieved chunks.
        
        Args:
            question: The user's question
            chunks: List of retrieved and ranked chunks
            system_prompt: System prompt for the LLM
            answer_template: Template/instructions for answer format
        
        Returns:
            Structured AnswerResponse
        """
        pass
    
    @abstractmethod
    def rewrite_query(self, question: str) -> str:
        """Rewrite a query for better retrieval.
        
        Args:
            question: Original user question
        
        Returns:
            Rewritten query for retrieval
        """
        pass
    
    @abstractmethod
    def rerank_chunks(
        self,
        question: str,
        chunks: List[ChunkInfo],
        top_k: int
    ) -> List[ChunkInfo]:
        """Rerank chunks based on relevance to the question.
        
        Args:
            question: The user's question
            chunks: List of candidate chunks
            top_k: Number of top chunks to return
        
        Returns:
            Reranked list of chunks
        """
        pass
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for texts (optional, not all LLMs support this).
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        raise NotImplementedError("This LLM does not support embeddings")

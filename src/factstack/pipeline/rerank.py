"""Reranking for FactStack."""

from typing import List

from factstack.llm.schemas import ChunkInfo
from factstack.llm.base import BaseLLM


class Reranker:
    """Reranks retrieved chunks for better relevance."""
    
    def __init__(self, llm: BaseLLM, top_k: int = 5):
        """Initialize reranker.
        
        Args:
            llm: LLM instance for reranking
            top_k: Number of top chunks to return after reranking
        """
        self.llm = llm
        self.top_k = top_k
    
    def rerank(
        self,
        question: str,
        chunks: List[ChunkInfo],
        top_k: int = None
    ) -> List[ChunkInfo]:
        """Rerank chunks based on relevance to the question.
        
        Args:
            question: User's question
            chunks: List of candidate chunks
            top_k: Override default top_k if provided
        
        Returns:
            Reranked list of chunks (top_k results)
        """
        if not chunks:
            return []
        
        k = top_k or self.top_k
        
        # Use LLM for reranking
        return self.llm.rerank_chunks(question, chunks, k)


class HybridMerger:
    """Merges results from vector and BM25 search."""
    
    def __init__(self, vector_weight: float = 0.7, bm25_weight: float = 0.3):
        """Initialize merger.
        
        Args:
            vector_weight: Weight for vector search scores
            bm25_weight: Weight for BM25 scores
        """
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
    
    def merge(
        self,
        vector_results: List[ChunkInfo],
        bm25_results: List[ChunkInfo]
    ) -> List[ChunkInfo]:
        """Merge and deduplicate results from both search methods.
        
        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
        
        Returns:
            Merged and deduplicated list of chunks with combined scores
        """
        # Build a dict keyed by chunk_id
        merged: dict[str, ChunkInfo] = {}
        
        # Add vector results
        for chunk in vector_results:
            merged[chunk.chunk_id] = ChunkInfo(
                chunk_id=chunk.chunk_id,
                source_path=chunk.source_path,
                title=chunk.title,
                text=chunk.text,
                vector_score=chunk.vector_score,
                bm25_score=0.0,
                final_score=0.0
            )
        
        # Add/merge BM25 results
        for chunk in bm25_results:
            if chunk.chunk_id in merged:
                merged[chunk.chunk_id].bm25_score = chunk.bm25_score
            else:
                merged[chunk.chunk_id] = ChunkInfo(
                    chunk_id=chunk.chunk_id,
                    source_path=chunk.source_path,
                    title=chunk.title,
                    text=chunk.text,
                    vector_score=0.0,
                    bm25_score=chunk.bm25_score,
                    final_score=0.0
                )
        
        # Calculate combined scores
        for chunk in merged.values():
            chunk.final_score = (
                chunk.vector_score * self.vector_weight +
                chunk.bm25_score * self.bm25_weight
            )
        
        # Sort by final score
        results = sorted(
            merged.values(),
            key=lambda x: x.final_score,
            reverse=True
        )
        
        return results

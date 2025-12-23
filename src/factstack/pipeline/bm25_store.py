"""BM25 keyword search store for FactStack."""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional
import re

from factstack.pipeline.chunking import Chunk
from factstack.llm.schemas import ChunkInfo


class BM25Store:
    """BM25 keyword-based search store."""
    
    def __init__(self, persist_dir: Path):
        """Initialize BM25 store.
        
        Args:
            persist_dir: Directory to persist the index
        """
        self.persist_dir = Path(persist_dir)
        self._bm25 = None
        self._chunks_data: List[Dict] = []
        self._tokenized_corpus: List[List[str]] = []
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        # Lowercase and split on non-word characters
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def add_chunks(self, chunks: List[Chunk]) -> int:
        """Add chunks to the BM25 index.
        
        Args:
            chunks: List of Chunk objects
        
        Returns:
            Number of chunks added
        """
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            self._tokenized_corpus.append(tokens)
            self._chunks_data.append({
                'chunk_id': chunk.chunk_id,
                'source_path': chunk.source_path,
                'title': chunk.title,
                'text': chunk.text,
                'chunk_index': chunk.chunk_index
            })
        
        # Rebuild BM25 index
        self._build_index()
        
        return len(chunks)
    
    def _build_index(self) -> None:
        """Build or rebuild the BM25 index."""
        if not self._tokenized_corpus:
            return
        
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        except ImportError:
            # Fallback to simple TF-IDF-like scoring if rank_bm25 is not available
            import logging
            logging.warning(
                "rank_bm25 not available, falling back to simple keyword matching. "
                "Install rank_bm25 for better search quality: pip install rank-bm25"
            )
            self._bm25 = None
    
    def search(self, query: str, top_k: int = 10) -> List[ChunkInfo]:
        """Search for relevant chunks using BM25.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of ChunkInfo with BM25 scores
        """
        if not self._chunks_data:
            return []
        
        query_tokens = self._tokenize(query)
        
        if self._bm25 is not None:
            scores = self._bm25.get_scores(query_tokens)
            # Convert numpy array to list if needed
            if hasattr(scores, 'tolist'):
                scores = scores.tolist()
        else:
            # Fallback: simple keyword matching
            scores = self._simple_keyword_scores(query_tokens)
        
        # Get top-k indices
        scored_indices = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Normalize scores
        max_score = max(scores) if len(scores) > 0 else 1.0
        if max_score == 0:
            max_score = 1.0
        
        results = []
        for idx, score in scored_indices:
            if score > 0:
                chunk_data = self._chunks_data[idx]
                results.append(ChunkInfo(
                    chunk_id=chunk_data['chunk_id'],
                    source_path=chunk_data['source_path'],
                    title=chunk_data.get('title'),
                    text=chunk_data['text'],
                    bm25_score=score / max_score,  # Normalize to 0-1
                    final_score=score / max_score
                ))
        
        return results
    
    def _simple_keyword_scores(self, query_tokens: List[str]) -> List[float]:
        """Simple keyword matching as fallback."""
        scores = []
        query_set = set(query_tokens)
        
        for tokens in self._tokenized_corpus:
            token_set = set(tokens)
            overlap = len(query_set & token_set)
            # Simple TF-like score
            score = overlap / max(len(query_set), 1)
            scores.append(score)
        
        return scores
    
    def save(self) -> None:
        """Persist the index to disk."""
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Save chunks data as JSON
        chunks_path = self.persist_dir / "bm25_chunks.json"
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(self._chunks_data, f, ensure_ascii=False, indent=2)
        
        # Save tokenized corpus
        corpus_path = self.persist_dir / "bm25_corpus.pkl"
        with open(corpus_path, 'wb') as f:
            pickle.dump(self._tokenized_corpus, f)
    
    def load(self) -> bool:
        """Load the index from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        chunks_path = self.persist_dir / "bm25_chunks.json"
        corpus_path = self.persist_dir / "bm25_corpus.pkl"
        
        if not chunks_path.exists() or not corpus_path.exists():
            return False
        
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                self._chunks_data = json.load(f)
            
            with open(corpus_path, 'rb') as f:
                self._tokenized_corpus = pickle.load(f)
            
            self._build_index()
            return True
        except Exception:
            return False
    
    def get_count(self) -> int:
        """Get number of chunks in the store."""
        return len(self._chunks_data)
    
    def clear(self) -> None:
        """Clear all data."""
        self._chunks_data = []
        self._tokenized_corpus = []
        self._bm25 = None

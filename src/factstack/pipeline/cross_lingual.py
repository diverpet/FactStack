"""Cross-lingual retrieval with dual-channel support for FactStack."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from factstack.llm.schemas import ChunkInfo
from factstack.pipeline.vector_store import VectorStore
from factstack.pipeline.bm25_store import BM25Store
from factstack.pipeline.embeddings import EmbeddingGenerator
from factstack.pipeline.query_language import detect_language, needs_translation
from factstack.pipeline.query_translate import QueryTranslator


@dataclass
class ChannelResult:
    """Results from a single retrieval channel."""
    channel_name: str
    query_used: str
    vector_results: List[ChunkInfo] = field(default_factory=list)
    bm25_results: List[ChunkInfo] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DualRetrievalResult:
    """Combined results from dual-channel retrieval."""
    original_query: str
    translated_query: Optional[str]
    query_language: str
    channels: List[ChannelResult] = field(default_factory=list)
    merged_chunks: List[ChunkInfo] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def compute_channel_stats(
    vector_results: List[ChunkInfo],
    bm25_results: List[ChunkInfo]
) -> Dict[str, Any]:
    """Compute statistics for a retrieval channel.
    
    Args:
        vector_results: Vector search results
        bm25_results: BM25 search results
    
    Returns:
        Dictionary of statistics
    """
    stats = {}
    
    # Vector stats
    if vector_results:
        vector_scores = [c.vector_score for c in vector_results]
        stats["vector_count"] = len(vector_results)
        stats["vector_max"] = max(vector_scores)
        stats["vector_mean"] = sum(vector_scores) / len(vector_scores)
    else:
        stats["vector_count"] = 0
        stats["vector_max"] = 0.0
        stats["vector_mean"] = 0.0
    
    # BM25 stats
    if bm25_results:
        bm25_scores = [c.bm25_score for c in bm25_results]
        stats["bm25_count"] = len(bm25_results)
        stats["bm25_max"] = max(bm25_scores)
        stats["bm25_mean"] = sum(bm25_scores) / len(bm25_scores)
    else:
        stats["bm25_count"] = 0
        stats["bm25_max"] = 0.0
        stats["bm25_mean"] = 0.0
    
    return stats


def merge_channel_results(
    channels: List[ChannelResult],
    vector_weight: float = 0.3,
    bm25_weight: float = 0.7
) -> Tuple[List[ChunkInfo], Dict[str, Any]]:
    """Merge results from multiple retrieval channels.
    
    Args:
        channels: List of channel results
        vector_weight: Weight for vector scores
        bm25_weight: Weight for BM25 scores
    
    Returns:
        Tuple of (merged chunks, merge stats)
    """
    # Collect all chunks by chunk_id
    chunk_map: Dict[str, Dict[str, Any]] = {}
    
    for channel in channels:
        channel_name = channel.channel_name
        
        # Process vector results
        for chunk in channel.vector_results:
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = {
                    "chunk": chunk,
                    "vector_scores": {},
                    "bm25_scores": {},
                    "channels": set()
                }
            chunk_map[chunk.chunk_id]["vector_scores"][channel_name] = chunk.vector_score
            chunk_map[chunk.chunk_id]["channels"].add(channel_name)
        
        # Process BM25 results
        for chunk in channel.bm25_results:
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = {
                    "chunk": chunk,
                    "vector_scores": {},
                    "bm25_scores": {},
                    "channels": set()
                }
            chunk_map[chunk.chunk_id]["bm25_scores"][channel_name] = chunk.bm25_score
            chunk_map[chunk.chunk_id]["channels"].add(channel_name)
    
    # Compute combined scores
    merged_chunks = []
    for chunk_id, data in chunk_map.items():
        chunk = data["chunk"]
        
        # Get best scores across channels
        best_vector = max(data["vector_scores"].values()) if data["vector_scores"] else 0.0
        best_bm25 = max(data["bm25_scores"].values()) if data["bm25_scores"] else 0.0
        
        # Create merged chunk with combined score
        merged_chunk = ChunkInfo(
            chunk_id=chunk.chunk_id,
            source_path=chunk.source_path,
            title=chunk.title,
            text=chunk.text,
            vector_score=best_vector,
            bm25_score=best_bm25,
            final_score=best_vector * vector_weight + best_bm25 * bm25_weight
        )
        merged_chunks.append(merged_chunk)
    
    # Sort by final score
    merged_chunks.sort(key=lambda x: x.final_score, reverse=True)
    
    # Compute merge stats
    stats = {
        "total_candidates": len(chunk_map),
        "channels_used": len(channels),
        "multi_channel_hits": sum(1 for d in chunk_map.values() if len(d["channels"]) > 1)
    }
    
    return merged_chunks, stats


class DualRetriever:
    """Performs dual-channel cross-lingual retrieval."""
    
    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        embedding_gen: EmbeddingGenerator,
        translator: Optional[QueryTranslator] = None,
        vector_weight: float = 0.3,
        bm25_weight: float = 0.7
    ):
        """Initialize dual retriever.
        
        Args:
            vector_store: Vector store instance
            bm25_store: BM25 store instance
            embedding_gen: Embedding generator
            translator: Query translator (optional)
            vector_weight: Weight for vector scores
            bm25_weight: Weight for BM25 scores
        """
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.embedding_gen = embedding_gen
        self.translator = translator
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
    
    def retrieve_single_channel(
        self,
        query: str,
        channel_name: str,
        top_k: int = 8
    ) -> ChannelResult:
        """Perform retrieval for a single channel.
        
        Args:
            query: Query string
            channel_name: Name for this channel (e.g., "original", "translated")
            top_k: Number of results to retrieve
        
        Returns:
            ChannelResult with vector and BM25 results
        """
        # Vector search
        query_embedding = self.embedding_gen.generate_single(query)
        vector_results = self.vector_store.search(query_embedding, top_k=top_k)
        
        # BM25 search
        bm25_results = self.bm25_store.search(query, top_k=top_k)
        
        # Compute stats
        stats = compute_channel_stats(vector_results, bm25_results)
        
        return ChannelResult(
            channel_name=channel_name,
            query_used=query,
            vector_results=vector_results,
            bm25_results=bm25_results,
            stats=stats
        )
    
    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        enable_translation: bool = True
    ) -> DualRetrievalResult:
        """Perform dual-channel retrieval.
        
        Args:
            query: Original query string
            top_k: Number of results to retrieve per channel
            enable_translation: Whether to enable translation for cross-lingual retrieval
        
        Returns:
            DualRetrievalResult with merged results
        """
        # Detect query language
        query_lang = detect_language(query)
        
        # Determine if translation is needed
        translated_query = None
        if enable_translation and needs_translation(query) and self.translator:
            translated_query = self.translator.translate_for_retrieval(query, query_lang)
        
        channels = []
        
        # Channel A: Original query
        original_channel = self.retrieve_single_channel(query, "original", top_k)
        channels.append(original_channel)
        
        # Channel B: Translated query (if available)
        if translated_query and translated_query != query:
            translated_channel = self.retrieve_single_channel(
                translated_query, "translated", top_k
            )
            channels.append(translated_channel)
        
        # Merge results
        merged_chunks, merge_stats = merge_channel_results(
            channels, self.vector_weight, self.bm25_weight
        )
        
        # Build result
        result = DualRetrievalResult(
            original_query=query,
            translated_query=translated_query,
            query_language=query_lang,
            channels=channels,
            merged_chunks=merged_chunks,
            stats={
                "query_language": query_lang,
                "translation_used": translated_query is not None,
                "channels_count": len(channels),
                **merge_stats
            }
        )
        
        return result

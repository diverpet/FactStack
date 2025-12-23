"""Vector store implementation for FactStack."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict

from factstack.pipeline.chunking import Chunk
from factstack.llm.schemas import ChunkInfo


class VectorStore:
    """Vector store using ChromaDB for similarity search."""
    
    def __init__(self, persist_dir: Path, collection_name: str = "factstack"):
        """Initialize vector store.
        
        Args:
            persist_dir: Directory to persist the database
            collection_name: Name of the collection
        """
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
    
    @property
    def client(self):
        """Lazy initialization of ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self.persist_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=Settings(anonymized_telemetry=False)
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize ChromaDB: {e}")
        return self._client
    
    @property
    def collection(self):
        """Get or create collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection
    
    def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[List[float]]
    ) -> int:
        """Add chunks with their embeddings to the store.
        
        Args:
            chunks: List of Chunk objects
            embeddings: List of embedding vectors
        
        Returns:
            Number of chunks added
        """
        if not chunks or len(chunks) != len(embeddings):
            return 0
        
        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "source_path": chunk.source_path,
                "title": chunk.title or "",
                "chunk_index": chunk.chunk_index
            }
            for chunk in chunks
        ]
        
        # Add in batches to avoid memory issues
        batch_size = 100
        added = 0
        
        for i in range(0, len(chunks), batch_size):
            batch_end = min(i + batch_size, len(chunks))
            self.collection.add(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end]
            )
            added += batch_end - i
        
        return added
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10
    ) -> List[ChunkInfo]:
        """Search for similar chunks.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
        
        Returns:
            List of ChunkInfo with similarity scores
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        chunks = []
        if results and results['ids'] and results['ids'][0]:
            for i, chunk_id in enumerate(results['ids'][0]):
                # Convert distance to similarity score (cosine distance -> similarity)
                distance = results['distances'][0][i] if results['distances'] else 0
                # ChromaDB returns squared L2 distance for cosine, convert to similarity
                similarity = max(0, 1 - distance)
                
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                chunks.append(ChunkInfo(
                    chunk_id=chunk_id,
                    source_path=metadata.get('source_path', ''),
                    title=metadata.get('title'),
                    text=results['documents'][0][i] if results['documents'] else '',
                    vector_score=similarity,
                    final_score=similarity
                ))
        
        return chunks
    
    def get_count(self) -> int:
        """Get number of chunks in the store."""
        return self.collection.count()
    
    def clear(self) -> None:
        """Clear all data from the collection."""
        self.client.delete_collection(self.collection_name)
        self._collection = None
    
    def get_all_chunk_ids(self) -> List[str]:
        """Get all chunk IDs in the store."""
        result = self.collection.get(include=[])
        return result['ids'] if result else []

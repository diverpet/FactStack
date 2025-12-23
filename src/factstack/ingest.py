"""Document ingestion CLI for FactStack."""

import argparse
import sys
from pathlib import Path

from factstack.config import Config
from factstack.pipeline.chunking import DocumentChunker
from factstack.pipeline.embeddings import EmbeddingGenerator
from factstack.pipeline.vector_store import VectorStore
from factstack.pipeline.bm25_store import BM25Store
from factstack.observability.tracer import Tracer, TracedOperation
from factstack.utils.time import get_timestamp_for_filename


def ingest(
    docs_dir: Path,
    persist_dir: Path,
    config: Config = None
) -> dict:
    """Ingest documents from a directory.
    
    Args:
        docs_dir: Directory containing documents
        persist_dir: Directory to persist the database
        config: Optional configuration
    
    Returns:
        Summary of ingestion results
    """
    config = config or Config.from_env()
    tracer = Tracer()
    
    # Initialize components
    chunker = DocumentChunker(
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap
    )
    
    embedding_gen = EmbeddingGenerator(config.embedding)
    vector_store = VectorStore(persist_dir / "vector")
    bm25_store = BM25Store(persist_dir / "bm25")
    
    # Step 1: Read and chunk documents
    with TracedOperation(tracer, "chunk_documents", f"docs_dir={docs_dir}") as op:
        chunks = chunker.chunk_directory(docs_dir)
        op.set_output(f"{len(chunks)} chunks created")
        op.set_metadata(chunk_count=len(chunks))
    
    if not chunks:
        print(f"No documents found in {docs_dir}")
        return {"chunks": 0, "error": "No documents found"}
    
    print(f"📄 Chunked {len(chunks)} chunks from documents in {docs_dir}")
    
    # Step 2: Generate embeddings
    with TracedOperation(tracer, "generate_embeddings", f"{len(chunks)} chunks") as op:
        texts = [chunk.text for chunk in chunks]
        embeddings = embedding_gen.generate(texts)
        op.set_output(f"{len(embeddings)} embeddings generated")
        op.set_metadata(embedding_dim=len(embeddings[0]) if embeddings else 0)
    
    print(f"🔢 Generated {len(embeddings)} embeddings")
    
    # Step 3: Store in vector database
    with TracedOperation(tracer, "vector_store", f"{len(chunks)} chunks") as op:
        try:
            # Clear existing data
            try:
                vector_store.clear()
            except Exception:
                pass
            
            # Recreate collection and add chunks
            vector_store._collection = None  # Force recreation
            added = vector_store.add_chunks(chunks, embeddings)
            op.set_output(f"{added} chunks added to vector store")
        except Exception as e:
            op.set_error(str(e))
            raise
    
    print(f"📊 Added {added} chunks to vector store")
    
    # Step 4: Build BM25 index
    with TracedOperation(tracer, "bm25_index", f"{len(chunks)} chunks") as op:
        bm25_store.clear()
        bm25_store.add_chunks(chunks)
        bm25_store.save()
        op.set_output(f"BM25 index built with {bm25_store.get_count()} chunks")
    
    print(f"🔍 Built BM25 index with {bm25_store.get_count()} chunks")
    
    # Save trace
    artifacts_dir = Path(config.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    trace_path = artifacts_dir / f"trace_ingest_{get_timestamp_for_filename()}.jsonl"
    tracer.save(trace_path)
    print(f"📝 Trace saved to {trace_path}")
    
    summary = {
        "docs_dir": str(docs_dir),
        "persist_dir": str(persist_dir),
        "chunks": len(chunks),
        "embeddings": len(embeddings),
        "trace_path": str(trace_path),
        "run_id": tracer.run_id
    }
    
    return summary


def main():
    """CLI entry point for ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into FactStack"
    )
    parser.add_argument(
        "--docs", "-d",
        type=str,
        default="./docs",
        help="Directory containing documents to ingest"
    )
    parser.add_argument(
        "--persist", "-p",
        type=str,
        default="./db",
        help="Directory to persist the database"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Maximum characters per chunk"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Character overlap between chunks"
    )
    
    args = parser.parse_args()
    
    docs_dir = Path(args.docs)
    persist_dir = Path(args.persist)
    
    if not docs_dir.exists():
        print(f"Error: Documents directory '{docs_dir}' does not exist")
        sys.exit(1)
    
    # Create config with CLI overrides
    config = Config.from_env()
    config.chunking.chunk_size = args.chunk_size
    config.chunking.chunk_overlap = args.chunk_overlap
    
    print(f"🚀 Starting FactStack ingestion")
    print(f"   Documents: {docs_dir}")
    print(f"   Database: {persist_dir}")
    print(f"   Chunk size: {config.chunking.chunk_size}")
    print()
    
    try:
        summary = ingest(docs_dir, persist_dir, config)
        print()
        print("✅ Ingestion complete!")
        print(f"   Total chunks: {summary['chunks']}")
        print(f"   Run ID: {summary['run_id']}")
    except Exception as e:
        print(f"❌ Error during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

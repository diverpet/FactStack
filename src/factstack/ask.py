"""Question answering CLI for FactStack."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from factstack.config import Config
from factstack.pipeline.embeddings import EmbeddingGenerator
from factstack.pipeline.vector_store import VectorStore
from factstack.pipeline.bm25_store import BM25Store
from factstack.pipeline.rerank import Reranker, HybridMerger
from factstack.pipeline.assemble import ContextAssembler
from factstack.pipeline.refusal import RefusalChecker
from factstack.llm.schemas import QueryResult, AnswerResponse
from factstack.llm.base import BaseLLM
from factstack.llm.dummy_llm import DummyLLM
from factstack.observability.tracer import Tracer, TracedOperation
from factstack.utils.time import get_timestamp_for_filename


def get_llm(config: Config) -> BaseLLM:
    """Get the appropriate LLM based on configuration.
    
    Args:
        config: Configuration
    
    Returns:
        LLM instance
    """
    if config.llm.provider == "openai":
        try:
            from factstack.llm.openai_llm import OpenAILLM
            return OpenAILLM(
                model=config.llm.model,
                temperature=config.llm.temperature
            )
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI LLM: {e}")
            print("Falling back to DummyLLM")
            return DummyLLM()
    else:
        return DummyLLM()


def ask(
    question: str,
    db_dir: Path,
    config: Config = None,
    top_k: int = 8,
    save_artifacts: bool = True
) -> QueryResult:
    """Answer a question using the RAG pipeline.
    
    Args:
        question: User's question
        db_dir: Directory containing the database
        config: Optional configuration
        top_k: Number of chunks to retrieve
        save_artifacts: Whether to save artifacts
    
    Returns:
        QueryResult with answer and metadata
    """
    config = config or Config.from_env()
    tracer = Tracer()
    
    # Initialize components
    llm = get_llm(config)
    embedding_gen = EmbeddingGenerator(config.embedding, llm)
    vector_store = VectorStore(db_dir / "vector")
    bm25_store = BM25Store(db_dir / "bm25")
    merger = HybridMerger(
        vector_weight=config.retrieval.vector_weight,
        bm25_weight=config.retrieval.bm25_weight
    )
    reranker = Reranker(llm, top_k=config.retrieval.rerank_top_k)
    assembler = ContextAssembler()
    refusal_checker = RefusalChecker(config.refusal)
    
    # Load BM25 index
    bm25_store.load()
    
    # Step 1: Query rewriting (optional)
    with TracedOperation(tracer, "query_rewrite", f"question={question[:50]}...") as op:
        rewritten_query = llm.rewrite_query(question)
        op.set_output(f"rewritten={rewritten_query[:50]}...")
        op.set_metadata(original=question, rewritten=rewritten_query)
    
    # Step 2: Vector search
    with TracedOperation(tracer, "vector_search", f"query={rewritten_query[:30]}...") as op:
        query_embedding = embedding_gen.generate_single(rewritten_query)
        vector_results = vector_store.search(query_embedding, top_k=top_k)
        op.set_output(f"{len(vector_results)} results")
        op.set_metadata(result_count=len(vector_results))
    
    # Step 3: BM25 search
    with TracedOperation(tracer, "bm25_search", f"query={rewritten_query[:30]}...") as op:
        bm25_results = bm25_store.search(rewritten_query, top_k=top_k)
        op.set_output(f"{len(bm25_results)} results")
        op.set_metadata(result_count=len(bm25_results))
    
    # Step 4: Merge results
    with TracedOperation(tracer, "merge", f"v={len(vector_results)}, b={len(bm25_results)}") as op:
        merged_chunks = merger.merge(vector_results, bm25_results)
        op.set_output(f"{len(merged_chunks)} merged chunks")
    
    # Step 5: Pre-answer refusal check
    with TracedOperation(tracer, "refusal_check_pre", f"{len(merged_chunks)} chunks") as op:
        pre_refusal = refusal_checker.check_pre_answer(merged_chunks)
        op.set_output(f"refuse={pre_refusal.should_refuse}, reason={pre_refusal.reason[:50]}")
        op.set_metadata(should_refuse=pre_refusal.should_refuse)
    
    if pre_refusal.should_refuse:
        # Create refusal response
        answer = refusal_checker.create_refusal_response(
            question, pre_refusal, merged_chunks
        )
        result = QueryResult(
            question=question,
            answer=answer,
            chunks=[],
            run_id=tracer.run_id
        )
    else:
        # Step 6: Rerank
        with TracedOperation(tracer, "rerank", f"{len(merged_chunks)} candidates") as op:
            reranked_chunks = reranker.rerank(
                question, merged_chunks, top_k=config.retrieval.rerank_top_k
            )
            op.set_output(f"{len(reranked_chunks)} reranked chunks")
            if reranked_chunks:
                op.set_metadata(top_score=reranked_chunks[0].final_score)
        
        # Step 7: Assemble context
        with TracedOperation(tracer, "assemble", f"{len(reranked_chunks)} chunks") as op:
            context, used_chunks = assembler.assemble(reranked_chunks)
            op.set_output(f"{len(context)} chars, {len(used_chunks)} chunks used")
        
        # Step 8: Generate answer
        prompt_config = config.get_prompt_config()
        
        with TracedOperation(tracer, "llm_answer", f"question={question[:30]}...") as op:
            answer = llm.generate_answer(
                question=question,
                chunks=used_chunks,
                system_prompt=prompt_config.get("system", ""),
                answer_template=prompt_config.get("answer_template", "")
            )
            op.set_output(f"confidence={answer.confidence:.2f}, refusal={answer.is_refusal}")
            op.set_metadata(confidence=answer.confidence)
        
        # Step 9: Post-answer refusal check
        with TracedOperation(tracer, "refusal_check_post", f"confidence={answer.confidence}") as op:
            post_refusal = refusal_checker.check_post_answer(answer, used_chunks)
            if post_refusal.confidence_adjustment != 0:
                adjusted = max(0.0, min(1.0, 
                    answer.confidence + post_refusal.confidence_adjustment))
                answer.confidence = adjusted
            op.set_output(f"adjustment={post_refusal.confidence_adjustment}")
        
        result = QueryResult(
            question=question,
            answer=answer,
            chunks=used_chunks,
            run_id=tracer.run_id
        )
    
    # Save artifacts
    if save_artifacts:
        artifacts_dir = Path(config.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = get_timestamp_for_filename()
        
        # Save trace
        trace_path = artifacts_dir / f"trace_{timestamp}.jsonl"
        tracer.save(trace_path)
        result.trace_path = str(trace_path)
        
        # Save human-readable answer
        answer_path = artifacts_dir / f"answer_{timestamp}.md"
        with open(answer_path, "w", encoding="utf-8") as f:
            f.write(format_answer_markdown(result))
    
    return result


def format_answer_markdown(result: QueryResult) -> str:
    """Format the query result as markdown."""
    md = f"""# Question
{result.question}

# Answer
{result.answer.answer}

## Confidence
{result.answer.confidence:.2%}

## Citations
"""
    for i, cit in enumerate(result.answer.citations):
        md += f"\n### [C{i+1}] {cit.source}\n"
        md += f"- Chunk ID: {cit.chunk_id}\n"
        md += f"- Score: {cit.score:.3f}\n"
        md += f"- Text: {cit.text[:200]}...\n"
    
    if result.answer.missing_info:
        md += "\n## Missing Information\n"
        for info in result.answer.missing_info:
            md += f"- {info}\n"
    
    if result.answer.is_refusal:
        md += f"\n## Refusal Reason\n{result.answer.refusal_reason}\n"
    
    md += f"\n## Metadata\n"
    md += f"- Run ID: {result.run_id}\n"
    if result.trace_path:
        md += f"- Trace: {result.trace_path}\n"
    
    return md


def main():
    """CLI entry point for asking questions."""
    parser = argparse.ArgumentParser(
        description="Ask questions using FactStack RAG"
    )
    parser.add_argument(
        "--db", "-d",
        type=str,
        default="./db",
        help="Database directory"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        required=True,
        help="Question to ask"
    )
    parser.add_argument(
        "--topk", "-k",
        type=int,
        default=8,
        help="Number of chunks to retrieve"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="base",
        help="Prompt configuration to use (base, strict)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    args = parser.parse_args()
    
    db_dir = Path(args.db)
    if not db_dir.exists():
        print(f"Error: Database directory '{db_dir}' does not exist")
        print("Run `python -m factstack.ingest` first to create the database")
        sys.exit(1)
    
    config = Config.from_env()
    config.prompt_config = args.prompt
    
    print(f"🤔 Asking: {args.question}")
    print(f"   Database: {db_dir}")
    print(f"   LLM Provider: {config.llm.provider}")
    print(f"   Prompt Config: {config.prompt_config}")
    print()
    
    try:
        result = ask(args.question, db_dir, config, top_k=args.topk)
        
        if args.json:
            print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("📝 ANSWER")
            print("=" * 60)
            print(result.answer.answer)
            print()
            print(f"📊 Confidence: {result.answer.confidence:.2%}")
            print()
            
            if result.answer.citations:
                print("📚 Citations:")
                for i, cit in enumerate(result.answer.citations):
                    print(f"   [{i+1}] {cit.source} (score: {cit.score:.3f})")
            
            if result.answer.missing_info:
                print()
                print("⚠️  Missing Information:")
                for info in result.answer.missing_info:
                    print(f"   - {info}")
            
            if result.answer.is_refusal:
                print()
                print(f"❌ Refusal: {result.answer.refusal_reason}")
            
            print()
            print(f"🔍 Run ID: {result.run_id}")
            if result.trace_path:
                print(f"📝 Trace saved to: {result.trace_path}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

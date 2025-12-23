"""Question answering CLI for FactStack."""

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Literal

from factstack.config import Config
from factstack.pipeline.embeddings import EmbeddingGenerator
from factstack.pipeline.vector_store import VectorStore
from factstack.pipeline.bm25_store import BM25Store
from factstack.pipeline.rerank import Reranker, HybridMerger
from factstack.pipeline.assemble import ContextAssembler
from factstack.pipeline.refusal import RefusalChecker
from factstack.pipeline.query_language import detect_language, needs_translation
from factstack.pipeline.query_translate import QueryTranslator
from factstack.pipeline.cross_lingual import DualRetriever
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
    rerank_top_k: int = None,
    save_artifacts: bool = True,
    cross_lingual: bool = True,
    translate: bool = True,
    translation_mode: Literal["llm", "rule", "off"] = "llm"
) -> QueryResult:
    """Answer a question using the RAG pipeline.
    
    Args:
        question: User's question
        db_dir: Directory containing the database
        config: Optional configuration
        top_k: Number of chunks to retrieve per channel
        rerank_top_k: Number of chunks after reranking (defaults to config value)
        save_artifacts: Whether to save artifacts
        cross_lingual: Enable cross-lingual dual retrieval
        translate: Enable query translation
        translation_mode: Translation mode ("llm", "rule", or "off")
    
    Returns:
        QueryResult with answer and metadata
    """
    config = config or Config.from_env()
    tracer = Tracer()
    
    # Use config value if not specified
    if rerank_top_k is None:
        rerank_top_k = config.retrieval.rerank_top_k
    
    # Initialize components
    llm = get_llm(config)
    embedding_gen = EmbeddingGenerator(config.embedding, llm)
    vector_store = VectorStore(db_dir / "vector")
    bm25_store = BM25Store(db_dir / "bm25")
    reranker = Reranker(llm, top_k=rerank_top_k)
    assembler = ContextAssembler()
    refusal_checker = RefusalChecker(config.refusal)
    
    # Load BM25 index
    bm25_store.load()
    
    # Initialize translator if needed
    translator = None
    effective_translation_mode = translation_mode
    if translate and translation_mode != "off":
        # Determine effective mode based on LLM availability
        if translation_mode == "llm" and isinstance(llm, DummyLLM):
            effective_translation_mode = "rule"
        translator = QueryTranslator(llm=llm, mode=effective_translation_mode)
    
    # Step 1: Detect query language
    with TracedOperation(tracer, "language_detect", f"query={question[:30]}...") as op:
        query_lang = detect_language(question)
        needs_trans = needs_translation(question)
        op.set_output(f"lang={query_lang}, needs_translation={needs_trans}")
        op.set_metadata(
            query_language=query_lang,
            needs_translation=needs_trans
        )
    
    # Step 2: Translate query if needed
    translated_query = None
    if cross_lingual and needs_trans and translator:
        with TracedOperation(tracer, "query_translate", f"query={question[:30]}...") as op:
            translated_query = translator.translate_for_retrieval(question, query_lang)
            op.set_output(f"translated={translated_query[:50] if translated_query else 'None'}...")
            op.set_metadata(
                original_query=question,
                translated_query=translated_query,
                translation_mode=effective_translation_mode
            )
    
    # Step 3: Query rewriting (on original or translated)
    search_query = question
    with TracedOperation(tracer, "query_rewrite", f"question={question[:50]}...") as op:
        rewritten_query = llm.rewrite_query(question)
        search_query = rewritten_query
        op.set_output(f"rewritten={rewritten_query[:50]}...")
        op.set_metadata(original=question, rewritten=rewritten_query)
    
    # Step 4: Dual retrieval (if cross-lingual enabled)
    cross_lingual_stats = None
    if cross_lingual and translated_query:
        # Initialize dual retriever
        dual_retriever = DualRetriever(
            vector_store=vector_store,
            bm25_store=bm25_store,
            embedding_gen=embedding_gen,
            translator=translator,
            vector_weight=config.retrieval.vector_weight,
            bm25_weight=config.retrieval.bm25_weight
        )
        
        with TracedOperation(tracer, "dual_retrieval", f"query={question[:30]}...") as op:
            dual_result = dual_retriever.retrieve(
                query=search_query,
                top_k=top_k,
                enable_translation=True
            )
            merged_chunks = dual_result.merged_chunks
            cross_lingual_stats = dual_result.stats
            
            # Log channel stats
            for channel in dual_result.channels:
                op.set_metadata(**{
                    f"{channel.channel_name}_vector_max": channel.stats.get("vector_max", 0),
                    f"{channel.channel_name}_bm25_max": channel.stats.get("bm25_max", 0),
                })
            
            op.set_output(f"{len(merged_chunks)} merged chunks from {len(dual_result.channels)} channels")
            op.set_metadata(
                original_query=dual_result.original_query,
                translated_query=dual_result.translated_query,
                query_language=dual_result.query_language,
                total_candidates=cross_lingual_stats.get("total_candidates", 0),
                multi_channel_hits=cross_lingual_stats.get("multi_channel_hits", 0)
            )
    else:
        # Single channel retrieval (original behavior)
        merger = HybridMerger(
            vector_weight=config.retrieval.vector_weight,
            bm25_weight=config.retrieval.bm25_weight
        )
        
        # Vector search
        with TracedOperation(tracer, "vector_search", f"query={search_query[:30]}...") as op:
            query_embedding = embedding_gen.generate_single(search_query)
            vector_results = vector_store.search(query_embedding, top_k=top_k)
            op.set_output(f"{len(vector_results)} results")
            op.set_metadata(result_count=len(vector_results))
        
        # BM25 search
        with TracedOperation(tracer, "bm25_search", f"query={search_query[:30]}...") as op:
            bm25_results = bm25_store.search(search_query, top_k=top_k)
            op.set_output(f"{len(bm25_results)} results")
            op.set_metadata(result_count=len(bm25_results))
        
        # Merge results
        with TracedOperation(tracer, "merge", f"v={len(vector_results)}, b={len(bm25_results)}") as op:
            merged_chunks = merger.merge(vector_results, bm25_results)
            op.set_output(f"{len(merged_chunks)} merged chunks")
    
    # Step 5: Pre-answer refusal check (with cross-lingual stats)
    with TracedOperation(tracer, "refusal_check_pre", f"{len(merged_chunks)} chunks") as op:
        pre_refusal = refusal_checker.check_pre_answer(merged_chunks, cross_lingual_stats)
        op.set_output(f"refuse={pre_refusal.should_refuse}, reason={pre_refusal.reason[:50]}")
        op.set_metadata(
            should_refuse=pre_refusal.should_refuse,
            indicators=pre_refusal.indicators
        )
    
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
                question, merged_chunks, top_k=rerank_top_k
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
            f.write(format_answer_markdown(result, translated_query))
    
    return result


def format_answer_markdown(result: QueryResult, translated_query: str = None) -> str:
    """Format the query result as markdown."""
    md = f"""# Question
{result.question}
"""
    
    if translated_query:
        md += f"\n## Translated Query\n{translated_query}\n"
    
    md += f"""
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
        help="Number of chunks to retrieve per channel"
    )
    parser.add_argument(
        "--rerank-topk",
        type=int,
        default=None,
        help="Number of chunks after reranking (default: from config)"
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
    # Cross-lingual options
    parser.add_argument(
        "--cross-lingual",
        type=str,
        choices=["on", "off"],
        default="on",
        help="Enable cross-lingual dual retrieval (default: on)"
    )
    parser.add_argument(
        "--translate",
        type=str,
        choices=["on", "off"],
        default="on",
        help="Enable query translation (default: on)"
    )
    parser.add_argument(
        "--translation-mode",
        type=str,
        choices=["llm", "rule", "off"],
        default="llm",
        help="Translation mode: llm (use LLM), rule (dictionary-based), off (default: llm)"
    )
    
    args = parser.parse_args()
    
    db_dir = Path(args.db)
    if not db_dir.exists():
        print(f"Error: Database directory '{db_dir}' does not exist")
        print("Run `python -m factstack.ingest` first to create the database")
        sys.exit(1)
    
    config = Config.from_env()
    config.prompt_config = args.prompt
    
    # Parse cross-lingual options
    cross_lingual = args.cross_lingual == "on"
    translate = args.translate == "on"
    translation_mode = args.translation_mode
    
    # Auto-downgrade translation mode if no API key
    if translation_mode == "llm" and config.llm.provider == "dummy":
        translation_mode = "rule"
    
    # Detect query language for display
    query_lang = detect_language(args.question)
    
    print(f"🤔 Asking: {args.question}")
    print(f"   Database: {db_dir}")
    print(f"   LLM Provider: {config.llm.provider}")
    print(f"   QueryLang={query_lang}, CrossLingual={cross_lingual}, Translation={translation_mode}")
    print()
    
    try:
        result = ask(
            args.question,
            db_dir,
            config,
            top_k=args.topk,
            rerank_top_k=args.rerank_topk,
            cross_lingual=cross_lingual,
            translate=translate,
            translation_mode=translation_mode
        )
        
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
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

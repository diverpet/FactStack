"""Evaluation CLI for FactStack."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

import yaml

from factstack.config import Config
from factstack.ask import ask, get_llm
from factstack.llm.schemas import QueryResult
from factstack.observability.tracer import Tracer, TracedOperation
from factstack.utils.time import get_timestamp_for_filename


@dataclass
class EvalCase:
    """A single evaluation test case."""
    question: str
    expected_sources: List[str] = field(default_factory=list)
    expected_answer_contains: List[str] = field(default_factory=list)
    difficulty: str = "medium"
    should_refuse: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating a single case."""
    question: str
    difficulty: str
    
    # Recall metrics
    recall_at_k: float = 0.0
    expected_sources_found: List[str] = field(default_factory=list)
    expected_sources_missing: List[str] = field(default_factory=list)
    
    # Citation metrics
    citation_precision: float = 0.0
    citations_from_expected: int = 0
    total_citations: int = 0
    
    # Answer groundedness
    answer_groundedness: float = 0.0
    citation_count_in_answer: int = 0
    
    # Refusal accuracy
    refusal_correct: bool = True
    expected_refusal: bool = False
    actual_refusal: bool = False
    
    # Answer quality
    answer_contains_expected: List[str] = field(default_factory=list)
    answer_missing_expected: List[str] = field(default_factory=list)
    
    # Metadata
    confidence: float = 0.0
    run_id: str = ""
    error: Optional[str] = None


@dataclass
class EvalSummary:
    """Summary of all evaluation results."""
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    
    # Aggregate metrics
    avg_recall_at_k: float = 0.0
    avg_citation_precision: float = 0.0
    avg_answer_groundedness: float = 0.0
    refusal_accuracy: float = 0.0
    
    # By difficulty
    easy_pass_rate: float = 0.0
    medium_pass_rate: float = 0.0
    hard_pass_rate: float = 0.0
    
    # Details
    results: List[Dict] = field(default_factory=list)


def load_eval_set(path: Path) -> List[EvalCase]:
    """Load evaluation cases from YAML file.
    
    Args:
        path: Path to eval_set.yaml
    
    Returns:
        List of EvalCase objects
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    cases = []
    for item in data.get("cases", []):
        cases.append(EvalCase(
            question=item["question"],
            expected_sources=item.get("expected_sources", []),
            expected_answer_contains=item.get("expected_answer_contains", []),
            difficulty=item.get("difficulty", "medium"),
            should_refuse=item.get("should_refuse", False),
            tags=item.get("tags", [])
        ))
    
    return cases


def evaluate_case(
    case: EvalCase,
    result: QueryResult
) -> EvalResult:
    """Evaluate a single query result against expected outcomes.
    
    Args:
        case: Expected outcomes
        result: Actual query result
    
    Returns:
        EvalResult with metrics
    """
    eval_result = EvalResult(
        question=case.question,
        difficulty=case.difficulty,
        expected_refusal=case.should_refuse,
        actual_refusal=result.answer.is_refusal,
        confidence=result.answer.confidence,
        run_id=result.run_id
    )
    
    # 1. Calculate Recall@K
    sources_found = set()
    all_sources = [c.source_path for c in result.chunks]
    
    for expected_src in case.expected_sources:
        expected_lower = expected_src.lower()
        for actual_src in all_sources:
            if expected_lower in actual_src.lower():
                sources_found.add(expected_src)
                break
    
    eval_result.expected_sources_found = list(sources_found)
    eval_result.expected_sources_missing = [
        s for s in case.expected_sources if s not in sources_found
    ]
    
    if case.expected_sources:
        eval_result.recall_at_k = len(sources_found) / len(case.expected_sources)
    else:
        eval_result.recall_at_k = 1.0  # No expected sources = pass
    
    # 2. Calculate Citation Precision
    citation_sources = [c.source for c in result.answer.citations]
    eval_result.total_citations = len(citation_sources)
    
    citations_from_expected = 0
    for cit_src in citation_sources:
        for expected_src in case.expected_sources:
            if expected_src.lower() in cit_src.lower():
                citations_from_expected += 1
                break
    
    eval_result.citations_from_expected = citations_from_expected
    if citation_sources:
        eval_result.citation_precision = citations_from_expected / len(citation_sources)
    else:
        eval_result.citation_precision = 0.0 if case.expected_sources else 1.0
    
    # 3. Calculate Answer Groundedness
    answer_text = result.answer.answer
    citation_markers = sum(1 for i in range(20) if f"[C{i+1}]" in answer_text)
    eval_result.citation_count_in_answer = citation_markers
    
    # Groundedness: has citations and they're relevant
    if citation_markers >= 1:
        eval_result.answer_groundedness = min(1.0, citation_markers / 3) * eval_result.citation_precision
    else:
        eval_result.answer_groundedness = 0.0
    
    # 4. Check Refusal Accuracy
    eval_result.refusal_correct = (case.should_refuse == result.answer.is_refusal)
    
    # 5. Check answer content
    answer_lower = answer_text.lower()
    for expected in case.expected_answer_contains:
        if expected.lower() in answer_lower:
            eval_result.answer_contains_expected.append(expected)
        else:
            eval_result.answer_missing_expected.append(expected)
    
    return eval_result


def run_evaluation(
    eval_path: Path,
    db_dir: Path,
    config: Config = None
) -> EvalSummary:
    """Run evaluation on all cases.
    
    Args:
        eval_path: Path to eval_set.yaml
        db_dir: Database directory
        config: Optional configuration
    
    Returns:
        EvalSummary with all results
    """
    config = config or Config.from_env()
    cases = load_eval_set(eval_path)
    
    if not cases:
        print("No evaluation cases found")
        return EvalSummary()
    
    print(f"📋 Running {len(cases)} evaluation cases...")
    print()
    
    results = []
    difficulty_counts = {"easy": [0, 0], "medium": [0, 0], "hard": [0, 0]}
    
    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] {case.question[:50]}...")
        
        try:
            query_result = ask(
                question=case.question,
                db_dir=db_dir,
                config=config,
                save_artifacts=False
            )
            
            eval_result = evaluate_case(case, query_result)
            
            # Determine if case passed
            passed = (
                eval_result.recall_at_k >= 0.5 and
                eval_result.refusal_correct
            )
            
            if passed:
                print(f"   ✅ PASS (recall={eval_result.recall_at_k:.2f})")
            else:
                print(f"   ❌ FAIL (recall={eval_result.recall_at_k:.2f}, "
                      f"refusal_correct={eval_result.refusal_correct})")
            
            # Track by difficulty
            difficulty = case.difficulty.lower()
            if difficulty in difficulty_counts:
                difficulty_counts[difficulty][1] += 1  # Total
                if passed:
                    difficulty_counts[difficulty][0] += 1  # Passed
            
            results.append(eval_result)
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append(EvalResult(
                question=case.question,
                difficulty=case.difficulty,
                error=str(e)
            ))
    
    # Calculate summary
    summary = EvalSummary(
        total_cases=len(cases),
        passed_cases=sum(1 for r in results if not r.error and r.recall_at_k >= 0.5 and r.refusal_correct),
        failed_cases=sum(1 for r in results if r.error or r.recall_at_k < 0.5 or not r.refusal_correct)
    )
    
    # Aggregate metrics
    valid_results = [r for r in results if not r.error]
    if valid_results:
        summary.avg_recall_at_k = sum(r.recall_at_k for r in valid_results) / len(valid_results)
        summary.avg_citation_precision = sum(r.citation_precision for r in valid_results) / len(valid_results)
        summary.avg_answer_groundedness = sum(r.answer_groundedness for r in valid_results) / len(valid_results)
        summary.refusal_accuracy = sum(1 for r in valid_results if r.refusal_correct) / len(valid_results)
    
    # By difficulty
    for difficulty, (passed, total) in difficulty_counts.items():
        if total > 0:
            rate = passed / total
            if difficulty == "easy":
                summary.easy_pass_rate = rate
            elif difficulty == "medium":
                summary.medium_pass_rate = rate
            elif difficulty == "hard":
                summary.hard_pass_rate = rate
    
    summary.results = [asdict(r) for r in results]
    
    return summary


def main():
    """CLI entry point for evaluation."""
    parser = argparse.ArgumentParser(
        description="Run FactStack evaluation"
    )
    parser.add_argument(
        "--db", "-d",
        type=str,
        default="./db",
        help="Database directory"
    )
    parser.add_argument(
        "--eval", "-e",
        type=str,
        default="./tests/eval_set.yaml",
        help="Path to evaluation set YAML"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="base",
        help="Prompt configuration to use"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path (optional)"
    )
    
    args = parser.parse_args()
    
    db_dir = Path(args.db)
    eval_path = Path(args.eval)
    
    if not db_dir.exists():
        print(f"Error: Database directory '{db_dir}' does not exist")
        sys.exit(1)
    
    if not eval_path.exists():
        print(f"Error: Evaluation file '{eval_path}' does not exist")
        sys.exit(1)
    
    config = Config.from_env()
    config.prompt_config = args.prompt
    
    print("=" * 60)
    print("🧪 FactStack Evaluation")
    print("=" * 60)
    print(f"Database: {db_dir}")
    print(f"Eval Set: {eval_path}")
    print(f"LLM Provider: {config.llm.provider}")
    print()
    
    try:
        summary = run_evaluation(eval_path, db_dir, config)
        
        print()
        print("=" * 60)
        print("📊 EVALUATION SUMMARY")
        print("=" * 60)
        print(f"Total Cases: {summary.total_cases}")
        print(f"Passed: {summary.passed_cases}")
        print(f"Failed: {summary.failed_cases}")
        print()
        print("Aggregate Metrics:")
        print(f"  - Recall@K: {summary.avg_recall_at_k:.2%}")
        print(f"  - Citation Precision: {summary.avg_citation_precision:.2%}")
        print(f"  - Answer Groundedness: {summary.avg_answer_groundedness:.2%}")
        print(f"  - Refusal Accuracy: {summary.refusal_accuracy:.2%}")
        print()
        print("By Difficulty:")
        print(f"  - Easy: {summary.easy_pass_rate:.2%}")
        print(f"  - Medium: {summary.medium_pass_rate:.2%}")
        print(f"  - Hard: {summary.hard_pass_rate:.2%}")
        
        # Save results
        artifacts_dir = Path(config.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = args.output or str(
            artifacts_dir / f"eval_{get_timestamp_for_filename()}.json"
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2, ensure_ascii=False)
        
        print()
        print(f"📝 Results saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

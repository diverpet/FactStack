"""Refusal logic for FactStack."""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field

from factstack.llm.schemas import ChunkInfo, AnswerResponse
from factstack.config import RefusalConfig


# Constants for multi-indicator refusal logic
MIN_REFUSAL_REASONS = 2  # Minimum number of reasons to trigger refusal
LOW_SCORE_MULTIPLIER = 0.5  # Multiplier for score threshold in severe cases
TOP_N_AVG_THRESHOLD = 0.2  # Minimum average score for top-N chunks
LOW_COVERAGE_THRESHOLD = 0.2  # Minimum coverage ratio
LOW_MAX_SCORE_THRESHOLD = 0.3  # Max score below which coverage is considered


@dataclass
class RefusalDecision:
    """Decision about whether to refuse to answer."""
    should_refuse: bool
    reason: str
    confidence_adjustment: float = 0.0
    missing_info: List[str] = None
    indicators: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.missing_info is None:
            self.missing_info = []


class RefusalChecker:
    """Checks whether the system should refuse to answer.
    
    Uses multi-indicator based refusal logic:
    - Top-N average score and coverage
    - Minimum high-quality evidence count
    - Score distribution analysis
    """
    
    def __init__(self, config: RefusalConfig, min_high_quality_chunks: int = 2):
        """Initialize refusal checker.
        
        Args:
            config: Refusal configuration
            min_high_quality_chunks: Minimum number of high-quality chunks required
        """
        self.config = config
        self.min_high_quality_chunks = min_high_quality_chunks
        # High quality threshold (chunks above this are considered good evidence)
        self.high_quality_threshold = 0.25
    
    def check_pre_answer(
        self,
        chunks: List[ChunkInfo],
        cross_lingual_stats: Optional[Dict[str, Any]] = None
    ) -> RefusalDecision:
        """Check if we should refuse before generating answer.
        
        Uses multi-indicator based refusal:
        1. Checks if there are enough chunks
        2. Checks top-N average score
        3. Checks number of high-quality evidence chunks
        4. Considers cross-lingual retrieval results if available
        
        Args:
            chunks: Retrieved and ranked chunks
            cross_lingual_stats: Optional stats from cross-lingual retrieval
        
        Returns:
            RefusalDecision
        """
        indicators = {}
        
        if not chunks:
            return RefusalDecision(
                should_refuse=True,
                reason="No relevant evidence found in the knowledge base",
                missing_info=["Any relevant documentation for this query"],
                indicators={"no_chunks": True}
            )
        
        # Calculate indicators
        max_score = max(c.final_score for c in chunks)
        top_n = min(5, len(chunks))
        top_n_scores = [c.final_score for c in chunks[:top_n]]
        top_n_avg = sum(top_n_scores) / len(top_n_scores)
        
        # Count high-quality chunks
        high_quality_count = sum(
            1 for c in chunks if c.final_score >= self.high_quality_threshold
        )
        
        # Coverage: what percentage of top-5 are above threshold
        coverage = high_quality_count / top_n if top_n > 0 else 0
        
        indicators = {
            "max_score": max_score,
            "top_n_avg": top_n_avg,
            "high_quality_count": high_quality_count,
            "coverage": coverage,
            "total_chunks": len(chunks)
        }
        
        # Add cross-lingual stats if available
        if cross_lingual_stats:
            indicators["cross_lingual"] = cross_lingual_stats
            # If translated channel had better results, boost confidence
            if cross_lingual_stats.get("translation_used"):
                indicators["translation_boosted"] = True
        
        # Multi-indicator refusal decision
        refusal_reasons = []
        
        # Check minimum chunks requirement
        if len(chunks) < self.config.min_chunks_required:
            refusal_reasons.append(
                f"Insufficient chunks: {len(chunks)} < {self.config.min_chunks_required}"
            )
        
        # Check if max score is too low (but use lower threshold for cross-lingual)
        effective_threshold = self.config.min_score_threshold
        if cross_lingual_stats and cross_lingual_stats.get("translation_used"):
            # Be more lenient when translation was used
            effective_threshold *= 0.8
        
        if max_score < effective_threshold:
            refusal_reasons.append(
                f"Best score too low: {max_score:.3f} < {effective_threshold:.3f}"
            )
        
        # Check high-quality evidence count
        if high_quality_count < self.min_high_quality_chunks:
            # Only add as reason if other indicators are also weak
            if top_n_avg < TOP_N_AVG_THRESHOLD:
                refusal_reasons.append(
                    f"Insufficient high-quality evidence: {high_quality_count} chunks above threshold"
                )
        
        # Check coverage
        if coverage < LOW_COVERAGE_THRESHOLD and max_score < LOW_MAX_SCORE_THRESHOLD:
            refusal_reasons.append(
                f"Low coverage: only {coverage:.0%} of top results are relevant"
            )
        
        # Make final decision
        # Refuse only if multiple indicators suggest low quality
        should_refuse = len(refusal_reasons) >= MIN_REFUSAL_REASONS or (
            len(refusal_reasons) >= 1 and max_score < effective_threshold * LOW_SCORE_MULTIPLIER
        )
        
        if should_refuse:
            return RefusalDecision(
                should_refuse=True,
                reason="; ".join(refusal_reasons),
                confidence_adjustment=-0.3,
                missing_info=["Higher quality matches for this query"],
                indicators=indicators
            )
        
        # Check for potential conflicts (high variance in scores among top chunks)
        if len(chunks) >= 2:
            score_variance = self._calculate_variance(top_n_scores)
            indicators["score_variance"] = score_variance
            
            if score_variance > self.config.conflict_threshold:
                return RefusalDecision(
                    should_refuse=False,  # Don't refuse, but flag uncertainty
                    reason=f"High variance in relevance scores suggests potential "
                           f"conflicting information (variance: {score_variance:.2f})",
                    confidence_adjustment=-0.2,
                    missing_info=["Clarification on which context is most relevant"],
                    indicators=indicators
                )
        
        # No refusal needed
        return RefusalDecision(
            should_refuse=False,
            reason="Sufficient evidence found",
            indicators=indicators
        )
    
    def check_post_answer(
        self,
        answer: AnswerResponse,
        chunks: List[ChunkInfo]
    ) -> RefusalDecision:
        """Check answer quality after generation.
        
        Args:
            answer: Generated answer
            chunks: Chunks used for generation
        
        Returns:
            RefusalDecision
        """
        issues = []
        confidence_adjustment = 0.0
        
        # Check if answer cites evidence
        citation_markers = [f"[C{i+1}]" for i in range(len(chunks))]
        citations_used = sum(1 for m in citation_markers if m in answer.answer)
        
        if citations_used == 0 and chunks:
            issues.append("Answer does not cite any evidence")
            confidence_adjustment -= 0.3
        
        # Check confidence level
        if answer.confidence < 0.3:
            issues.append(f"Low confidence score: {answer.confidence:.2f}")
        
        # Check if answer is too short (might indicate hallucination or uncertainty)
        if len(answer.answer.split()) < 10 and not answer.is_refusal:
            issues.append("Answer is unusually short")
            confidence_adjustment -= 0.1
        
        if issues:
            return RefusalDecision(
                should_refuse=False,
                reason="; ".join(issues),
                confidence_adjustment=confidence_adjustment,
                missing_info=answer.missing_info or []
            )
        
        return RefusalDecision(
            should_refuse=False,
            reason="Answer quality check passed"
        )
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of scores."""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return variance
    
    def create_refusal_response(
        self,
        question: str,
        decision: RefusalDecision,
        chunks: List[ChunkInfo]
    ) -> AnswerResponse:
        """Create a refusal response.
        
        Args:
            question: Original question
            decision: Refusal decision
            chunks: Available chunks (may be empty)
        
        Returns:
            AnswerResponse indicating refusal
        """
        from factstack.llm.schemas import Citation
        
        # Include any available citations even in refusal
        citations = []
        for i, chunk in enumerate(chunks[:3]):
            citations.append(Citation(
                chunk_id=chunk.chunk_id,
                source=chunk.source_path,
                text=chunk.text[:150] + "...",
                score=chunk.final_score
            ))
        
        return AnswerResponse(
            answer=f"I cannot confidently answer this question. {decision.reason}",
            citations=citations,
            confidence=max(0.0, 0.2 + decision.confidence_adjustment),
            missing_info=decision.missing_info,
            reasoning=decision.reason,
            is_refusal=True,
            refusal_reason=decision.reason
        )

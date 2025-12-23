"""Refusal logic for FactStack."""

from typing import List, Tuple, Optional
from dataclasses import dataclass

from factstack.llm.schemas import ChunkInfo, AnswerResponse
from factstack.config import RefusalConfig


@dataclass
class RefusalDecision:
    """Decision about whether to refuse to answer."""
    should_refuse: bool
    reason: str
    confidence_adjustment: float = 0.0
    missing_info: List[str] = None
    
    def __post_init__(self):
        if self.missing_info is None:
            self.missing_info = []


class RefusalChecker:
    """Checks whether the system should refuse to answer."""
    
    def __init__(self, config: RefusalConfig):
        """Initialize refusal checker.
        
        Args:
            config: Refusal configuration
        """
        self.config = config
    
    def check_pre_answer(
        self,
        chunks: List[ChunkInfo]
    ) -> RefusalDecision:
        """Check if we should refuse before generating answer.
        
        Args:
            chunks: Retrieved and ranked chunks
        
        Returns:
            RefusalDecision
        """
        if not chunks:
            return RefusalDecision(
                should_refuse=True,
                reason="No relevant evidence found in the knowledge base",
                missing_info=["Any relevant documentation for this query"]
            )
        
        # Check minimum chunks requirement
        if len(chunks) < self.config.min_chunks_required:
            return RefusalDecision(
                should_refuse=True,
                reason=f"Insufficient evidence: only {len(chunks)} chunk(s) found, "
                       f"minimum {self.config.min_chunks_required} required",
                missing_info=["More relevant documents to support the answer"]
            )
        
        # Check score threshold
        max_score = max(c.final_score for c in chunks)
        avg_score = sum(c.final_score for c in chunks) / len(chunks)
        
        if max_score < self.config.min_score_threshold:
            return RefusalDecision(
                should_refuse=True,
                reason=f"Low relevance scores: best match score {max_score:.2f} "
                       f"is below threshold {self.config.min_score_threshold}",
                confidence_adjustment=-0.3,
                missing_info=["Higher quality matches for this query"]
            )
        
        # Check for potential conflicts (high variance in scores among top chunks)
        if len(chunks) >= 2:
            top_scores = [c.final_score for c in chunks[:3]]
            score_variance = self._calculate_variance(top_scores)
            
            if score_variance > self.config.conflict_threshold:
                return RefusalDecision(
                    should_refuse=False,  # Don't refuse, but flag uncertainty
                    reason=f"High variance in relevance scores suggests potential "
                           f"conflicting information (variance: {score_variance:.2f})",
                    confidence_adjustment=-0.2,
                    missing_info=["Clarification on which context is most relevant"]
                )
        
        # No refusal needed
        return RefusalDecision(
            should_refuse=False,
            reason="Sufficient evidence found"
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

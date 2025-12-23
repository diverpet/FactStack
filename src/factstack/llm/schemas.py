"""Pydantic schemas for LLM outputs."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A citation reference to a source chunk."""
    chunk_id: str = Field(description="Unique identifier of the referenced chunk")
    source: str = Field(description="Source file path")
    text: str = Field(description="The quoted text from the chunk")
    score: float = Field(default=0.0, description="Relevance score of this citation")


class AnswerResponse(BaseModel):
    """Structured response from the LLM."""
    answer: str = Field(description="The answer text with [C1], [C2], etc. citations")
    citations: List[Citation] = Field(
        default_factory=list,
        description="List of citations supporting the answer"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score between 0 and 1"
    )
    missing_info: List[str] = Field(
        default_factory=list,
        description="List of missing information that would improve the answer"
    )
    reasoning: str = Field(
        default="",
        description="Explanation of how the answer was derived"
    )
    is_refusal: bool = Field(
        default=False,
        description="Whether this response is a refusal to answer"
    )
    refusal_reason: Optional[str] = Field(
        default=None,
        description="Reason for refusing to answer (if is_refusal=True)"
    )


class ChunkInfo(BaseModel):
    """Information about a retrieved chunk."""
    chunk_id: str
    source_path: str
    title: Optional[str] = None
    text: str
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0


class QueryResult(BaseModel):
    """Complete result from a query."""
    question: str
    answer: AnswerResponse
    chunks: List[ChunkInfo]
    trace_path: Optional[str] = None
    run_id: str

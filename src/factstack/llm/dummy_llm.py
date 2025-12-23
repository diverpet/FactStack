"""Dummy LLM implementation for testing without API keys."""

import re
import json
from typing import List

from factstack.llm.base import BaseLLM
from factstack.llm.schemas import AnswerResponse, ChunkInfo, Citation


class DummyLLM(BaseLLM):
    """Dummy LLM that generates template-based responses without an API.
    
    This implementation allows running the complete pipeline without
    requiring an external LLM API. It provides structured responses
    with citations and confidence scores based on heuristics.
    """
    
    def generate_answer(
        self,
        question: str,
        chunks: List[ChunkInfo],
        system_prompt: str,
        answer_template: str,
    ) -> AnswerResponse:
        """Generate a template-based answer using retrieved chunks.
        
        The answer includes citations from the provided chunks and
        uses heuristics to determine confidence and potential refusals.
        """
        if not chunks:
            return AnswerResponse(
                answer="I cannot answer this question as no relevant evidence was found.",
                citations=[],
                confidence=0.0,
                missing_info=["No relevant documents found for this query"],
                reasoning="No chunks were retrieved, indicating the knowledge base may not contain relevant information.",
                is_refusal=True,
                refusal_reason="No evidence available"
            )
        
        # Calculate average score to determine confidence
        avg_score = sum(c.final_score for c in chunks) / len(chunks)
        max_score = max(c.final_score for c in chunks)
        
        # Build citations
        citations = []
        answer_parts = []
        
        for i, chunk in enumerate(chunks[:5]):  # Use top 5 chunks
            citation = Citation(
                chunk_id=chunk.chunk_id,
                source=chunk.source_path,
                text=chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                score=chunk.final_score
            )
            citations.append(citation)
            
            # Extract key sentence from chunk for answer
            sentences = chunk.text.split('.')
            if sentences:
                key_sentence = sentences[0].strip()
                if key_sentence:
                    answer_parts.append(f"According to {chunk.source_path}, {key_sentence} [C{i+1}].")
        
        # Determine if we should refuse
        # Refuse only if max score is really low, or if there's no good top result
        should_refuse = max_score < 0.2 and avg_score < 0.1
        
        if should_refuse:
            return AnswerResponse(
                answer=f"I cannot confidently answer '{question}' based on the available evidence. "
                       f"The retrieved documents have low relevance scores (max: {max_score:.2f}).",
                citations=citations,
                confidence=max_score * 0.5,
                missing_info=[
                    "More specific documentation on this topic",
                    "Higher quality matches in the knowledge base"
                ],
                reasoning=f"The maximum relevance score ({max_score:.2f}) is below the confidence threshold.",
                is_refusal=True,
                refusal_reason="Insufficient evidence confidence"
            )
        
        # Build answer from chunks
        answer = f"Based on the retrieved evidence, here is what I found regarding '{question}':\n\n"
        answer += "\n".join(answer_parts) if answer_parts else "See the cited sources for details."
        
        # Calculate confidence based on scores and coverage
        confidence = min(0.95, max_score * 0.8 + avg_score * 0.2)
        
        # Identify missing info based on question keywords not found in chunks
        question_words = set(question.lower().split())
        chunk_text = " ".join(c.text.lower() for c in chunks)
        missing_keywords = [w for w in question_words if len(w) > 4 and w not in chunk_text]
        
        missing_info = []
        if missing_keywords:
            missing_info.append(f"More information about: {', '.join(missing_keywords[:3])}")
        if len(chunks) < 3:
            missing_info.append("Additional supporting documents would increase confidence")
        
        return AnswerResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            missing_info=missing_info,
            reasoning=f"Answer synthesized from {len(chunks)} relevant chunks with average score {avg_score:.2f}",
            is_refusal=False,
            refusal_reason=None
        )
    
    def rewrite_query(self, question: str) -> str:
        """Simple query rewriting using keyword extraction.
        
        In a real implementation, this would use an LLM to generate
        better search queries. Here we just clean and normalize.
        """
        # Remove common question words
        stop_words = {'what', 'how', 'why', 'when', 'where', 'who', 'which', 
                      'is', 'are', 'do', 'does', 'can', 'could', 'would', 
                      'the', 'a', 'an', 'to', 'for', 'of', 'in', 'on', 'with'}
        
        words = question.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Return cleaned query or original if too short
        rewritten = ' '.join(keywords)
        return rewritten if len(rewritten) > 3 else question
    
    def rerank_chunks(
        self,
        question: str,
        chunks: List[ChunkInfo],
        top_k: int
    ) -> List[ChunkInfo]:
        """Rerank chunks using simple keyword matching heuristics.
        
        In a real implementation, this would use a cross-encoder model.
        Here we use keyword overlap scoring.
        """
        question_lower = question.lower()
        question_words = set(question_lower.split())
        
        for chunk in chunks:
            chunk_lower = chunk.text.lower()
            chunk_words = set(chunk_lower.split())
            
            # Calculate overlap score
            overlap = len(question_words & chunk_words)
            keyword_score = overlap / max(len(question_words), 1)
            
            # Check for exact phrase matches
            exact_match_bonus = 0.3 if question_lower in chunk_lower else 0.0
            
            # Combine scores
            chunk.rerank_score = (
                chunk.final_score * 0.4 +  # Original score
                keyword_score * 0.4 +       # Keyword overlap
                exact_match_bonus           # Exact match bonus
            )
            chunk.final_score = chunk.rerank_score
        
        # Sort by rerank score and return top_k
        chunks.sort(key=lambda x: x.rerank_score, reverse=True)
        return chunks[:top_k]
    
    def get_embeddings(self, texts: List[str], dimension: int = 1536) -> List[List[float]]:
        """Generate simple hash-based pseudo-embeddings.
        
        This is NOT a real embedding - just for testing the pipeline.
        In production, use a real embedding model.
        
        Args:
            texts: List of texts to embed
            dimension: Embedding dimension (default 1536 for OpenAI compatibility)
        """
        import hashlib
        
        embeddings = []
        for text in texts:
            # Create deterministic pseudo-embedding based on text hash
            hashes = []
            for i in range(dimension // 32 + 1):
                h = hashlib.sha256(f"{text}:{i}".encode()).digest()
                hashes.extend([float(b) / 255.0 - 0.5 for b in h])
            
            embedding = hashes[:dimension]
            
            # Normalize
            norm = sum(x * x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        return embeddings

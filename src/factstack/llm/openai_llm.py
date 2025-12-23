"""OpenAI LLM implementation for FactStack."""

import json
import os
from typing import List, Optional

from factstack.llm.base import BaseLLM
from factstack.llm.schemas import AnswerResponse, ChunkInfo, Citation


class OpenAILLM(BaseLLM):
    """OpenAI-based LLM implementation.
    
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        """Initialize OpenAI LLM.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation
        """
        self.model = model
        self.temperature = temperature
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        return self._client
    
    def _build_context(self, chunks: List[ChunkInfo]) -> str:
        """Build context string from chunks with citation markers."""
        context_parts = []
        for i, chunk in enumerate(chunks):
            marker = f"[C{i+1}]"
            context_parts.append(
                f"{marker} Source: {chunk.source_path}\n"
                f"Content: {chunk.text}\n"
            )
        return "\n---\n".join(context_parts)
    
    def generate_answer(
        self,
        question: str,
        chunks: List[ChunkInfo],
        system_prompt: str,
        answer_template: str,
    ) -> AnswerResponse:
        """Generate answer using OpenAI API."""
        if not chunks:
            return AnswerResponse(
                answer="I cannot answer this question as no relevant evidence was found.",
                citations=[],
                confidence=0.0,
                missing_info=["No relevant documents found for this query"],
                reasoning="No chunks were retrieved.",
                is_refusal=True,
                refusal_reason="No evidence available"
            )
        
        context = self._build_context(chunks)
        
        user_message = f"""Question: {question}

Evidence (use [C1], [C2], etc. to cite):
{context}

{answer_template}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Build citations from response
            citations = []
            for i, chunk in enumerate(chunks):
                if f"[C{i+1}]" in data.get("answer", ""):
                    citations.append(Citation(
                        chunk_id=chunk.chunk_id,
                        source=chunk.source_path,
                        text=chunk.text[:200],
                        score=chunk.final_score
                    ))
            
            # If response includes citations, use them
            if "citations" in data and isinstance(data["citations"], list):
                for cit in data["citations"]:
                    if isinstance(cit, dict):
                        citations.append(Citation(
                            chunk_id=cit.get("chunk_id", ""),
                            source=cit.get("source", ""),
                            text=cit.get("text", "")[:200],
                            score=cit.get("score", 0.0)
                        ))
            
            return AnswerResponse(
                answer=data.get("answer", ""),
                citations=citations,
                confidence=float(data.get("confidence", 0.5)),
                missing_info=data.get("missing_info", []),
                reasoning=data.get("reasoning", ""),
                is_refusal=data.get("is_refusal", False),
                refusal_reason=data.get("refusal_reason")
            )
            
        except Exception as e:
            return AnswerResponse(
                answer=f"Error generating answer: {str(e)}",
                citations=[],
                confidence=0.0,
                missing_info=["LLM error occurred"],
                reasoning=f"API error: {str(e)}",
                is_refusal=True,
                refusal_reason=f"LLM error: {str(e)}"
            )
    
    def rewrite_query(self, question: str) -> str:
        """Rewrite query using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a query rewriter. Rewrite the user's question to be more effective for document retrieval. Output ONLY the rewritten query, nothing else."
                    },
                    {"role": "user", "content": question}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return question
    
    def rerank_chunks(
        self,
        question: str,
        chunks: List[ChunkInfo],
        top_k: int
    ) -> List[ChunkInfo]:
        """Rerank chunks using OpenAI for relevance scoring."""
        if not chunks:
            return []
        
        try:
            # Build prompt for relevance scoring
            chunk_texts = []
            for i, chunk in enumerate(chunks):
                chunk_texts.append(f"[{i}] {chunk.text[:300]}")
            
            prompt = f"""Question: {question}

Rate the relevance of each document chunk (0-10) for answering the question.
Output JSON: {{"scores": [score_for_0, score_for_1, ...]}}

Chunks:
{chr(10).join(chunk_texts)}"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": "You are a relevance scorer. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content)
            scores = data.get("scores", [])
            
            # Update rerank scores
            for i, chunk in enumerate(chunks):
                if i < len(scores):
                    chunk.rerank_score = float(scores[i]) / 10.0
                    chunk.final_score = chunk.rerank_score
            
            # Sort and return top_k
            chunks.sort(key=lambda x: x.rerank_score, reverse=True)
            return chunks[:top_k]
            
        except Exception:
            # Fallback to original order
            return chunks[:top_k]
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using OpenAI API."""
        if not texts:
            return []
        
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        
        return [item.embedding for item in response.data]

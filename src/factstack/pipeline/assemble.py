"""Context assembly for FactStack."""

from typing import List, Tuple

from factstack.llm.schemas import ChunkInfo
from factstack.utils.text import count_tokens_approx


class ContextAssembler:
    """Assembles context from ranked chunks for LLM input."""
    
    def __init__(self, max_tokens: int = 3000, max_chunks: int = 8):
        """Initialize assembler.
        
        Args:
            max_tokens: Maximum approximate tokens for context
            max_chunks: Maximum number of chunks to include
        """
        self.max_tokens = max_tokens
        self.max_chunks = max_chunks
    
    def assemble(
        self,
        chunks: List[ChunkInfo]
    ) -> Tuple[str, List[ChunkInfo]]:
        """Assemble context from chunks.
        
        Args:
            chunks: Ranked list of chunks
        
        Returns:
            Tuple of (formatted context string, chunks used)
        """
        if not chunks:
            return "", []
        
        context_parts = []
        used_chunks = []
        total_tokens = 0
        
        for i, chunk in enumerate(chunks[:self.max_chunks]):
            chunk_text = f"[C{i+1}] Source: {chunk.source_path}\n{chunk.text}"
            chunk_tokens = count_tokens_approx(chunk_text)
            
            if total_tokens + chunk_tokens > self.max_tokens and used_chunks:
                # Stop adding more chunks
                break
            
            context_parts.append(chunk_text)
            used_chunks.append(chunk)
            total_tokens += chunk_tokens
        
        context = "\n\n---\n\n".join(context_parts)
        return context, used_chunks
    
    def format_for_prompt(
        self,
        question: str,
        context: str,
        system_prompt: str,
        answer_template: str
    ) -> str:
        """Format the full prompt for the LLM.
        
        Args:
            question: User's question
            context: Assembled context
            system_prompt: System prompt
            answer_template: Answer template/instructions
        
        Returns:
            Formatted prompt string
        """
        prompt = f"""{system_prompt}

## Evidence

{context}

## Question

{question}

## Instructions

{answer_template}
"""
        return prompt

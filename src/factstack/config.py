"""Configuration management for FactStack."""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import yaml


@dataclass
class EmbeddingConfig:
    """Embedding configuration."""
    model: str = "text-embedding-3-small"
    dimension: int = 1536


@dataclass
class ChunkingConfig:
    """Chunking configuration."""
    chunk_size: int = 500
    chunk_overlap: int = 50


@dataclass
class RetrievalConfig:
    """Retrieval configuration."""
    top_k: int = 8
    vector_weight: float = 0.3  # Lower weight for hash-based embeddings
    bm25_weight: float = 0.7    # Higher weight for keyword matching
    rerank_top_k: int = 5


@dataclass
class RefusalConfig:
    """Refusal/uncertainty configuration."""
    min_score_threshold: float = 0.15  # Lower threshold for dummy LLM testing
    min_chunks_required: int = 1
    conflict_threshold: float = 0.2


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: str = "dummy"  # "openai" or "dummy"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 2000
    max_repair_attempts: int = 2


@dataclass
class Config:
    """Main configuration class."""
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    refusal: RefusalConfig = field(default_factory=RefusalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    
    # Paths
    docs_dir: str = "./docs"
    db_dir: str = "./db"
    artifacts_dir: str = "./artifacts"
    prompts_dir: str = "./prompts"
    
    # Current prompt config
    prompt_config: str = "base"
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        config = cls()
        
        # LLM provider from environment
        provider = os.environ.get("LLM_PROVIDER", "dummy").lower()
        config.llm.provider = provider
        
        # OpenAI API key check
        if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            print("Warning: LLM_PROVIDER=openai but OPENAI_API_KEY not set. Falling back to dummy.")
            config.llm.provider = "dummy"
        
        return config
    
    def get_prompt_config(self) -> dict:
        """Load the current prompt configuration."""
        prompt_path = Path(self.prompts_dir) / f"{self.prompt_config}.yaml"
        if not prompt_path.exists():
            # Return default prompt config
            return {
                "system": "You are a helpful assistant that answers questions based on provided evidence.",
                "answer_template": """Based on the provided evidence, answer the question.
You MUST:
1. Only use information from the provided chunks
2. Cite sources using [C1], [C2], etc. format
3. If evidence is insufficient, say "I cannot answer this with confidence"
4. Provide a confidence score between 0 and 1

Output your response as valid JSON with this structure:
{
  "answer": "your answer with [C1] citations",
  "citations": [{"chunk_id": "...", "source": "...", "text": "...", "score": 0.0}],
  "confidence": 0.0,
  "missing_info": ["what information is missing"],
  "reasoning": "why you gave this answer"
}
""",
                "refusal_prompt": "If you cannot find sufficient evidence, explicitly state uncertainty.",
                "strict_mode": False
            }
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

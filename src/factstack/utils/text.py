"""Text utilities for FactStack."""

import re
import hashlib
from typing import List, Optional


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def generate_chunk_id(source_path: str, chunk_index: int) -> str:
    """Generate a stable chunk ID based on file path and index."""
    # Create a hash-based stable ID
    content = f"{source_path}:{chunk_index}"
    hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
    # Create readable ID
    clean_path = re.sub(r'[^\w]', '_', source_path)
    return f"{clean_path}_{chunk_index}_{hash_val}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_title_from_markdown(content: str) -> Optional[str]:
    """Extract title from markdown content (first # header)."""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def count_tokens_approx(text: str) -> int:
    """Approximate token count (simple word-based estimation)."""
    # Rough estimation: ~4 characters per token on average
    return len(text) // 4

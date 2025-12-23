"""Query language detection for FactStack."""

import re
from typing import Literal


# CJK Unicode ranges
CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
    (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
    (0x3000, 0x303F),    # CJK Symbols and Punctuation
    (0x3040, 0x309F),    # Hiragana (Japanese)
    (0x30A0, 0x30FF),    # Katakana (Japanese)
    (0xAC00, 0xD7AF),    # Hangul Syllables (Korean)
]


def is_cjk_char(char: str) -> bool:
    """Check if a character is CJK (Chinese, Japanese, Korean)."""
    code_point = ord(char)
    for start, end in CJK_RANGES:
        if start <= code_point <= end:
            return True
    return False


def count_cjk_chars(text: str) -> int:
    """Count the number of CJK characters in text."""
    return sum(1 for char in text if is_cjk_char(char))


def count_ascii_words(text: str) -> int:
    """Count ASCII words in text."""
    ascii_words = re.findall(r'[a-zA-Z]+', text)
    return len(ascii_words)


def detect_language(query: str) -> Literal["zh", "en", "mixed"]:
    """Detect the primary language of a query.
    
    Args:
        query: The input query string
    
    Returns:
        "zh" if primarily CJK characters
        "en" if primarily ASCII/English
        "mixed" if a mix of both
    """
    if not query or not query.strip():
        return "en"
    
    cjk_count = count_cjk_chars(query)
    ascii_word_count = count_ascii_words(query)
    
    # Calculate ratios
    total_chars = len(query.replace(" ", ""))
    if total_chars == 0:
        return "en"
    
    cjk_ratio = cjk_count / total_chars
    
    # Thresholds for classification
    if cjk_ratio > 0.5:
        return "zh"
    elif cjk_ratio > 0.1 and ascii_word_count > 0:
        return "mixed"
    else:
        return "en"


def needs_translation(query: str) -> bool:
    """Check if a query needs translation for cross-lingual retrieval.
    
    Args:
        query: The input query string
    
    Returns:
        True if the query contains CJK characters and might benefit from translation
    """
    lang = detect_language(query)
    return lang in ("zh", "mixed")

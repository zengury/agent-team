"""Utility functions for conversation processing."""

from pathlib import Path


def load_transcript(path: str | Path) -> str:
    """Load a transcript from a file path."""
    return Path(path).read_text()


def chunk_transcript(text: str, max_chars: int = 8000) -> list[str]:
    """
    Split a long transcript into chunks suitable for LLM context windows.
    Tries to split at paragraph boundaries.
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current = ""
    
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 <= max_chars:
            current += paragraph + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph + "\n\n"
    
    if current:
        chunks.append(current.strip())
    
    return chunks


def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    """Simple keyword extraction from text (for tagging/matching)."""
    # Remove common words, extract unique capitalized words and key terms
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "you", "your",
        "we", "our", "they", "their", "it", "its", "this", "that", "these",
        "those", "am", "i", "me", "my", "he", "she", "him", "her", "us",
        "not", "no", "nor", "so", "if", "then", "than", "too", "very",
        "just", "about", "also", "like", "well", "really", "ok", "okay",
        "yeah", "yes", "right", "got", "get", "going", "gonna", "want",
        "need", "think", "know",
    }
    
    words = text.replace("\n", " ").split()
    keywords = []
    
    # First pass: multi-word capitalized phrases
    # (simplified — in production use NLP)
    for word in words:
        clean = word.strip(".,!?;:\"'()[]{}").lower()
        if (
            clean not in stop_words
            and len(clean) > 2
            and clean not in keywords
        ):
            keywords.append(clean)
    
    # Prioritize uncommon words (longer = more specific)
    keywords.sort(key=len, reverse=True)
    
    return keywords[:max_keywords]

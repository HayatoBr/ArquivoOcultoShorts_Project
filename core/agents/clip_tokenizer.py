from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


_WORD_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ']+", re.UNICODE)


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def clamp_prompt_words(text: str, max_words: int = 55) -> str:
    """Conservative CLIP-safe clamp.
    We don't have the real CLIP tokenizer here, so we clamp by words (<=55) to keep <~70 tokens in practice.
    """
    text = normalize_spaces(text)
    words = _WORD_RE.findall(text)
    if len(words) <= max_words:
        return text

    # Reconstruct preserving original order but dropping after max_words
    kept = words[:max_words]
    return " ".join(kept)


def strip_redundant_phrases(text: str) -> str:
    """Remove very common redundancy patterns that bloat prompts."""
    t = normalize_spaces(text)
    # remove duplicated commas/semicolons
    t = re.sub(r"[,;]{2,}", ",", t)
    # remove repeated words like "cinematic cinematic"
    t = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", t, flags=re.IGNORECASE)
    return normalize_spaces(t)


def sanitize_for_clip(text: str, max_words: int = 55) -> str:
    t = strip_redundant_phrases(text)
    t = re.sub(r"[\[\]{}<>]", " ", t)  # avoid tokenizer weirdness
    t = re.sub(r"\s+", " ", t).strip()
    return clamp_prompt_words(t, max_words=max_words)

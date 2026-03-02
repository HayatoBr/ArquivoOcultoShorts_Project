from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional


@dataclass
class Scene:
    idx: int
    kind: str  # character | environment | detail | climax
    text: str


_SENT_RE = re.compile(r"(?<=[\.!\?])\s+", re.UNICODE)


def _sentences(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    parts = _SENT_RE.split(t)
    # keep only non-empty
    return [p.strip() for p in parts if p and p.strip()]


def split_script_into_scenes(script_text: str, max_scenes: int = 5) -> List[Scene]:
    """Deterministic splitter (no LLM) to avoid cost and improve stability.

    Strategy:
      - Split into sentences
      - Group into N chunks
      - Assign alternating kinds: character -> environment -> detail -> character -> climax
    """
    sents = _sentences(script_text)
    if not sents:
        return [Scene(idx=1, kind="character", text="")]

    max_scenes = int(max(3, min(6, max_scenes)))
    # If script is short, reduce scenes to fit
    if len(sents) <= 3:
        max_scenes = 3
    elif len(sents) <= 5:
        max_scenes = min(max_scenes, 4)

    # chunking
    n = max_scenes
    chunk_size = max(1, len(sents) // n)
    chunks: List[List[str]] = []
    i = 0
    for k in range(n):
        if k == n - 1:
            chunk = sents[i:]
        else:
            chunk = sents[i:i + chunk_size]
        if not chunk:
            break
        chunks.append(chunk)
        i += len(chunk)
        if i >= len(sents):
            break

    kinds_cycle = ["character", "environment", "detail", "character", "climax", "environment"]
    scenes: List[Scene] = []
    for j, chunk in enumerate(chunks, start=1):
        kind = kinds_cycle[(j - 1) % len(kinds_cycle)]
        scenes.append(Scene(idx=j, kind=kind, text=" ".join(chunk).strip()))
    # Ensure last scene is climax for retention
    if scenes:
        scenes[-1].kind = "climax"
    return scenes

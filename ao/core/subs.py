from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from ao.core.media_utils import format_srt_timestamp



def _chunk_lines(text: str, max_chars: int = 42) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        tentative = f"{current} {word}".strip()
        if len(tentative) <= max_chars:
            current = tentative
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines



def _caption_blocks(script_text: str, max_words: int = 10) -> list[str]:
    text = re.sub(r"\s+", " ", script_text).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    blocks: list[str] = []

    for sentence in sentences:
        words = sentence.split()
        if len(words) <= max_words:
            blocks.append(sentence)
            continue
        for start in range(0, len(words), max_words):
            blocks.append(" ".join(words[start:start + max_words]))
    return [b for b in blocks if b]



def simple_srt(script_text: str, duration: float, out_path: Path, max_words: int = 10) -> Path:
    blocks = _caption_blocks(script_text, max_words=max_words)
    if not blocks:
        out_path.write_text("", encoding="utf-8")
        return out_path

    total_duration = max(1.0, float(duration))
    step = total_duration / len(blocks)

    entries: list[str] = []
    for idx, block in enumerate(blocks, start=1):
        start = (idx - 1) * step
        end = min(total_duration, idx * step)
        caption_lines = _chunk_lines(block)
        caption_text = "\n".join(caption_lines[:2]) if caption_lines else block
        entries.append(
            f"{idx}\n"
            f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n"
            f"{caption_text}\n"
        )

    out_path.write_text("\n".join(entries), encoding="utf-8")
    return out_path



def export_scene_json(out_path: Path, topic: str, scene_plan: List[Dict[str, Any]], script_clean: str) -> Path:
    payload = {
        "title": topic,
        "script_clean": script_clean,
        "scenes": scene_plan,
    }
    out_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path

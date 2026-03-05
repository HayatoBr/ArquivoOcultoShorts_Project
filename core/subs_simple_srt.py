from __future__ import annotations
import re
from pathlib import Path

def _fmt_ts(t: float) -> str:
    if t < 0: t = 0.0
    ms = int(round((t - int(t)) * 1000))
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def make_srt_from_text(text: str, out_srt: str, total_seconds: float = 60.0, max_chars: int = 42) -> str:
    """Create a simple SRT by splitting text into readable chunks and distributing across total_seconds."""
    text = (text or "").strip()
    if not text:
        Path(out_srt).write_text("", encoding="utf-8")
        return out_srt

    # Split into sentences / phrases
    parts = re.split(r"(?<=[\.!\?])\s+|\n+", text)
    parts = [p.strip() for p in parts if p.strip()]

    # Further wrap long parts
    chunks = []
    for p in parts:
        if len(p) <= max_chars:
            chunks.append(p)
            continue
        words = p.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 <= max_chars:
                line = (line + " " + w).strip()
            else:
                chunks.append(line)
                line = w
        if line:
            chunks.append(line)

    n = max(1, len(chunks))
    seg = float(total_seconds) / n
    cur = 0.0
    out_lines = []
    for i, ch in enumerate(chunks, 1):
        start = cur
        end = cur + seg
        cur = end
        out_lines.append(str(i))
        out_lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        out_lines.append(ch)
        out_lines.append("")
    Path(out_srt).parent.mkdir(parents=True, exist_ok=True)
    Path(out_srt).write_text("\n".join(out_lines).strip() + "\n", encoding="utf-8")
    return out_srt

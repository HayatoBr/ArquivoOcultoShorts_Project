import re
from typing import Dict, Any, List

def _sentences(text: str) -> List[str]:
    # Keep it simple and robust for PT-BR
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    parts = re.split(r"(?<=[\.!\?])\s+", t)
    return [p.strip() for p in parts if p.strip()]

def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+[\w'-]*\b", text or "", flags=re.U))

def fit_to_duration(text: str, target_seconds: int, wpm: int = 155, max_words: int | None = None,
                    closing_question: bool = True) -> Dict[str, Any]:
    """Reduce texto para caber ~no tempo (estimativa por WPM)."""
    if max_words is None:
        max_words = max(60, int(target_seconds * wpm / 60))

    before_words = _word_count(text)
    if before_words <= max_words:
        return {"changed": False, "before_words": before_words, "after_words": before_words, "max_words": max_words, "text": text}

    sents = _sentences(text)
    if not sents:
        short = " ".join((text or "").split()[:max_words])
        return {"changed": True, "before_words": before_words, "after_words": _word_count(short), "max_words": max_words, "text": short}

    # Strategy:
    #  - Keep first sentence as hook
    #  - Add most informative next sentences until hitting limit
    #  - Optionally finish with a short question
    out: List[str] = []
    out_words = 0

    def add_sent(s: str):
        nonlocal out_words
        w = _word_count(s)
        out.append(s)
        out_words += w

    # hook
    add_sent(sents[0])

    for s in sents[1:]:
        if out_words + _word_count(s) > max_words - (10 if closing_question else 0):
            break
        add_sent(s)

    if closing_question:
        q = "O que você acha que realmente aconteceu?"
        if out_words + _word_count(q) <= max_words:
            out.append(q)

    final = " ".join(out).strip()
    # hard cap just in case
    words = re.findall(r"\b\w+[\w'-]*\b", final, flags=re.U)
    if len(words) > max_words:
        # truncate by words, keep punctuation at end
        final = " ".join(words[:max_words]).strip()
        if final and final[-1] not in ".!?":
            final += "."

    return {"changed": True, "before_words": before_words, "after_words": _word_count(final), "max_words": max_words, "text": final}


def fit_text_to_seconds(text: str, seconds: int, cfg: Dict[str, Any] | None = None) -> tuple[str, Dict[str, Any]]:
    """Compat wrapper expected by pipeline: returns (text, report)."""
    wpm = 155
    if cfg and isinstance(cfg.get("agents"), dict):
        wpm = int(cfg["agents"].get("wpm", wpm))
    rep = fit_to_duration(text, target_seconds=int(seconds), wpm=wpm)
    out_text = rep.get("text", text) if isinstance(rep, dict) else text
    return out_text, (rep if isinstance(rep, dict) else {"changed": False, "text": out_text})

# Backwards-compat alias
def fit_text_to_duration(text: str, seconds: int, cfg: Dict[str, Any] | None = None) -> tuple[str, Dict[str, Any]]:
    return fit_text_to_seconds(text, seconds=seconds, cfg=cfg)

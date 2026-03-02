import re
from typing import Dict, Any

_HEADING_PATTERNS = [
    r"^\s*#.+$",
    r"^\s*\*\*?t[ií]tulo\*\*?\s*:\s*.*$",
    r"^\s*t[ií]tulo\s*:\s*.*$",
    r"^\s*resumo\s*:\s*.*$",
    r"^\s*(introdu[cç][aã]o|conclus[aã]o)\s*:\s*$",
]

# Parentheses often contain birth/death dates and locations that bloat TTS + CLIP tokens
_PAREN_NOISE = re.compile(r"\((?:[^)(]{0,120})\)")

# Fix spaced digits like "1 9 7 3" -> "1973" (helps CLIP + TTS)
_SPACED_DIGITS = re.compile(r"(?<!\d)(?:\d\s+){2,}\d(?!\d)")

def _collapse_spaced_digits(s: str) -> str:
    def repl(m):
        return re.sub(r"\s+", "", m.group(0))
    return _SPACED_DIGITS.sub(repl, s)

def clean_script_text(text: str, cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Remove termos meta/markdown e normaliza para TTS (Piper) + prompts (CLIP)."""
    original = text or ""
    t = original.replace("\r\n", "\n").replace("\r", "\n")

    # remove markdown/code fences
    t = re.sub(r"```.*?```", "", t, flags=re.S)

    # remove headings/metadata lines
    for pat in _HEADING_PATTERNS:
        t = re.sub(pat, "", t, flags=re.I | re.M)

    # remove common wiki glue separators
    t = re.sub(r"\n\s*---\s*\n", "\n", t)
    t = re.sub(r"\n\s*--\s*\n", "\n", t)

    # remove leading bullets and numbering artifacts
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*\d+\)\s*", "", t, flags=re.M)

    # strip label-like prefixes inside lines
    t = re.sub(r"(?im)^\s*(t[ií]tulo|title|cena|scene|narrador|narra[cç][aã]o)\s*:\s*", "", t)

    # normalize quotes/dashes
    t = t.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-").replace("—", "-")

    # remove parentheses noise (dates/places) – keep short ones only if useful
    # If you ever want to keep parentheses, disable via cfg: script.keep_parentheses=true
    keep_paren = bool(((cfg or {}).get("script") or {}).get("keep_parentheses", False))
    if not keep_paren:
        t = _PAREN_NOISE.sub("", t)

    # collapse spaced digits for CLIP/TTS
    t = _collapse_spaced_digits(t)

    # collapse whitespace
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.strip()

    # cadence: add a period at end if missing
    if t and t[-1] not in ".!?":
        t += "."

    # ensure space after punctuation
    t = re.sub(r"([\.!\?])([^\s])", r"\1 \2", t)

    return {
        "changed": (t != original),
        "before_chars": len(original),
        "after_chars": len(t),
        "text": t,
    }

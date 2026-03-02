from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class PolicyFinding:
    rule: str
    snippet: str


_YT_RISKY_PATTERNS: List[Tuple[str, str]] = [
    ("violence_graphic", r"\b(decapita|decapitaç|esquartej|mutila|tortur|sangue\s+espirr|cadáver\s+em\s+decomposi)"),
    ("sexual_minors", r"\b(pedof|estupro\s+de\s+crian|abuso\s+sexual\s+infant)"),
    ("hate_or_slurs", r"\b(nazis?mo|hitler|supremac|limpeza\s+étnica)"),
    ("self_harm", r"\b(suicid|auto\s*mutila|se\s+matou)"),
    ("weapons_instructions", r"\b(como\s+fazer\s+uma\s+bomba|fabricar\s+arma)"),
]

_SOFT_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bestupro\b", re.I), "violência sexual"),
    (re.compile(r"\bsuicid(?:io|ou|a)\b", re.I), "morte auto-infligida"),
    (re.compile(r"\bdecomposi(?:ção|cao)\b", re.I), "condição grave"),
]


def scan_youtube_policy_risks(text: str) -> List[PolicyFinding]:
    findings: List[PolicyFinding] = []
    for rule, pat in _YT_RISKY_PATTERNS:
        m = re.search(pat, text, flags=re.I)
        if m:
            snip = text[max(0, m.start()-40): m.end()+40]
            findings.append(PolicyFinding(rule=rule, snippet=snip))
    return findings


def soften_text_for_youtube(text: str) -> str:
    # Lightweight sanitization: soften certain explicit terms without changing meaning too much.
    out = text
    for pat, repl in _SOFT_REPLACEMENTS:
        out = pat.sub(repl, out)
    return out
def apply_policy_soften(text: str) -> str:
    """Compat wrapper (used by script_generator).

    Earlier versions imported `apply_policy_soften`; the actual implementation lives in
    `soften_text_for_youtube`. This keeps backwards compatibility.
    """
    return soften_text_for_youtube(text)

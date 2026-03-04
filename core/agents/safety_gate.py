from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple, Optional


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s


@dataclass
class SafetyFinding:
    level: str  # "block" | "warn"
    rule: str
    evidence: str


_DEFAULT_BLOCK_PHRASES = [
    # sexual violence / minors
    "abuso sexual",
    "violencia sexual",
    "assedio sexual",
    "estupro",
    "pedof",
    "pornografia infantil",
    "exploracao sexual",
    # self-harm
    "suicid",
    "auto mutil",
    "automutil",
    "enforc",
    # explicit gore / torture (keep small to avoid false positives)
    "decapit",
    "desmembr",
    "esquartej",
    "tortur",
]

_DEFAULT_MINOR_HINTS = [
    "crianca", "crianças", "menor", "menina", "menino", "infantil", "adolescente",
]

_DEFAULT_GORE_HINTS = [
    "sangue", "cadaver", "corpo", "morto", "assassin", "homicid", "massacre",
]


def _cfg_safety(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    s = (cfg or {}).get("safety") or {}
    return {
        "enabled": bool(s.get("enabled", True)),
        "max_regen_attempts": int(s.get("max_regen_attempts", 3)),
        "hard_fail": bool(s.get("hard_fail", False)),
        "block_phrases": list(s.get("block_phrases") or _DEFAULT_BLOCK_PHRASES),
        "minor_hints": list(s.get("minor_hints") or _DEFAULT_MINOR_HINTS),
        "gore_hints": list(s.get("gore_hints") or _DEFAULT_GORE_HINTS),
        "allow_sensitive_crime": bool(s.get("allow_sensitive_crime", False)),
    }


def scan_text(cfg: Optional[Dict[str, Any]], text: str) -> List[SafetyFinding]:
    """Heuristic safety scan to keep Shorts monetization-safe.

    Returns findings; caller decides to block/regen.
    """
    conf = _cfg_safety(cfg)
    if not conf["enabled"]:
        return []

    t = _norm(text)
    findings: List[SafetyFinding] = []

    def add(level: str, rule: str, evidence: str):
        findings.append(SafetyFinding(level=level, rule=rule, evidence=evidence[:160]))

    # Block phrases (strong indicators)
    for ph in conf["block_phrases"]:
        phn = _norm(ph)
        if phn and phn in t:
            add("block", "blocked_phrase", ph)

    # If mentions minors AND any sexual-violence indicator -> block hard
    minor = any(_norm(w) in t for w in conf["minor_hints"])
    sexual = any(_norm(w) in t for w in ["abuso sexual", "violencia sexual", "estupro", "pedof", "pornografia infantil", "exploracao sexual"])
    if minor and sexual:
        add("block", "minor_plus_sexual", "menor/criança + violência sexual")

    # Crime/violence warnings (can be acceptable if framed safely, but we prefer to avoid in safe-mode)
    if not conf["allow_sensitive_crime"]:
        crime = any(_norm(w) in t for w in conf["gore_hints"])
        if crime:
            add("warn", "crime_violence_hint", "menções a crime/violência")

    return findings


def should_block(cfg: Optional[Dict[str, Any]], findings: List[SafetyFinding]) -> bool:
    conf = _cfg_safety(cfg)
    if not conf["enabled"]:
        return False
    # Any block finding blocks
    if any(f.level == "block" for f in findings):
        return True
    # If we disallow crime/violence hints, treat warn as block? keep warn only.
    return False


def redact_for_prompts(cfg: Optional[Dict[str, Any]], text: str) -> str:
    """Remove/neutralize sensitive phrases for image prompting (never include explicit terms)."""
    conf = _cfg_safety(cfg)
    t = text or ""
    # Always remove explicit blocked phrases from prompts
    for ph in conf["block_phrases"]:
        if not ph:
            continue
        # case-insensitive replacement (keep coarse)
        t = re.sub(re.escape(ph), "conteúdo sensível", t, flags=re.IGNORECASE)
    # Also neutralize common explicit words
    t = re.sub(r"\b(estupro|pedof\w*|abuso sexual|pornografia infantil)\b", "conteúdo sensível", t, flags=re.IGNORECASE)
    return t

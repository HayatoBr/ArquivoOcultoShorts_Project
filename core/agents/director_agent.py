from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DirectorDecision:
    approved: bool
    score: int
    reasons: List[str]
    rewrite_text: str = ""
    suggested_title: str = ""
    scene_beats: List[str] = None  # type: ignore[assignment]


def _get_director_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("director", {}) or {}


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from an LLM response."""
    if not text:
        return None
    text = text.strip()
    # Direct JSON
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Try to extract the first {...} block
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    chunk = m.group(0)
    try:
        obj = json.loads(chunk)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _heuristic_is_generic_pt(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) < 220:
        return True
    # Strong signals of encyclopedic definition
    generic_markers = [
        "é o estudo",
        "é a ciência",
        "é considerado",
        "define-se",
        "refere-se",
        "é uma área",
    ]
    if any(g in t[:500] for g in generic_markers):
        return True
    # Too few proper nouns / dates (very rough)
    has_year = bool(re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text))
    has_caps = len(re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+\b", text)) >= 5
    return not (has_year or has_caps)


def director_review(
    cfg: Optional[Dict[str, Any]],
    script_text: str,
    llm: Any = None,
    *,
    test_mode: bool = False,
) -> DirectorDecision:
    """Validate / rewrite the script using an Ollama "director".

    Returns a DirectorDecision with approve/veto and an optional rewritten script.
    """
    dcfg = _get_director_cfg(cfg)
    enabled = bool(dcfg.get("enabled", True))
    min_score = int(dcfg.get("min_score", 7))
    if not enabled:
        return DirectorDecision(approved=True, score=10, reasons=["director_disabled"], rewrite_text="", scene_beats=[])

    # If script is clearly generic, we still ask the LLM to rewrite, but we already treat it as "not approved".
    generic_flag = _heuristic_is_generic_pt(script_text)

    # No LLM available -> heuristic-only decision
    if llm is None or not hasattr(llm, "generate"):
        if generic_flag:
            return DirectorDecision(approved=False, score=3, reasons=["heuristic_generic"], rewrite_text="", scene_beats=[])
        return DirectorDecision(approved=True, score=8, reasons=["heuristic_ok"], rewrite_text="", scene_beats=[])

    niche = ((cfg or {}).get("channel") or {}).get("niche", "mistério investigativo")
    target_seconds = int((((cfg or {}).get("video") or {}).get("seconds", 60)))

    prompt = (
        "Você é o DIRETOR/QA de um canal de YouTube Shorts investigativos.\n"
        "Sua tarefa: avaliar o roteiro e decidir se está BOM para um short de ~60s, ou se está genérico/enciclopédico.\n\n"
        "Regras obrigatórias:\n"
        "- Precisa começar com GANCHO forte nos primeiros 3-5 segundos.\n"
        "- Precisa ser investigativo (mistério, evidência, documento, pergunta, tensão).\n"
        "- Não pode ser definição genérica de Wikipedia (ex: 'X é o estudo de...').\n"
        "- Precisa ser específico (nomes/datas/locais) ou pelo menos um CASO claro.\n"
        "- Deve caber em aproximadamente "+str(target_seconds)+" segundos.\n"
        "- Linguagem: PT-BR.\n"
        "- Nicho: "+str(niche)+".\n\n"
        "Saída: responda APENAS em JSON, sem texto extra.\n"
        "Formato JSON:\n"
        "{\n"
        "  \"approved\": true|false,\n"
        "  \"score\": 0-10,\n"
        "  \"reasons\": [\"...\"],\n"
        "  \"rewrite_text\": \"...\",\n"
        "  \"suggested_title\": \"...\",\n"
        "  \"scene_beats\": [\"...\"]\n"
        "}\n\n"
        "ROTEIRO PARA AVALIAR:\n" + script_text
    )

    raw = str(llm.generate(prompt) or "").strip()
    obj = _extract_json(raw) or {}

    approved = bool(obj.get("approved", False)) and (not generic_flag)
    score = int(obj.get("score", 0) or 0)
    reasons = obj.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]

    rewrite_text = str(obj.get("rewrite_text") or "").strip()
    suggested_title = str(obj.get("suggested_title") or "").strip()
    scene_beats = obj.get("scene_beats") or []
    if not isinstance(scene_beats, list):
        scene_beats = [str(scene_beats)]

    # Force veto if generic heuristics trigger
    if generic_flag:
        if "heuristic_generic" not in reasons:
            reasons.insert(0, "heuristic_generic")
        approved = False
        score = min(score if score else 4, 4)

    # Enforce threshold
    if score < min_score:
        approved = False

    return DirectorDecision(
        approved=approved,
        score=score,
        reasons=[str(r) for r in reasons],
        rewrite_text=rewrite_text,
        suggested_title=suggested_title,
        scene_beats=[str(s) for s in scene_beats],
    )


def apply_director_gate(
    cfg: Optional[Dict[str, Any]],
    script_text: str,
    llm: Any = None,
    *,
    test_mode: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """Runs director review and (optionally) rewrites the script.

    Returns (final_script_text, report_dict)
    """
    dcfg = _get_director_cfg(cfg)
    max_rewrites = int(dcfg.get("max_rewrites", 2))
    hard_fail = bool(dcfg.get("hard_fail", False))

    attempts = 0
    report: Dict[str, Any] = {"attempts": []}
    cur = script_text

    while True:
        attempts += 1
        dec = director_review(cfg, cur, llm=llm, test_mode=test_mode)
        attempt = {
            "attempt": attempts,
            "approved": dec.approved,
            "score": dec.score,
            "reasons": dec.reasons,
            "suggested_title": dec.suggested_title,
            "scene_beats": dec.scene_beats or [],
            "did_rewrite": False,
        }

        if dec.approved:
            report["final"] = attempt
            report["approved"] = True
            report["final_score"] = dec.score
            report["final_reasons"] = dec.reasons
            report["suggested_title"] = dec.suggested_title
            report["scene_beats"] = dec.scene_beats or []
            report["attempts"].append(attempt)
            return cur, report

        # Try rewrite if provided and we still have budget
        if attempts <= max_rewrites and dec.rewrite_text:
            cur = dec.rewrite_text.strip()
            attempt["did_rewrite"] = True
            report["attempts"].append(attempt)
            continue

        # No approval and no more rewrites
        report["attempts"].append(attempt)
        report["approved"] = False
        report["final_score"] = dec.score
        report["final_reasons"] = dec.reasons
        report["suggested_title"] = dec.suggested_title
        report["scene_beats"] = dec.scene_beats or []

        if hard_fail:
            raise RuntimeError(f"Director reprovou o roteiro (score={dec.score}): {dec.reasons}")
        return cur, report

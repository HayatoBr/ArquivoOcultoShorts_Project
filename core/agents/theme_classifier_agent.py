from __future__ import annotations

import re
from typing import Optional, Dict, Any

THEMES = ("desaparecimento", "caso_historico", "conspiracao", "default")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def llm_classify_theme(
    llm,
    text: str,
    *,
    language: str = "pt-BR",
    max_chars: int = 6000,
) -> Optional[str]:
    """Classify theme using an LLM. Returns one of THEMES or None on failure."""
    if llm is None:
        return None

    prompt = f"""
Você é um classificador de tema para um canal investigativo de vídeos curtos.
Escolha APENAS uma das opções:
- desaparecimento
- caso_historico
- conspiracao
- default

Regras:
- Se o texto for sobre pessoas sumidas, 'última vez visto', buscas, pistas: desaparecimento.
- Se o texto for sobre eventos antigos (século, ano histórico, arquivo/relatos antigos): caso_historico.
- Se o texto for sobre encobrimento, evidências controversas, teorias, governo/organizações escondendo: conspiracao.
- Caso não encaixe claramente: default.

Responda APENAS com UMA palavra (uma das opções).

Texto:
{_clean(text)[:max_chars]}
""".strip()

    try:
        out = llm(prompt) if callable(llm) else llm.generate(prompt)
    except Exception:
        return None

    out = _clean(out).lower()
    out = re.sub(r"[^a-z_]", "", out)

    if out in THEMES:
        return out

    # tolerate small variations
    if "desapare" in out:
        return "desaparecimento"
    if "histor" in out:
        return "caso_historico"
    if "consp" in out:
        return "conspiracao"

    return None


def resolve_theme_from_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    images = cfg.get("images") or {}
    tp = images.get("theme_presets") or {}
    return {
        "enabled": bool(tp.get("enabled", True)),
        "use_llm": bool(tp.get("use_llm", False)),
        "language": (tp.get("language") or "pt-BR"),
    }

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional

from core.agents.theme_classifier_agent import llm_classify_theme, resolve_theme_from_cfg
from core.agents.theme_preset_catalog_agent import load_catalog, select_preset_for_theme

DEFAULT_CATALOG_PATH = Path("presets/theme_presets_catalog.json")
JOB_PRESET_ID_FILENAME = "job_theme_preset_id.txt"


def _read_if_exists(p: Path) -> str:
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        try:
            return p.read_text(encoding="utf-8-sig").strip()
        except Exception:
            return ""
    return ""


def detect_theme_heuristic(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["desapareceu", "desaparecimento", "sumiu", "última vez visto", "ultima vez visto"]):
        return "desaparecimento"
    if any(k in t for k in ["histórico", "historico", "século", "seculo", "em 19", "em 18", "arquivo", "relatos antigos"]):
        return "caso_historico"
    if any(k in t for k in ["conspiração", "conspiracao", "encoberto", "teoria", "governo esconde", "evidências controversas", "evidencias controversas"]):
        return "conspiracao"
    return "default"


def resolve_theme_preset(
    text: str,
    *,
    llm=None,
    cfg: Optional[Dict[str, Any]] = None,
    job_id: str = "",
    job_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    enabled = True
    use_llm = False
    language = "pt-BR"
    catalog_path = str(DEFAULT_CATALOG_PATH)
    deterministic = False

    if cfg is not None:
        info = resolve_theme_from_cfg(cfg)
        enabled = bool(info.get("enabled", True))
        use_llm = bool(info.get("use_llm", False))
        language = info.get("language") or "pt-BR"
        images = cfg.get("images") or {}
        tp = images.get("theme_presets") or {}
        catalog_path = (tp.get("catalog_path") or catalog_path)
        deterministic = bool(tp.get("deterministic", False))

    if not enabled:
        return {"theme": "disabled", "preset": {}, "method": "disabled", "selection": {}}

    # Forced preset ID (job override file)
    forced_id = ""
    if job_dir is not None:
        forced_id = _read_if_exists(job_dir / JOB_PRESET_ID_FILENAME)

    theme = None
    method = "heuristic"
    if use_llm and llm is not None:
        theme = llm_classify_theme(llm, text, language=language)
        if theme:
            method = "llm"
    if not theme:
        theme = detect_theme_heuristic(text)
        method = "heuristic"

    preset = {}
    selection_meta = {}
    try:
        path = Path(catalog_path)
        if path.exists():
            cat = load_catalog(path)
            preset, selection_meta = select_preset_for_theme(
                cat,
                theme,
                job_id=job_id,
                deterministic=deterministic,
                forced_preset_id=forced_id,
            )
            # If forced preset id moved theme, reflect in theme too
            if selection_meta.get("theme") and selection_meta.get("theme") != theme:
                theme = selection_meta["theme"]
        else:
            preset = {}
            selection_meta = {"catalog_path": catalog_path, "method": "missing"}
    except Exception as e:
        preset = {}
        selection_meta = {"catalog_path": catalog_path, "method": "error", "error": str(e)}

    if forced_id and selection_meta.get("method") != "forced_id":
        selection_meta["forced_id"] = forced_id
        selection_meta["forced_id_status"] = "not_found"

    return {"theme": theme, "preset": preset or {}, "method": method, "selection": selection_meta}

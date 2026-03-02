from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional


JOB_PRESET_ID_FILENAME = "job_theme_preset_id.txt"
JOB_PRESET_META_FILENAME = "job_theme_preset_meta.json"


def _read_text(p: Path) -> str:
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return p.read_text(encoding=enc).strip()
        except Exception:
            pass
    try:
        return p.read_text(errors="ignore").strip()
    except Exception:
        return ""


def _write_text(p: Path, text: str):
    p.write_text((text or "").strip() + "\n", encoding="utf-8")


def _write_json(p: Path, obj: Dict[str, Any]):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_job_theme_preset_id(
    *,
    job_dir: Path,
    script_text: str,
    cfg: Dict[str, Any],
    llm=None,
) -> Optional[str]:
    """Zero-config: if job_theme_preset_id.txt missing, auto-select and write it.

    Returns the chosen preset id (or None if not available).
    """
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    id_path = job_dir / JOB_PRESET_ID_FILENAME
    meta_path = job_dir / JOB_PRESET_META_FILENAME

    # If already fixed, keep it.
    if id_path.exists():
        try:
            return _read_text(id_path) or None
        except Exception:
            return None

    images = cfg.get("images") or {}
    tp = images.get("theme_presets") or {}
    enabled = bool(tp.get("enabled", True))
    auto_write = bool(tp.get("auto_write_job_preset_id", True))
    if not (enabled and auto_write):
        return None

    try:
        from core.agents.theme_presets_manager import resolve_theme_preset
    except Exception:
        return None

    job_id = job_dir.name
    info = resolve_theme_preset(script_text or "", llm=llm, cfg=cfg, job_id=job_id, job_dir=job_dir)
    selection = info.get("selection") or {}
    chosen_id = selection.get("chosen_id") or (info.get("preset") or {}).get("id")

    if not chosen_id:
        return None

    try:
        _write_text(id_path, str(chosen_id))
        _write_json(meta_path, {
            "job_id": job_id,
            "theme": info.get("theme"),
            "method": info.get("method"),
            "selection": selection,
        })
    except Exception:
        # best-effort; don't fail pipeline
        return str(chosen_id)

    return str(chosen_id)

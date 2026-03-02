from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


def load_catalog(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_seed_from_job_id(job_id: str) -> int:
    """Stable 32-bit FNV-1a seed from job_id (cross-run stable)."""
    s = (job_id or "").encode("utf-8", errors="ignore")
    h = 2166136261
    for b in s:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return int(h & 0x7FFFFFFF) or 1337


def _weighted_choice(items: List[Dict[str, Any]], rnd: random.Random) -> Dict[str, Any]:
    total = 0.0
    weights = []
    for it in items:
        w = float(it.get("weight", 1.0))
        weights.append(max(0.0, w))
        total += max(0.0, w)
    if total <= 0.0:
        return items[0]
    r = rnd.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if r <= acc:
            return it
    return items[-1]


def _find_by_id(items: List[Dict[str, Any]], preset_id: str) -> Optional[Dict[str, Any]]:
    pid = (preset_id or "").strip()
    if not pid:
        return None
    for it in items:
        if (it.get("id") or "").strip() == pid:
            return it
    return None


def select_preset_for_theme(
    catalog: Dict[str, Any],
    theme: str,
    *,
    job_id: str = "",
    deterministic: bool = False,
    forced_preset_id: str = "",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    themes = (catalog.get("themes") or {})
    items = themes.get(theme) or themes.get("default") or []
    if not items:
        return ({}, {"theme": theme, "method": "none"})

    # Forced preset id (job override)
    forced = _find_by_id(items, forced_preset_id)
    if forced is None and forced_preset_id:
        # Try searching across all themes (useful if user copy/pasted wrong theme)
        for _t, _items in themes.items():
            forced = _find_by_id(_items or [], forced_preset_id)
            if forced is not None:
                items = _items
                theme = _t
                break

    if forced is not None:
        meta = {
            "theme": theme,
            "method": "forced_id",
            "catalog_version": catalog.get("version"),
            "job_seed": None,
            "chosen_id": forced.get("id"),
            "forced_id": forced_preset_id,
            "candidates": [it.get("id") for it in items],
        }
        return forced, meta

    sel = catalog.get("selection") or {}
    mode = (sel.get("mode") or "weighted_random").lower()
    seed_from_job = bool(sel.get("seed_from_job", True))

    seed = 1337
    if seed_from_job and job_id:
        seed = stable_seed_from_job_id(job_id)

    rnd = random.Random(seed)

    if deterministic or mode == "deterministic":
        chosen = items[0]
        method = "deterministic"
    else:
        chosen = _weighted_choice(items, rnd)
        method = "weighted_random"

    meta = {
        "theme": theme,
        "method": method,
        "catalog_version": catalog.get("version"),
        "job_seed": seed,
        "chosen_id": chosen.get("id"),
        "candidates": [it.get("id") for it in items],
    }
    return chosen, meta

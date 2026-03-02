from __future__ import annotations

import copy
import json
from typing import Dict, Any, List, Tuple


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _coerce_weight(v: Any) -> float:
    try:
        w = float(v)
    except Exception:
        w = 1.0
    if w < 0:
        w = 0.0
    return w


def normalize_catalog(catalog: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize catalog deterministically."""
    changes: List[str] = []
    cat = copy.deepcopy(catalog) if isinstance(catalog, dict) else {}
    if not isinstance(cat, dict):
        cat = {}
        changes.append("reset_catalog_to_dict")

    if "version" not in cat:
        cat["version"] = "1.0"
        changes.append("set_default_version")

    sel = cat.get("selection")
    if not isinstance(sel, dict):
        sel = {"mode": "weighted_random", "seed_from_job": True}
        cat["selection"] = sel
        changes.append("set_default_selection")

    mode = (sel.get("mode") or "weighted_random")
    if mode not in ("weighted_random", "deterministic"):
        sel["mode"] = "weighted_random"
        changes.append("fix_selection_mode")
    if "seed_from_job" not in sel:
        sel["seed_from_job"] = True
        changes.append("set_seed_from_job_true")

    themes = cat.get("themes")
    if not isinstance(themes, dict):
        themes = {}
        cat["themes"] = themes
        changes.append("create_themes_dict")

    known_fields = {"id", "weight", "visual_profile", "negative_profile", "character_anchor_hint"}

    new_themes: Dict[str, Any] = {}
    for theme_name in sorted(themes.keys()):
        items = themes.get(theme_name)
        if not isinstance(items, list):
            continue

        normalized_items = []
        for it in items:
            if not isinstance(it, dict):
                changes.append(f"drop_non_dict_item:{theme_name}")
                continue

            pid = (it.get("id") or "").strip()
            if not pid:
                changes.append(f"drop_missing_id:{theme_name}")
                continue

            out: Dict[str, Any] = {}
            out["id"] = pid
            out["weight"] = _coerce_weight(it.get("weight", 1.0))

            for f in ("visual_profile", "negative_profile", "character_anchor_hint"):
                val = it.get(f)
                if isinstance(val, str):
                    val = val.strip()
                if not _is_empty(val):
                    out[f] = val

            if any(k not in known_fields for k in it.keys()):
                changes.append(f"drop_unknown_fields:{pid}")

            normalized_items.append(out)

        normalized_items.sort(key=lambda x: x.get("id", ""))
        new_themes[theme_name] = normalized_items

    cat["themes"] = new_themes

    for k in list(cat.keys()):
        if _is_empty(cat[k]):
            del cat[k]
            changes.append(f"remove_empty_root:{k}")

    return cat, changes


def catalogs_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    try:
        return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    except Exception:
        return a == b

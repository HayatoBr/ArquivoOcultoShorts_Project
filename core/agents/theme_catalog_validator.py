from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


REQUIRED_THEMES = ("desaparecimento", "caso_historico", "conspiracao", "default")


MIN_PRESETS = {
    "desaparecimento": [
        {
            "id": "desaparecimento_auto_min_v1",
            "weight": 1.0,
            "visual_profile": "cold desaturated palette, foggy atmosphere, low light, subtle film grain, investigative tone",
            "negative_profile": "bright sunny lighting, vibrant colors, cheerful mood",
            "character_anchor_hint": "investigador tenso, olhar preocupado, ambiente frio e sombrio",
        }
    ],
    "caso_historico": [
        {
            "id": "caso_historico_auto_min_v1",
            "weight": 1.0,
            "visual_profile": "documentary realism, slightly faded colors, archival look, soft contrast",
            "negative_profile": "modern neon lighting, futuristic elements",
            "character_anchor_hint": "narrador documental, expressão neutra, estilo clássico",
        }
    ],
    "conspiracao": [
        {
            "id": "conspiracao_auto_min_v1",
            "weight": 1.0,
            "visual_profile": "dark noir lighting, strong shadows, high contrast, dramatic atmosphere",
            "negative_profile": "bright comedy style, colorful cartoonish look",
            "character_anchor_hint": "investigador desconfiado, luz lateral dramática",
        }
    ],
    "default": [
        {
            "id": "default_auto_min_v1",
            "weight": 1.0,
            "visual_profile": "cinematic investigative lighting, documentary realism, subtle film grain",
            "negative_profile": "cartoon style, bright neon colors, cheerful mood",
            "character_anchor_hint": "investigador sério, luz lateral suave, close-up cinematográfico",
        }
    ],
}


def load_catalog(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_catalog(catalog: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    themes = catalog.get("themes")
    if not isinstance(themes, dict) or not themes:
        errors.append("Catalog inválido: 'themes' ausente ou vazio.")
        return False, errors

    seen_ids = set()

    for theme_name, items in themes.items():
        if not isinstance(items, list) or not items:
            errors.append(f"Tema '{theme_name}' não possui presets válidos.")
            continue

        for idx, item in enumerate(items):
            pid = item.get("id")
            if not pid:
                errors.append(f"Tema '{theme_name}' item #{idx} sem 'id'.")
                continue

            if pid in seen_ids:
                errors.append(f"ID duplicado encontrado: '{pid}'.")
            seen_ids.add(pid)

            weight = item.get("weight", 1.0)
            try:
                float(weight)
            except Exception:
                errors.append(f"Peso inválido no preset '{pid}'.")

    return len(errors) == 0, errors


def ensure_default_catalog(path: Path) -> bool:
    """Create a minimal catalog if file is missing."""
    if path.exists():
        return False

    default_catalog = {
        "version": "1.0-auto",
        "selection": {"mode": "weighted_random", "seed_from_job": True},
        "themes": {"default": MIN_PRESETS["default"]},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(default_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def ensure_minimum_themes(catalog: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Ensure required themes exist and have at least 1 preset. Returns (catalog, changes)."""
    changes: List[str] = []

    if not isinstance(catalog, dict):
        catalog = {}
        changes.append("catalog_reset_to_dict")

    if "version" not in catalog:
        catalog["version"] = "1.0-auto"
        changes.append("set_version_1.0-auto")

    if "selection" not in catalog or not isinstance(catalog.get("selection"), dict):
        catalog["selection"] = {"mode": "weighted_random", "seed_from_job": True}
        changes.append("set_default_selection")

    themes = catalog.get("themes")
    if not isinstance(themes, dict):
        themes = {}
        catalog["themes"] = themes
        changes.append("create_themes_dict")

    for th in REQUIRED_THEMES:
        items = themes.get(th)
        if not isinstance(items, list) or len(items) == 0:
            themes[th] = list(MIN_PRESETS[th])
            changes.append(f"add_min_theme:{th}")

    # Deduplicate IDs by adding suffix if necessary (rare but safe)
    seen = set()
    for th, items in themes.items():
        if not isinstance(items, list):
            continue
        for it in items:
            pid = (it.get("id") or "").strip()
            if not pid:
                continue
            if pid in seen:
                # append suffix
                n = 2
                new_id = f"{pid}_{n}"
                while new_id in seen:
                    n += 1
                    new_id = f"{pid}_{n}"
                it["id"] = new_id
                changes.append(f"dedupe_id:{pid}->{new_id}")
                pid = new_id
            seen.add(pid)

    return catalog, changes


def write_catalog(path: Path, catalog: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

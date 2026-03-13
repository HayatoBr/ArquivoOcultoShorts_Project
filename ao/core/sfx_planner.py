
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import random


def _resolve_cat_dir(base_dir: Path, category: str) -> Path:
    direct = base_dir / category
    nested = base_dir / 'sfx' / category
    if direct.exists():
        return direct
    if nested.exists():
        return nested
    return direct


def _pick_file(cat_dir: Path) -> Optional[str]:
    if not cat_dir.exists():
        return None
    files = sorted([p for p in cat_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.wav', '.mp3', '.m4a'}])
    if not files:
        return None
    return str(random.choice(files))


def plan_sfx_events(scene_plan: List[Dict[str, Any]], sfx_base_dir: str | Path | None) -> List[Dict[str, Any]]:
    if not sfx_base_dir:
        return []
    base_dir = Path(sfx_base_dir)
    mapping = {
        'establishing': ('ambience', 0.18),
        'character': ('archive', 0.22),
        'detail': ('archive', 0.22),
        'evidence': ('hits', 0.35),
        'investigation': ('archive', 0.24),
        'reenactment': ('hits', 0.32),
        'ending': ('transitions', 0.28),
    }
    events: List[Dict[str, Any]] = []
    for idx, beat in enumerate(scene_plan):
        scene_type = (beat.get('scene_type') or 'detail').strip().lower()
        category, vol = mapping.get(scene_type, ('transitions', 0.22))
        path = _pick_file(_resolve_cat_dir(base_dir, category))
        if not path:
            continue
        start = float(beat.get('start_seconds') or 0.0)
        if idx > 0:
            start = max(0.0, start - 0.12)
        events.append({
            'path': path,
            'start_seconds': round(start, 3),
            'volume': vol,
            'category': category,
            'scene_index': beat.get('scene_index', idx + 1),
        })
    return events

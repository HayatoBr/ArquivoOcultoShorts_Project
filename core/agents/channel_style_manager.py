from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

CHANNEL_STYLE_FILENAME = "channel_visual_profile.txt"

DEFAULT_PROFILE_PT = (
    "cinematic documentary noir, desaturated color palette, teal-blue shadows, warm highlights, "
    "high contrast, subtle film grain, anamorphic lens look, shallow depth of field, "
    "moody lighting, investigative atmosphere"
)

def get_channel_style(project_root: Path) -> Optional[str]:
    path = project_root / CHANNEL_STYLE_FILENAME
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None

def ensure_channel_style(project_root: Path, profile_text: str = DEFAULT_PROFILE_PT) -> str:
    """Create the global channel visual profile file if missing and return the profile."""
    path = project_root / CHANNEL_STYLE_FILENAME
    if not path.exists():
        path.write_text(profile_text.strip() + "\n", encoding="utf-8")
        return profile_text.strip()
    return path.read_text(encoding="utf-8").strip()

def build_profile_from_config(cfg: Dict[str, Any]) -> str:
    images = cfg.get("images") or {}
    ch = images.get("channel_profile") or {}
    parts = []
    for k in ("palette", "lighting", "lens", "film"):
        v = (ch.get(k) or "").strip()
        if v:
            parts.append(v)
    v = (ch.get("extra") or "").strip()
    if v:
        parts.append(v)
    return ", ".join([p for p in parts if p]).strip()

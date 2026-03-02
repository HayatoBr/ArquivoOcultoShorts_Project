from __future__ import annotations
from pathlib import Path
from typing import Optional

CHANNEL_ANCHOR_FILENAME = "channel_character_anchor.txt"

def get_channel_anchor(project_root: Path) -> Optional[str]:
    path = project_root / CHANNEL_ANCHOR_FILENAME
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None

def save_channel_anchor(project_root: Path, anchor_text: str):
    path = project_root / CHANNEL_ANCHOR_FILENAME
    path.write_text(anchor_text.strip(), encoding="utf-8")

from __future__ import annotations

from pathlib import Path
from typing import Optional

CHANNEL_NEGATIVE_FILENAME = "channel_negative_profile.txt"

DEFAULT_NEGATIVE = (
    "bad anatomy, deformed, mutated, extra fingers, missing fingers, fused fingers, "
    "bad hands, poorly drawn hands, disfigured, cross-eye, blurry, lowres, "
    "text, watermark, logo, signature, jpeg artifacts, worst quality, low quality"
)

def get_channel_negative(project_root: Path) -> Optional[str]:
    path = project_root / CHANNEL_NEGATIVE_FILENAME
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None

def ensure_channel_negative(project_root: Path, negative_text: str = DEFAULT_NEGATIVE) -> str:
    path = project_root / CHANNEL_NEGATIVE_FILENAME
    if not path.exists():
        path.write_text(negative_text.strip() + "\n", encoding="utf-8")
        return negative_text.strip()
    return path.read_text(encoding="utf-8").strip()

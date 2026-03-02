# -*- coding: utf-8 -*-
"""Builds SD prompts per scene (safe, documentary style)."""

import re
from typing import Dict, Optional

DEFAULT_NEG = (
    "cartoon, anime, illustration, lowres, blurry, pixelated, watermark, logo, text, "
    "bad anatomy, bad hands, extra fingers, deformed, mutated, nude, gore, blood"
)

def _clean(txt: str) -> str:
    txt = (txt or "").strip()
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"^(t[ií]tulo|t[ií]tulo da cena|cena|scene)\s*:\s*", "", txt, flags=re.I)
    return txt

def build_scene_prompt(scene_text: str, channel_style: Optional[str] = None) -> Dict[str, str]:
    st = _clean(scene_text)
    style = channel_style or (
        "documentary still, cinematic, realistic, moody lighting, film grain, "
        "investigation board, evidence, archival vibe, 35mm lens"
    )
    prompt = f"{style}. {st}. ultra realistic, high detail"
    prompt = prompt.replace("sangue", "mancha escura").replace("cadáver", "silhueta")
    return {"prompt": prompt, "negative_prompt": DEFAULT_NEG}

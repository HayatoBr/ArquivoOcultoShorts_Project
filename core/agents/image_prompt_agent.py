from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import os

from .scene_splitter_agent import split_script_into_scenes, Scene
from .character_anchor_agent import build_character_anchor
from .clip_tokenizer import sanitize_for_clip


@dataclass
class ScenePrompt:
    idx: int
    kind: str
    prompt: str
    negative_prompt: str


_DEFAULT_BASE = (
    "cinematic, dramatic lighting, realistic, film grain, shallow depth of field, " 
    "close-up framing, high detail"
)

_DEFAULT_NEG = (
    "text, watermark, logo, blurry, lowres, bad anatomy, bad hands, extra fingers, " 
    "deformed, distorted face, mutated, disfigured, cropped, out of frame, jpeg artifacts"
)


def _style_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return ((cfg or {}).get("image_style") or {})


def _get_base_and_neg(cfg: Optional[Dict[str, Any]]) -> tuple[str, str]:
    sc = _style_cfg(cfg)
    base = str(sc.get("base_prompt") or _DEFAULT_BASE).strip()
    neg = str(sc.get("negative_prompt") or _DEFAULT_NEG).strip()
    return base, neg


def _scene_template(kind: str) -> str:
    # Templates emphasize channel look: close-up for character scenes, wide for environment.
    if kind == "environment":
        return "moody investigative environment, documentary still, atmospheric fog, empty streets, archival feel"
    if kind == "detail":
        return "macro detail shot, evidence-focused, newspaper clipping, old photograph, detective board, gritty texture"
    if kind == "climax":
        return "dramatic reveal moment, intense cinematic lighting, tension, mystery, final impact"
    # character default
    return "close-up cinematic portrait, shoulders up, serious expression, investigative mood"


def build_scene_prompts(script_text: str, max_scenes: int = 5, cfg: Optional[Dict[str, Any]] = None) -> List[ScenePrompt]:
    """Build CLIP-safe per-scene prompts with stable identity + base/negative prompts.

    Backwards compatible signature: build_scene_prompts(text, max_scenes=1) still works.
    """
    # Determine number of scenes from cfg if present
    if cfg is not None:
        try:
            max_scenes = int(((cfg.get("images") or {}).get("max_scenes")) or max_scenes)
        except Exception:
            pass

    max_scenes = int(max(3, min(6, max_scenes)))
    scenes = split_script_into_scenes(script_text, max_scenes=max_scenes)

    anchor = build_character_anchor(script_text).description
    base, neg = _get_base_and_neg(cfg)

    prompts: List[ScenePrompt] = []
    for sc in scenes:
        template = _scene_template(sc.kind)

        # Build scene-specific descriptor from text (short, CLIP-safe)
        # We keep only a short excerpt to avoid token overflow
        excerpt = sc.text
        excerpt = excerpt.replace("\n", " ").strip()
        excerpt = sanitize_for_clip(excerpt, max_words=28)

        # Compose prompt
        if sc.kind in ("character", "climax"):
            p = f"{base}, {anchor}, {template}, {excerpt}"
        else:
            p = f"{base}, {template}, {excerpt}"

        p = sanitize_for_clip(p, max_words=55)
        prompts.append(ScenePrompt(idx=sc.idx, kind=sc.kind, prompt=p, negative_prompt=neg))

    return prompts


def to_json_list(scene_prompts: List[ScenePrompt]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in scene_prompts]

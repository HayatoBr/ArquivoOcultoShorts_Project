from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import json
from pathlib import Path

from .clip_tokenizer import sanitize_for_clip
from .character_anchor_agent import build_character_anchor
from .scene_splitter_agent import split_script_into_scenes
from .visual_translator_agent import translate_scenes, VisualScene


@dataclass
class ScenePrompt:
    idx: int
    kind: str
    prompt: str
    negative_prompt: str


# NOTE: keep base style neutral; framing lives in templates per kind.
_DEFAULT_BASE = (
    "cinematic, documentary realism, film grain, high detail, dramatic lighting, "
    "shallow depth of field"
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
    # Templates determine camera & composition.
    if kind == "environment":
        return "wide shot, establishing scene, moody investigative atmosphere, archival documentary still"
    if kind == "detail":
        return "macro shot, evidence-focused objects, gritty texture, high contrast"
    if kind == "climax":
        return "dramatic reveal moment, cinematic lighting, tension, mystery, impactful composition"
    # character default (only when used)
    return "close-up portrait, shoulders up, serious expression, investigative mood, consistent identity"


def _visual_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("visual_translator", {}) or {}


def _use_visual_translator(cfg: Optional[Dict[str, Any]]) -> bool:
    vc = _visual_cfg(cfg)
    return bool(vc.get("enabled", True))


def _build_from_visual_scenes(script_text: str, cfg: Optional[Dict[str, Any]]) -> List[ScenePrompt]:
    vc = _visual_cfg(cfg)
    max_scenes = int(vc.get("max_scenes", 4))
    max_scenes = max(3, min(6, max_scenes))

    base, neg = _get_base_and_neg(cfg)
    anchor = build_character_anchor(script_text).description

    scenes, provider_used = translate_scenes(script_text, cfg=cfg or {}, test_mode=bool(((cfg or {}).get("llm") or {}).get("test_mode", False)))
    scenes = scenes[:max_scenes]

    # Persist trace in job folder when possible (same behavior as old splitter)
    try:
        job_dir = Path((cfg or {}).get("job_dir") or "")
        if job_dir and job_dir.exists():
            (job_dir / "visual_translator_meta.json").write_text(
                json.dumps({"provider": provider_used}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass

    out: List[ScenePrompt] = []
    for sc in scenes:
        template = _scene_template(sc.kind)
        visual = sanitize_for_clip(sc.visual, max_words=int(vc.get("max_visual_words", 35)))

        # Compose prompt: base + template + (optional) anchor + visual core
        if sc.kind == "character":
            p = f"{base}, {anchor}, {template}, {visual}"
        else:
            p = f"{base}, {template}, {visual}"

        # Final clamp to avoid CLIP>77 (roughly)
        p = sanitize_for_clip(p, max_words=int(vc.get("max_prompt_words", 48)))
        n = sc.negative_prompt.strip() if sc.negative_prompt else neg
        n = sanitize_for_clip(n, max_words=28)
        out.append(ScenePrompt(idx=sc.idx, kind=sc.kind, prompt=p, negative_prompt=n))
    return out


def _build_from_splitter(script_text: str, max_scenes: int, cfg: Optional[Dict[str, Any]]) -> List[ScenePrompt]:
    # Legacy deterministic splitter
    max_scenes = int(max(3, min(6, max_scenes)))
    scenes = split_script_into_scenes(script_text, max_scenes=max_scenes)

    anchor = build_character_anchor(script_text).description
    base, neg = _get_base_and_neg(cfg)

    prompts: List[ScenePrompt] = []
    for sc in scenes:
        template = _scene_template(sc.kind)
        excerpt = sc.text.replace("\n", " ").strip()
        excerpt = sanitize_for_clip(excerpt, max_words=18)  # shorter to avoid overflows

        if sc.kind == "character":
            p = f"{base}, {anchor}, {template}, {excerpt}"
        else:
            p = f"{base}, {template}, {excerpt}"

        p = sanitize_for_clip(p, max_words=45)
        prompts.append(ScenePrompt(idx=sc.idx, kind=sc.kind, prompt=p, negative_prompt=neg))

    return prompts


def build_scene_prompts(script_text: str, max_scenes: int = 5, cfg: Optional[Dict[str, Any]] = None) -> List[ScenePrompt]:
    """Build per-scene prompts.

    Default path uses Visual Translator (LLM) to avoid literal script copying and improve relevance.
    """
    # Determine number of scenes from cfg if present
    if cfg is not None:
        try:
            max_scenes = int(((cfg.get("images") or {}).get("max_scenes")) or max_scenes)
        except Exception:
            pass

    if _use_visual_translator(cfg):
        return _build_from_visual_scenes(script_text, cfg)

    return _build_from_splitter(script_text, max_scenes=max_scenes, cfg=cfg)


def to_json_list(scene_prompts: List[ScenePrompt]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in scene_prompts]

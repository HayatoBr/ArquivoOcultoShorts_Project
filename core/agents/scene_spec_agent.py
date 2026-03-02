from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.agents.prompt_visual_agent import PromptVisualAgent
from core.agents.scene_splitter import split_script_into_scenes
from core.agents.channel_style_manager import get_channel_visual_profile, get_channel_negative_profile
from core.agents.character_anchor_agent import get_character_anchor

try:
    from transformers import CLIPTokenizer  # type: ignore
except Exception:  # pragma: no cover
    CLIPTokenizer = None  # type: ignore


@dataclass
class SceneSpec:
    idx: int
    kind: str
    text: str
    prompt: str
    negative: str
    token_count: int


def _get_tokenizer() -> Any:
    if CLIPTokenizer is None:
        return None
    try:
        # SD1.5 uses OpenAI CLIP ViT-L/14 tokenizer
        return CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
    except Exception:
        return None


def build_scene_specs(cfg: Dict[str, Any], script_text: str, *, max_images: int) -> List[Dict[str, Any]]:
    images_cfg = cfg.get("images", {}) or {}
    style_base = images_cfg.get("base_style") or "cinematic photo, dramatic lighting, ultra detailed, sharp focus"
    negative_base = images_cfg.get("negative_prompt") or "lowres, blurry, bad anatomy, extra fingers, missing fingers, deformed, watermark, text, logo, hands, fingers"
    max_tokens = int(images_cfg.get("max_prompt_tokens", 70))

    global_profile = get_channel_visual_profile(cfg) or ""
    global_negative = get_channel_negative_profile(cfg) or ""
    ca = get_character_anchor(cfg) or {}
    character_anchor = (ca.get("anchor") or "").strip()
    character_reinforce = (ca.get("reinforce") or "").strip()

    agent = PromptVisualAgent(
        style_base=style_base,
        negative_base=negative_base,
        max_tokens=max_tokens,
        global_profile=global_profile,
        global_negative=global_negative,
    )
    tok = _get_tokenizer()

    seconds = int((cfg.get("video") or {}).get("seconds", 60))
    scenes = split_script_into_scenes(
        script_text,
        target_seconds=seconds,
        min_scenes=int(images_cfg.get("min_scenes", 4)),
        max_scenes=int(images_cfg.get("max_scenes", max_images)),
    )

    out: List[Dict[str, Any]] = []
    for s in scenes[:max_images]:
        idx = int(s.get("idx") or (len(out) + 1))
        text = str(s.get("text") or "").strip()
        kind = str(s.get("kind") or "auto")

        res = agent.build(
            text,
            tokenizer=tok,
            kind=kind,
            character_anchor=character_anchor,
            character_reinforce=character_reinforce,
        )
        token_count = int(res.token_count or 0)
        out.append(
            {
                "idx": idx,
                "kind": kind,
                "text": text,
                "prompt": res.prompt,
                "negative": res.negative_prompt,
                "token_count": token_count,
            }
        )
    return out


def try_llm_scene_plan(cfg: Dict[str, Any], script_text: str, *, max_scenes: int) -> Optional[List[Dict[str, Any]]]:
    """Tenta pedir ao LLM um plano de cenas limpo (texto curto por cena + tipo).

    Retorna apenas o plano textual (sem prompts). Prompts continuam sendo gerados pelo PromptVisualAgent.
    """
    from core.agents.llm_router import call_best

    prompt = f"""Você vai transformar um roteiro de short (PT-BR) em um plano de cenas para geração de imagens.

REGRAS:
- Gere entre 4 e {max_scenes} cenas.
- Cada cena deve ter:
  idx (1..N), kind (character|environment|detail|impact), text (<= 180 caracteres, PT-BR, sem aspas).
- Não invente fatos; apenas reorganize o texto.
- Evite detalhes explícitos. Linguagem YouTube-friendly.
- Saída DEVE ser JSON puro: uma lista de objetos.

ROTEIRO:
{script_text}
""".strip()

    res = call_best(prompt, cfg)
    if not res.text:
        return None
    try:
        data = json.loads(res.text)
        if isinstance(data, list) and data:
            cleaned = []
            for i, it in enumerate(data, 1):
                if not isinstance(it, dict):
                    continue
                idx = int(it.get("idx") or i)
                kind = str(it.get("kind") or "auto")
                text = str(it.get("text") or "").strip()
                if not text:
                    continue
                cleaned.append({"idx": idx, "kind": kind, "text": text})
            return cleaned or None
    except Exception:
        return None
    return None


def build_scene_specs_with_llm(cfg: Dict[str, Any], script_text: str, *, max_images: int) -> List[Dict[str, Any]]:
    plan = try_llm_scene_plan(cfg, script_text, max_scenes=max_images)
    if plan:
        # turn plan into prompts
        images_cfg = cfg.get("images", {}) or {}
        style_base = images_cfg.get("base_style") or "cinematic photo, dramatic lighting, ultra detailed, sharp focus"
        negative_base = images_cfg.get("negative_prompt") or "lowres, blurry, bad anatomy, extra fingers, missing fingers, deformed, watermark, text, logo, hands, fingers"
        max_tokens = int(images_cfg.get("max_prompt_tokens", 70))
        global_profile = get_channel_visual_profile(cfg) or ""
        global_negative = get_channel_negative_profile(cfg) or ""
        ca = get_character_anchor(cfg) or {}
        character_anchor = (ca.get("anchor") or "").strip()
        character_reinforce = (ca.get("reinforce") or "").strip()

        agent = PromptVisualAgent(
            style_base=style_base,
            negative_base=negative_base,
            max_tokens=max_tokens,
            global_profile=global_profile,
            global_negative=global_negative,
        )
        tok = _get_tokenizer()
        out: List[Dict[str, Any]] = []
        for s in plan[:max_images]:
            idx = int(s.get("idx") or (len(out) + 1))
            text = str(s.get("text") or "").strip()
            kind = str(s.get("kind") or "auto")
            res = agent.build(
                text,
                tokenizer=tok,
                kind=kind,
                character_anchor=character_anchor,
                character_reinforce=character_reinforce,
            )
            out.append(
                {
                    "idx": idx,
                    "kind": kind,
                    "text": text,
                    "prompt": res.prompt,
                    "negative": res.negative_prompt,
                    "token_count": int(res.token_count or 0),
                }
            )
        return out

    return build_scene_specs(cfg, script_text, max_images=max_images)

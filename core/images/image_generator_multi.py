# -*- coding: utf-8 -*-
import os
import random
from typing import Dict, List, Tuple

from core.agents.scene_splitter import split_script_into_scenes
from core.agents.image_scene_prompt import build_scene_prompt
from core.images.sdnext_client import txt2img_sdnext


def generate_images_from_script(
    cfg: Dict,
    script_text: str,
    out_dir: str,
    target_seconds: int = 60,
) -> Tuple[List[Dict], List[str]]:
    """Gera N imagens (3-7 por padrão) a partir do roteiro final."""
    images_cfg = cfg.get("images", {}) if isinstance(cfg, dict) else {}
    sd = images_cfg.get("sdnext", {}) if isinstance(images_cfg.get("sdnext", {}), dict) else {}

    base_url = sd.get("base_url") or images_cfg.get("sdnext_base_url") or "http://127.0.0.1:7860"
    model = sd.get("model") or images_cfg.get("sd_model") or None
    sampler = sd.get("sampler") or images_cfg.get("sampler") or "Euler a"
    steps = int(sd.get("steps") or images_cfg.get("steps") or 18)
    cfg_scale = float(sd.get("cfg_scale") or images_cfg.get("cfg_scale") or 6.5)
    width = int(sd.get("width") or images_cfg.get("width") or 576)
    height = int(sd.get("height") or images_cfg.get("height") or 1024)

    min_scenes = int(sd.get("min_scenes") or images_cfg.get("min_scenes") or 3)
    max_scenes = int(sd.get("max_scenes") or images_cfg.get("max_scenes") or 7)

    scenes = split_script_into_scenes(
        script_text,
        target_seconds=int(target_seconds),
        min_scenes=min_scenes,
        max_scenes=max_scenes,
    )

    os.makedirs(out_dir, exist_ok=True)
    image_paths: List[str] = []

    base_seed = sd.get("seed_base")
    if base_seed is None:
        base_seed = random.randint(100000, 900000)
    else:
        base_seed = int(base_seed)

    for sc in scenes:
        prompts = build_scene_prompt(sc["text"], channel_style=sd.get("style"))
        sc["prompt"] = prompts["prompt"]
        sc["negative_prompt"] = prompts["negative_prompt"]
        sc["seed"] = int(base_seed) + int(sc["idx"])
        out_path = os.path.join(out_dir, f"scene{sc['idx']}.png")
        sc["image_path"] = out_path

        try:
            txt2img_sdnext(
                base_url=base_url,
                prompt=sc["prompt"],
                negative_prompt=sc["negative_prompt"],
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                sampler_name=sampler,
                seed=sc["seed"],
                model=model,
                out_path=out_path,
            )
        except Exception as e:
            sc["error"] = str(e)

        image_paths.append(out_path)

    return scenes, image_paths

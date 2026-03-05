from __future__ import annotations

import os
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

from core.agents.image_prompt_agent import build_scene_prompts, to_json_list


def _ensure_dir(p: str | Path) -> Path:
    pp = Path(p)
    pp.mkdir(parents=True, exist_ok=True)
    return pp


def _load_sd15_pipe(cfg: Dict[str, Any]):
    # Lazy imports to avoid slowing healthcheck
    from diffusers import StableDiffusionPipeline, EulerAncestralDiscreteScheduler
    from diffusers import DDIMScheduler

    images_cfg = (cfg.get("images") or {})
    model_path = images_cfg.get("model_path")
    if not model_path:
        raise RuntimeError("images.model_path não definido no config.yml")

    dtype_cfg = str(images_cfg.get("dtype", "float32")).lower().strip()
    torch_dtype = torch.float32 if dtype_cfg in ("float32", "fp32") else torch.float16

    # NOTE: For GTX 1660 Ti we strongly prefer float32 stability.
    pipe = StableDiffusionPipeline.from_single_file(
        model_path,
        torch_dtype=torch_dtype,
        safety_checker=None,
        requires_safety_checker=False,
    )

    # Scheduler
    sched = str(images_cfg.get("scheduler", "euler_a")).lower().strip()
    if sched in ("ddim",):
        pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
    else:
        pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = pipe.to(device)
    try:
        pipe.set_progress_bar_config(disable=True)
    except Exception:
        pass

    # Memory knobs
    try:
        pipe.enable_attention_slicing()
    except Exception:
        pass

    return pipe


def generate_images_from_script(cfg: Dict[str, Any], script_path: str, out_dir: str, max_images: int = 5) -> List[str]:
    """Generate multiple images based on scene prompts.
    Writes scenes.json in the same folder as script_path (job dir) for traceability.
    """
    job_dir = Path(script_path).parent
    outp = _ensure_dir(out_dir)

    text = Path(script_path).read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        raise RuntimeError("script.txt vazio")

    # Build scene prompts (3-6), then clamp to max_images
    scenes = build_scene_prompts(text, max_scenes=max(3, max_images), cfg=cfg)
    scenes = scenes[:max_images]

    scenes_path = job_dir / "scenes.json"
    scenes_path.write_text(json.dumps(to_json_list(scenes), ensure_ascii=False, indent=2), encoding="utf-8")

    pipe = _load_sd15_pipe(cfg)

    images_cfg = (cfg.get("images") or {})
    steps = int(images_cfg.get("steps", 20))
    cfg_scale = float(images_cfg.get("cfg_scale", 6.5))
    w = int(images_cfg.get("width", 576))
    h = int(images_cfg.get("height", 1024))
    base_seed = int(images_cfg.get("seed", int(time.time()) % 100000))

    results: List[str] = []
    for i, sc in enumerate(scenes, start=1):
        seed = base_seed + i * 11
        gen = torch.Generator(device=pipe.device).manual_seed(seed)

        print(f"[IMG] {i}/{len(scenes)} kind={sc.kind} seed={seed} steps={steps} cfg={cfg_scale}")
        print(f"[IMG] prompt: {sc.prompt}")
        print(f"[IMG] negative: {sc.negative_prompt}")

        def _cb(step, timestep, latents):
            # callback do diffusers: step é 0-based
            try:
                s = int(step) + 1
            except Exception:
                s = step
            if s == 1 or s == steps or (isinstance(s, int) and s % 5 == 0):
                print(f"[IMG] ... step {s}/{steps}", flush=True)

        t0 = time.time()
        try:
            img = pipe(
                prompt=sp.prompt,
                negative_prompt=sp.negative,
                num_inference_steps=steps,
                guidance_scale=cfg_scale,
                generator=gen,
                callback=_cb,
                callback_steps=1,
            ).images[0]
        except TypeError:
            # compat com versões do diffusers que não suportam callback
            img = pipe(
                prompt=sp.prompt,
                negative_prompt=sp.negative,
                num_inference_steps=steps,
                guidance_scale=cfg_scale,
                generator=gen,
            ).images[0]
        dt = time.time() - t0

        out_file = outp / f"scene_{i:02d}.png"
        img.save(out_file)
        print(f"[IMG] saved {out_file} ({dt:.1f}s)")
        results.append(str(out_file))

    return results


def generate_scene1(cfg: Dict[str, Any], out_path: str) -> str:
    """Fallback single image."""
    # Keep it deterministic and safe
    tmp_script = Path(out_path).with_suffix(".tmp_script.txt")
    tmp_script.write_text("Cena investigativa cinematográfica, clima de mistério.", encoding="utf-8")
    imgs = generate_images_from_script(cfg, script_path=str(tmp_script), out_dir=str(Path(out_path).parent), max_images=1)
    # Rename to requested output
    if imgs:
        Path(imgs[0]).replace(out_path)
    try:
        tmp_script.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass
    return out_path

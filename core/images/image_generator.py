from __future__ import annotations

import gc
import json
from pathlib import Path
from typing import List, Optional, Tuple

import torch

from core.utils import ensure_dir

DEFAULT_BASE_STYLE = "cinematic photo, dramatic lighting, ultra detailed, sharp focus"
DEFAULT_NEGATIVE = "lowres, blurry, bad anatomy, extra fingers, missing fingers, deformed, watermark, text, logo, hands, fingers"


def _load_scene_specs_from_job(script_path: str, *, max_images: int) -> Optional[List[dict]]:
    """Se existir scenes.json ao lado do script, tenta usar.

    Formatos aceitos:
      - lista de {idx, text, prompt, negative, token_count}
      - lista de {idx, text} (sem prompt) -> ainda útil
    """
    sp = Path(script_path)
    sj = sp.parent / "scenes.json"
    if not sj.exists():
        return None
    try:
        data = json.loads(sj.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, list) and data:
            out = []
            for it in data[:max_images]:
                if isinstance(it, dict):
                    out.append(it)
            return out or None
    except Exception:
        return None
    return None

def _collect_images(out_dir: Path) -> List[str]:
    if not out_dir.exists():
        return []
    imgs = sorted([p for p in out_dir.glob("*.png")], key=lambda p: p.name)
    return [str(p) for p in imgs]


def _load_sd_pipe(model_path: str, device: str, *, torch_dtype=torch.float32):
    """Load Stable Diffusion pipeline from a local .safetensors (SD1.5) file."""
    from diffusers import StableDiffusionPipeline  # local import for faster CLI startup

    mp = Path(model_path)
    if not mp.exists():
        raise FileNotFoundError(f"Modelo SD não encontrado: {mp}")

    # diffusers supports loading from a single file checkpoint
    pipe = StableDiffusionPipeline.from_single_file(
        str(mp),
        torch_dtype=torch_dtype,
        safety_checker=None,  # keep deterministic + avoid extra deps
        requires_safety_checker=False,
    )

    # Stability/VRAM options
    pipe.set_progress_bar_config(disable=True)

    if device == "cuda":
        pipe = pipe.to("cuda")
    else:
        pipe = pipe.to("cpu")

    return pipe


def _maybe_gc_cuda():
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass
    gc.collect()


def generate_scene1(cfg: dict, out_path: str) -> str:
    """Fallback single image."""
    prompt = "close-up cinematic photo, mysterious investigator, moody lighting, film grain, noir, dramatic shadows"
    neg = (cfg.get("images") or {}).get("negative_prompt") or DEFAULT_NEGATIVE
    out_dir = Path(out_path).parent
    ensure_dir(str(out_dir))
    imgs = _generate_images_inprocess(
        cfg,
        prompts=[prompt],
        negative_prompt=neg,
        out_dir=out_dir,
        start_index=1,
    )
    # Ensure output filename
    if imgs:
        Path(imgs[0]).replace(out_path)
        return out_path
    raise RuntimeError("Falha ao gerar imagem fallback.")


def _read_script_text(script_path: str) -> str:
    p = Path(script_path)
    if not p.exists():
        raise FileNotFoundError(f"Script não encontrado: {p}")
    return p.read_text(encoding="utf-8", errors="ignore")


def _scene_texts_from_script(cfg: dict, script_text: str, *, max_images: int) -> List[str]:
    # Prefer scene splitter agent (deterministic)
    try:
        from core.agents.scene_splitter import split_script_into_scenes
        seconds = int((cfg.get("video") or {}).get("seconds", 60))
        scenes = split_script_into_scenes(script_text, target_seconds=seconds, min_scenes=3, max_scenes=max(3, max_images))
        texts = [s.get("text", "").strip() for s in scenes if (s.get("text") or "").strip()]
    except Exception:
        texts = []

    if not texts:
        # Fallback: split by sentences/lines
        parts = [t.strip() for t in script_text.replace("\r", "\n").split("\n") if t.strip()]
        texts = parts[:max_images] if parts else [script_text.strip()]

    return texts[:max_images]


def _build_prompts(cfg: dict, scene_texts: List[str]) -> Tuple[List[str], str]:
    images_cfg = cfg.get("images", {}) or {}
    style_base = images_cfg.get("base_style", DEFAULT_BASE_STYLE)
    negative = images_cfg.get("negative_prompt", DEFAULT_NEGATIVE)

    # Global/channel profile (optional)
    global_profile = ""
    global_negative = ""
    try:
        from core.agents.channel_style_manager import get_channel_visual_profile, get_channel_negative_profile
        global_profile = get_channel_visual_profile(cfg) or ""
        global_negative = get_channel_negative_profile(cfg) or ""
    except Exception:
        pass

    # Character anchor (optional)
    character_anchor = ""
    character_reinforce = ""
    try:
        from core.agents.character_anchor_agent import get_character_anchor
        ca = get_character_anchor(cfg) or {}
        character_anchor = (ca.get("anchor") or "").strip()
        character_reinforce = (ca.get("reinforce") or "").strip()
    except Exception:
        pass

    # Prompt agent with token safety
    try:
        from core.agents.prompt_visual_agent import PromptVisualAgent
        agent = PromptVisualAgent(
            style_base=style_base,
            negative_base=negative,
            max_tokens=int(images_cfg.get("max_prompt_tokens", 70)),
            global_profile=global_profile,
            global_negative=global_negative,
        )
        prompts = []
        for i, st in enumerate(scene_texts, 1):
            kind = "auto"
            res = agent.build(
                st,
                kind=kind,
                character_anchor=character_anchor,
                character_reinforce=character_reinforce,
            )
            prompts.append(res.prompt)
        # merge negatives (agent already merges)
        neg = agent.build("x").negative_prompt
        return prompts, neg
    except Exception:
        prompts = [f"{style_base}, {t}".strip() for t in scene_texts]
        neg = ", ".join([negative, global_negative]).strip(", ")
        return prompts, neg


def _generate_images_inprocess(
    cfg: dict,
    *,
    prompts: List[str],
    negative_prompt: str,
    out_dir: Path,
    start_index: int = 1,
) -> List[str]:
    images_cfg = cfg.get("images", {}) or {}
    project_root = Path(cfg.get("project_root") or Path(__file__).resolve().parents[2])
    model_path = images_cfg.get("model_path") or str(project_root / "models" / "dreamshaper_8.safetensors")

    width = int(images_cfg.get("width", 576))
    height = int(images_cfg.get("height", 1024))
    steps = int(images_cfg.get("steps", 22))
    guidance = float(images_cfg.get("cfg_scale", 6.5))
    seed = images_cfg.get("seed", None)
    if seed is not None:
        try:
            seed = int(seed)
        except Exception:
            seed = None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float32  # stable for GTX 1660 Ti (no black images)
    pipe = _load_sd_pipe(model_path, device=device, torch_dtype=torch_dtype)

    # Optional performance knobs
    try:
        if bool(images_cfg.get("attention_slicing", True)):
            pipe.enable_attention_slicing()
    except Exception:
        pass
    try:
        if bool(images_cfg.get("vae_slicing", True)):
            pipe.enable_vae_slicing()
    except Exception:
        pass

    results: List[str] = []
    ensure_dir(str(out_dir))

    for idx, prompt in enumerate(prompts, start_index):
        gen = None
        if seed is not None:
            gen = torch.Generator(device=device).manual_seed(seed + idx)

        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=gen,
        ).images[0]

        out_path = out_dir / f"scene_{idx:02d}.png"
        image.save(out_path)
        results.append(str(out_path))

        # Try to keep VRAM stable between scenes
        _maybe_gc_cuda()

    # Cleanup
    try:
        pipe.to("cpu")
    except Exception:
        pass
    del pipe
    _maybe_gc_cuda()
    return results


def generate_images_from_script(cfg: dict, script_path: str, out_dir: str, max_images: int) -> List[str]:
    """Generate multiple images for the job, fully in-process (no subprocess).

    Prioridade:
      1) scenes.json ao lado do script (se tiver prompts prontos)
      2) SceneSpecAgent (tenta plano via LLM e gera prompts truncados com CLIP)
      3) fallback: split determinístico + PromptVisualAgent
    """
    out_dir_p = Path(out_dir)
    ensure_dir(str(out_dir_p))

    script_text = _read_script_text(script_path)

    # 1) scenes.json precomputado no job
    specs = _load_scene_specs_from_job(script_path, max_images=max_images)
    if specs:
        # se já tiver prompt, usa; senão gera prompts a partir de text
        prompts: List[str] = []
        neg = (cfg.get("images") or {}).get("negative_prompt") or DEFAULT_NEGATIVE
        # se houver negativos por cena, usa o primeiro; senão usa neg global
        for it in specs:
            p = (it.get("prompt") or "").strip()
            t = (it.get("text") or "").strip()
            if p:
                prompts.append(p)
                if (it.get("negative") or "").strip():
                    neg = str(it.get("negative")).strip()
            elif t:
                prompts.append(t)
        if prompts:
            # se não tinha prompt de verdade, _build_prompts vai completar
            if any(not (it.get("prompt") or "").strip() for it in specs):
                prompts, neg = _build_prompts(cfg, [s.get("text","") for s in specs if (s.get("text") or "").strip()])
            return _generate_images_inprocess(cfg, prompts=prompts, negative_prompt=neg, out_dir=out_dir_p, start_index=1)

    # 2) SceneSpec agent (gera prompts já truncados por CLIP)
    try:
        from core.agents.scene_spec_agent import build_scene_specs_with_llm
        scene_specs = build_scene_specs_with_llm(cfg, script_text, max_images=max_images)
        prompts = [s.get("prompt","").strip() for s in scene_specs if (s.get("prompt") or "").strip()]
        neg = (scene_specs[0].get("negative") if scene_specs else None) or (cfg.get("images") or {}).get("negative_prompt") or DEFAULT_NEGATIVE
        if prompts:
            return _generate_images_inprocess(cfg, prompts=prompts, negative_prompt=str(neg), out_dir=out_dir_p, start_index=1)
    except Exception:
        pass

    # 3) fallback legacy
    scene_texts = _scene_texts_from_script(cfg, script_text, max_images=max_images)
    prompts, neg = _build_prompts(cfg, scene_texts)
    return _generate_images_inprocess(cfg, prompts=prompts, negative_prompt=neg, out_dir=out_dir_p, start_index=1)

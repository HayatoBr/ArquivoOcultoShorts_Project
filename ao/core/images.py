from __future__ import annotations

import gc
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
from PIL import Image, ImageDraw

try:
    from safetensors.torch import load_file
except Exception:
    load_file = None

from ao.core.style import build_scene_prompt_v9, get_negative_prompt

try:
    from diffusers import (
        AutoPipelineForText2Image,
        StableDiffusionPipeline,
        StableDiffusionXLPipeline,
        DPMSolverMultistepScheduler,
        EulerDiscreteScheduler,
        UniPCMultistepScheduler,
    )
except Exception:
    AutoPipelineForText2Image = None
    StableDiffusionPipeline = None
    StableDiffusionXLPipeline = None
    DPMSolverMultistepScheduler = None
    EulerDiscreteScheduler = None
    UniPCMultistepScheduler = None

_PIPE_CACHE: dict[tuple, Any] = {}


def _runtime_summary(device: str, dtype: torch.dtype, backend: str, model_path: str, loader: str) -> Dict[str, Any]:
    return {
        "device": device,
        "dtype": str(dtype).replace("torch.", ""),
        "backend": backend,
        "model_path": model_path,
        "loader": loader,
        "cuda_available": torch.cuda.is_available(),
    }


def load_lightning_unet(pipe, unet_path, logger=None):
    if not os.path.exists(unet_path):
        if logger:
            logger.warning("[IMG] lightning UNet não encontrado")
        return pipe, False
    if load_file is None:
        if logger:
            logger.warning("[IMG] safetensors não disponível para carregar lightning UNet")
        return pipe, False
    try:
        state = load_file(unet_path)
        if all(k.startswith("unet.") for k in state.keys()):
            state = {k.replace("unet.", "", 1): v for k, v in state.items()}
        missing, unexpected = pipe.unet.load_state_dict(state, strict=False)
        if logger:
            logger.info("[IMG] lightning UNet loaded | missing=%s unexpected=%s", len(missing), len(unexpected))
        return pipe, True
    except Exception as e:
        if logger:
            logger.warning("[IMG] Falha ao carregar UNet lightning (%s)", e)
        return pipe, False


def _choose_device_dtype(images_cfg: Dict[str, Any], logger) -> tuple[str, torch.dtype]:
    use_cuda_cfg = bool(images_cfg.get("use_cuda", True))
    cuda_runtime_ok = torch.cuda.is_available()
    logger.info("[IMG] use_cuda_cfg=%s | cuda_runtime_ok=%s", use_cuda_cfg, cuda_runtime_ok)
    if use_cuda_cfg and cuda_runtime_ok:
        precision = str(images_cfg.get("precision", "fp32")).lower()
        if precision in {"fp16", "float16", "half"}:
            return "cuda", torch.float16
        return "cuda", torch.float32
    return "cpu", torch.float32


def _make_scheduler(pipe, name: str, logger):
    name = (name or "").strip().lower()
    if name == "dpmpp_2m_karras" and DPMSolverMultistepScheduler is not None:
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
        logger.info("[IMG] scheduler=DPMSolverMultistepScheduler(Karras)")
    elif name == "unipc" and UniPCMultistepScheduler is not None:
        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
        logger.info("[IMG] scheduler=UniPCMultistepScheduler")
    elif EulerDiscreteScheduler is not None:
        pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
        logger.info("[IMG] scheduler=EulerDiscreteScheduler")
    return pipe


def _build_pipe(model_path: str, dtype: torch.dtype, backend: str):
    loaders = []
    if backend.startswith("sdxl") and StableDiffusionXLPipeline is not None and hasattr(StableDiffusionXLPipeline, "from_single_file"):
        loaders.append(("StableDiffusionXLPipeline.from_single_file", lambda: StableDiffusionXLPipeline.from_single_file(model_path, torch_dtype=dtype, use_safetensors=True)))
    if AutoPipelineForText2Image is not None and hasattr(AutoPipelineForText2Image, "from_single_file"):
        loaders.append(("AutoPipelineForText2Image.from_single_file", lambda: AutoPipelineForText2Image.from_single_file(model_path, torch_dtype=dtype, use_safetensors=True)))
    if backend.startswith("sd") and StableDiffusionPipeline is not None and hasattr(StableDiffusionPipeline, "from_single_file"):
        loaders.append(("StableDiffusionPipeline.from_single_file", lambda: StableDiffusionPipeline.from_single_file(model_path, torch_dtype=dtype, use_safetensors=True)))

    errors = []
    for name, fn in loaders:
        try:
            return fn(), name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(" | ".join(errors) if errors else "Nenhum loader compatível do diffusers está disponível")


def _load_pipeline(cfg: Dict[str, Any], logger):
    images_cfg = cfg.get("images", {}) or {}
    backend = str(images_cfg.get("backend", "sdxl_lightning"))
    model_path = str(images_cfg.get("model_path") or images_cfg.get("sd_model") or "")
    if not model_path:
        raise RuntimeError("Modelo de imagem não definido no config")

    cache_key = (backend, model_path, str(images_cfg.get("lightning_unet_path") or ""), str(images_cfg.get("precision", "fp32")))
    if cache_key in _PIPE_CACHE:
        logger.info("[IMG] cache=hit | reutilizando pipeline visual")
        return _PIPE_CACHE[cache_key]

    logger.info("[IMG] cache=miss | carregando pipeline visual")
    device, dtype = _choose_device_dtype(images_cfg, logger)
    logger.info("[IMG] backend=%s | model=%s", backend, model_path)
    logger.info("[IMG] device=%s | dtype=%s", device, str(dtype).replace("torch.", ""))
    if device == "cuda":
        logger.info("[IMG] GPU detectada: %s", torch.cuda.get_device_name(0))

    pipe, loader_name = _build_pipe(model_path, dtype, backend)
    logger.info("[IMG] loader=%s", loader_name)
    pipe = _make_scheduler(pipe, str(images_cfg.get("scheduler", "dpmpp_2m_karras")), logger)

    if backend == "sdxl_lightning":
        lightning_path = str(images_cfg.get("lightning_unet_path") or "")
        if lightning_path and hasattr(pipe, "unet"):
            logger.info("[IMG] SDXL lightning UNet=%s", lightning_path)
            pipe, loaded = load_lightning_unet(pipe, lightning_path, logger)
            if not loaded:
                logger.warning("[IMG] Lightning não aplicado; seguindo com base pura.")

    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()
        logger.info("[IMG] attention_slicing=enabled")
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()
        logger.info("[IMG] vae.enable_slicing=enabled")
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
        logger.info("[IMG] vae.enable_tiling=enabled")
    if hasattr(pipe, "unet"):
        pipe.unet.to(memory_format=torch.channels_last)
        logger.info("[IMG] unet memory_format=channels_last")

    if device == "cuda":
        try:
            total_mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except Exception:
            total_mem_gb = 0
        if total_mem_gb and total_mem_gb <= 6.5 and hasattr(pipe, "enable_sequential_cpu_offload"):
            pipe.enable_sequential_cpu_offload()
            logger.info("[IMG] sequential_cpu_offload=enabled")
        else:
            pipe = pipe.to(device)
    else:
        pipe = pipe.to(device)
    _PIPE_CACHE[cache_key] = (pipe, _runtime_summary(device, dtype, backend, model_path, loader_name))
    return _PIPE_CACHE[cache_key]


def _seed_for_scene(global_seed: int, scene: Dict[str, Any], idx: int) -> int:
    raw = f"{global_seed}|{idx}|{scene.get('seed_group', '')}|{scene.get('prompt_en', '')}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


def _fallback_placeholder(path: Path, scene: Dict[str, Any], width: int, height: int):
    img = Image.new("RGB", (width, height), color=(18, 18, 18))
    draw = ImageDraw.Draw(img)
    draw.multiline_text((20, 20), (scene.get("prompt_en") or scene.get("subject") or "scene")[:240], fill=(230, 230, 230), spacing=6)
    img.save(path)


def _looks_black(path: Path) -> bool:
    try:
        img = Image.open(path).convert("RGB")
        extrema = img.getextrema()
        return all(lo == hi == 0 for lo, hi in extrema)
    except Exception:
        return False


def generate_images(cfg: Dict[str, Any], scene_prompts: List[Dict[str, Any]], images_dir: Path, logger) -> Tuple[List[str], Dict[str, Any]]:
    images_cfg = cfg.get("images", {}) or {}
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    width = int(images_cfg.get("width", 512))
    height = int(images_cfg.get("height", 896))
    if torch.cuda.is_available():
        try:
            total_mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except Exception:
            total_mem_gb = 0
        if total_mem_gb and total_mem_gb <= 6.5 and (width * height) > 800000:
            ratio = (800000 / float(width * height)) ** 0.5
            width = max(512, int(width * ratio) // 64 * 64)
            height = max(896, int(height * ratio) // 64 * 64)
            logger.info("[IMG] resolução ajustada para %sx%s por limite de VRAM", width, height)
    steps = int(images_cfg.get("steps", 4))
    guidance_scale = float(images_cfg.get("guidance_scale") or images_cfg.get("cfg_scale") or 1.6)
    negative_prompt = get_negative_prompt(cfg)
    global_seed = int((cfg.get("runtime", {}) or {}).get("seed", 42))

    try:
        pipe, runtime = _load_pipeline(cfg, logger)
    except Exception as exc:
        logger.warning("[IMG] Falha ao carregar pipeline visual (%s). Gerando placeholders.", exc)
        runtime = {"fallback": True, "reason": str(exc)}
        paths = []
        for idx, scene in enumerate(scene_prompts, start=1):
            scene = dict(scene)
            scene["prompt_en"] = scene.get("prompt_en") or build_scene_prompt_v9(scene, cfg=cfg, topic=scene.get("topic", ""))
            out_path = images_dir / f"scene_{idx:02d}.png"
            _fallback_placeholder(out_path, scene, width, height)
            paths.append(str(out_path))
        return paths, runtime

    paths: List[str] = []
    for idx, scene in enumerate(scene_prompts, start=1):
        if runtime.get("device") == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            gc.collect()
        scene = dict(scene)
        prompt_en = scene.get("prompt_en") or build_scene_prompt_v9(scene, cfg=cfg, topic=scene.get("topic", ""))
        seed = _seed_for_scene(global_seed, scene, idx)
        generator = torch.Generator(device=runtime["device"]).manual_seed(seed)
        logger.info("[IMG] Gerando imagem %s/%s", idx, len(scene_prompts))
        logger.info("[IMG] label=%s | seed=%s | seed_group=%s | motion=%s | prompt_tokens=%s", scene.get("scene_type", "detail"), seed, scene.get("seed_group", "topic_anchor"), scene.get("motion", "slow_push"), len(prompt_en.split(",")))
        logger.info("[IMG] prompt_en=%s", prompt_en)
        out_path = images_dir / f"scene_{idx:02d}.png"
        try:
            result = pipe(
                prompt=prompt_en,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )
            result.images[0].save(out_path)
            if _looks_black(out_path):
                raise RuntimeError("imagem preta detectada após geração")
        except Exception as exc:
            logger.warning("[IMG] Falha na geração da cena %s (%s). Criando placeholder.", idx, exc)
            _fallback_placeholder(out_path, scene, width, height)
        paths.append(str(out_path))
        if runtime.get("device") == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            gc.collect()
    return paths, runtime

# -*- coding: utf-8 -*-
import base64
import os
from typing import Any, Dict, Optional

import requests


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 600) -> Dict[str, Any]:
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def list_samplers(base_url: str) -> list:
    r = requests.get(f"{base_url}/sdapi/v1/samplers", timeout=60)
    r.raise_for_status()
    return r.json()


def txt2img_sdnext(
    base_url: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 576,
    height: int = 1024,
    steps: int = 18,
    cfg_scale: float = 6.5,
    sampler_name: str = "Euler a",
    seed: int = -1,
    model: Optional[str] = None,
    out_path: str = "output.png",
) -> str:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
        "sampler_name": sampler_name,
        "seed": int(seed),
        "restore_faces": False,
        "enable_hr": False,
    }

    if model:
        payload["override_settings"] = {"sd_model_checkpoint": model}
        payload["override_settings_restore_afterwards"] = True

    j = _post_json(f"{base_url}/sdapi/v1/txt2img", payload, timeout=900)
    imgs = j.get("images") or []
    if not imgs:
        raise RuntimeError("Nenhuma imagem retornada pela API (images vazio).")
    img_b64 = imgs[0]
    raw = base64.b64decode(img_b64.split(",", 1)[-1])

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(raw)
    return out_path

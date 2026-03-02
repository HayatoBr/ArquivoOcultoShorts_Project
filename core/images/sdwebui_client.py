from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


class SDWebUIError(RuntimeError):
    pass


@dataclass
class SDModel:
    title: str
    model_name: str | None = None
    hash: str | None = None
    filename: str | None = None
    sha256: str | None = None


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _req(method: str, base_url: str, path: str, payload: Optional[dict] = None, timeout: int = 120) -> Any:
    url = _url(base_url, path)
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=_headers(), timeout=timeout)
        else:
            r = requests.request(method.upper(), url, headers=_headers(),
                                 data=json.dumps(payload or {}), timeout=timeout)
        r.raise_for_status()
        if r.text.strip() == "":
            return None
        return r.json()
    except requests.RequestException as e:
        msg = getattr(e.response, "text", "") if hasattr(e, "response") else ""
        raise SDWebUIError(f"Falha chamando SD API {method} {url}: {e}\n{msg}") from e


def get_options(base_url: str) -> Dict[str, Any]:
    return _req("GET", base_url, "/sdapi/v1/options")


def set_options(base_url: str, options: Dict[str, Any]) -> None:
    _req("POST", base_url, "/sdapi/v1/options", options)


def list_models(base_url: str) -> List[SDModel]:
    data = _req("GET", base_url, "/sdapi/v1/sd-models") or []
    out: List[SDModel] = []
    for m in data:
        out.append(SDModel(
            title=m.get("title", ""),
            model_name=m.get("model_name"),
            hash=m.get("hash"),
            filename=m.get("filename"),
            sha256=m.get("sha256"),
        ))
    return out


def list_samplers(base_url: str) -> List[str]:
    data = _req("GET", base_url, "/sdapi/v1/samplers") or []
    names: List[str] = []
    for s in data:
        n = s.get("name")
        if n:
            names.append(n)
    return names


def _pick_sampler(available: List[str], preferred: str) -> str:
    if not available:
        return preferred
    for n in available:
        if n.lower() == preferred.lower():
            return n
    for cand in ["Euler a", "Euler", "DPM++ 2M", "DPM++ 2M Karras", "UniPC"]:
        for n in available:
            if n.lower() == cand.lower():
                return n
    return available[0]


def _normalize_checkpoint_name(checkpoint: str) -> str:
    return checkpoint.strip()


def ensure_checkpoint_loaded(
    base_url: str,
    preferred_checkpoint: Optional[str] = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 30.0,
) -> Tuple[str, List[SDModel]]:
    # Tries to ensure a checkpoint is selected.
    models = list_models(base_url)
    opts = get_options(base_url)
    cur = str(opts.get("sd_model_checkpoint", "") or "")
    cur_norm = _normalize_checkpoint_name(cur)

    target: Optional[str] = None
    if preferred_checkpoint:
        target = preferred_checkpoint
    elif len(models) == 1 and models[0].title:
        target = models[0].title

    if target:
        try:
            set_options(base_url, {"sd_model_checkpoint": target})
        except SDWebUIError:
            # some servers reject set_options; ignore and rely on override_settings
            pass

        deadline = time.time() + max_wait_seconds
        while time.time() < deadline:
            try:
                cur2 = str(get_options(base_url).get("sd_model_checkpoint", "") or "")
            except SDWebUIError:
                break
            if cur2 and target.lower() in cur2.lower():
                cur_norm = _normalize_checkpoint_name(cur2)
                break
            time.sleep(poll_seconds)

    return cur_norm, models


def txt2img(
    base_url: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int = 20,
    sampler: str = "Euler a",
    cfg_scale: float = 7.0,
    seed: int = -1,
    batch_size: int = 1,
    checkpoint_override: Optional[str] = None,
    timeout: int = 600,
) -> List[bytes]:
    # Returns list of PNG bytes. Works for SD.Next and A1111.
    try:
        samplers = list_samplers(base_url)
    except SDWebUIError:
        samplers = []
    sampler_use = _pick_sampler(samplers, sampler)

    payload: Dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "sampler_name": sampler_use,
        "cfg_scale": float(cfg_scale),
        "seed": int(seed),
        "batch_size": int(batch_size),
        "n_iter": 1,
        "restore_faces": False,
    }
    if checkpoint_override:
        payload["override_settings"] = {"sd_model_checkpoint": checkpoint_override}
        payload["override_settings_restore_afterwards"] = True

    data = _req("POST", base_url, "/sdapi/v1/txt2img", payload, timeout=timeout) or {}
    images_b64 = data.get("images") or []
    out: List[bytes] = []
    for b64 in images_b64:
        if not isinstance(b64, str) or b64.strip() == "":
            continue
        if "," in b64 and b64.strip().lower().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        out.append(base64.b64decode(b64))
    return out

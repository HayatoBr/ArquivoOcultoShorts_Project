from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class CheckItem:
    name: str
    ok: bool
    severity: str  # "error" | "warn" | "info"
    detail: str = ""


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _get_free_disk_gb(path: Path) -> float:
    try:
        usage = shutil.disk_usage(str(path))
        return usage.free / (1024**3)
    except Exception:
        return -1.0


def _try_import(modname: str) -> bool:
    try:
        __import__(modname)
        return True
    except Exception:
        return False


def _cuda_info() -> Tuple[bool, Dict[str, Any]]:
    info: Dict[str, Any] = {}
    try:
        import torch  # type: ignore
        info["torch_version"] = getattr(torch, "__version__", "")
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["device_name"] = torch.cuda.get_device_name(0)
            info["device_capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
            try:
                free, total = torch.cuda.mem_get_info()
                info["vram_free_mb"] = int(free / (1024**2))
                info["vram_total_mb"] = int(total / (1024**2))
            except Exception:
                pass
        return True, info
    except Exception as e:
        info["error"] = str(e)
        return False, info


def run_healthcheck(cfg: Dict[str, Any]) -> Dict[str, Any]:
    hc_cfg = (cfg.get("healthcheck") or {})
    enabled = bool(hc_cfg.get("enabled", True))
    if not enabled:
        return {"enabled": False, "items": [], "ok": True}

    items: List[CheckItem] = []

    items.append(CheckItem(
        name="system.os",
        ok=True,
        severity="info",
        detail=f"{platform.system()} {platform.release()} ({platform.version()})"
    ))
    items.append(CheckItem(
        name="system.python",
        ok=True,
        severity="info",
        detail=platform.python_version()
    ))

    out_root = Path((cfg.get("paths") or {}).get("output_dir", "output"))
    try:
        out_root.mkdir(parents=True, exist_ok=True)
        test = out_root / ".write_test.tmp"
        test.write_text("ok", encoding="utf-8")
        try:
            test.unlink()
        except Exception:
            pass
        items.append(CheckItem("paths.output_writable", True, "info", str(out_root.resolve())))
    except Exception as e:
        items.append(CheckItem("paths.output_writable", False, "error", f"{out_root}: {e}"))

    min_free_gb = float(hc_cfg.get("min_free_disk_gb", 3.0))
    free_gb = _get_free_disk_gb(out_root)
    if free_gb >= 0 and free_gb < min_free_gb:
        items.append(CheckItem("disk.free_space", False, "warn", f"{free_gb:.2f} GB livres (mínimo recomendado {min_free_gb} GB)"))
    else:
        items.append(CheckItem("disk.free_space", True, "info", f"{free_gb:.2f} GB livres"))

    ffmpeg_path = (hc_cfg.get("ffmpeg_path") or "").strip()
    ffmpeg_cmd = ffmpeg_path if ffmpeg_path else "ffmpeg"
    found = _which(ffmpeg_cmd) if not Path(ffmpeg_cmd).exists() else str(Path(ffmpeg_cmd))
    if found:
        items.append(CheckItem("deps.ffmpeg", True, "info", found))
    else:
        items.append(CheckItem("deps.ffmpeg", False, "error", "ffmpeg não encontrado no PATH (ou ffmpeg_path)."))

    piper_path = (hc_cfg.get("piper_path") or (cfg.get("tts") or {}).get("piper_path") or "").strip()
    if piper_path:
        ok = Path(piper_path).exists()
        items.append(CheckItem("deps.piper_path", ok, "error" if not ok else "info", piper_path))
    else:
        items.append(CheckItem("deps.piper_path", False, "warn", "piper_path não configurado (tts.piper_path ou healthcheck.piper_path)."))

    whisper_ok = _try_import("whisper") or _try_import("faster_whisper")
    items.append(CheckItem("deps.whisper", whisper_ok, "warn" if not whisper_ok else "info",
                           "OK" if whisper_ok else "Instale whisper ou faster-whisper conforme requirements."))

    diff_ok = _try_import("diffusers") and _try_import("transformers")
    items.append(CheckItem("deps.diffusers_transformers", diff_ok, "error" if not diff_ok else "info",
                           "OK" if diff_ok else "diffusers/transformers não estão importáveis."))

    img_cfg = (cfg.get("images") or {})
    model_path = (img_cfg.get("model_path") or img_cfg.get("model") or "").strip()
    if model_path:
        mp = Path(model_path)
        ok = mp.exists()
        items.append(CheckItem("images.model_path", ok, "error" if not ok else "info", model_path))
    else:
        items.append(CheckItem("images.model_path", False, "warn", "config.images.model_path não definido."))

    torch_ok, cuda = _cuda_info()
    if not torch_ok:
        items.append(CheckItem("gpu.torch", False, "warn", f"torch não importável: {cuda.get('error','')}"))
    else:
        items.append(CheckItem("gpu.cuda_available", bool(cuda.get("cuda_available")), "warn" if not cuda.get("cuda_available") else "info",
                               json.dumps(cuda, ensure_ascii=False)))
        min_vram_mb = int(hc_cfg.get("min_vram_free_mb", 800))
        vfree = int(cuda.get("vram_free_mb", -1))
        if vfree >= 0 and vfree < min_vram_mb:
            items.append(CheckItem("gpu.vram_free", False, "warn",
                                   f"{vfree} MB livres (mínimo recomendado {min_vram_mb} MB). Feche apps/limpe VRAM."))
        elif vfree >= 0:
            items.append(CheckItem("gpu.vram_free", True, "info", f"{vfree} MB livres"))

    overall_ok = True
    for it in items:
        if it.severity == "error" and not it.ok:
            overall_ok = False
            break

    return {
        "enabled": True,
        "ok": overall_ok,
        "items": [asdict(i) for i in items],
    }

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Any

from core.path_utils import resolve_exe


def _resolve_model(cfg: Dict[str, Any]) -> str:
    # Accept multiple legacy/new keys to avoid config mismatch
    tts_cfg = (cfg.get("tts") or {})
    paths_cfg = (cfg.get("paths") or {})

    candidates = [
        tts_cfg.get("model_path"),
        tts_cfg.get("piper_model"),
        tts_cfg.get("voice_model"),
        paths_cfg.get("piper_model"),
        paths_cfg.get("piper_model_path"),
        cfg.get("piper_model"),
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return ""


def synthesize_piper(cfg: Dict[str, Any], text: str, out_wav: str):
    # Executable comes from paths.piper_exe (via resolve_exe)
    piper = resolve_exe(cfg, "piper_exe")

    model = _resolve_model(cfg)
    if not model:
        raise RuntimeError("Modelo Piper não configurado (use tts.model_path ou paths.piper_model).")

    if not Path(model).exists():
        raise RuntimeError(f"Modelo Piper não encontrado: {model}")

    out_path = Path(out_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Piper expects UTF-8 input
    cmd = [
        str(piper),
        "--model", str(model),
        "--output_file", str(out_path),
    ]

    # Windows: send text via stdin
    proc = subprocess.run(
        cmd,
        input=(text or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    if proc.returncode != 0:
        out = proc.stdout.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Piper falhou (code {proc.returncode}). Saída:\n{out}")

    if not out_path.exists() or out_path.stat().st_size < 1024:
        raise RuntimeError("Piper não gerou WAV válido (arquivo ausente ou muito pequeno).")

    return str(out_path)

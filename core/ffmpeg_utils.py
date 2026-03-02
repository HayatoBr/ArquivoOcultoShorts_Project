from __future__ import annotations

import subprocess
from typing import List, Optional, Union

from core.path_utils import resolve_exe


def ffmpeg_path(cfg: dict) -> str:
    """
    Resolve ffmpeg executable path.
    Compatible keys:
      - config.paths.ffmpeg (preferred by this project)
      - config.paths.ffmpeg_exe (legacy/alternative)
    """
    paths = (cfg.get("paths") or {})
    if isinstance(paths.get("ffmpeg"), str) and paths.get("ffmpeg"):
        return resolve_exe(cfg, "ffmpeg", "ffmpeg")
    if isinstance(paths.get("ffmpeg_exe"), str) and paths.get("ffmpeg_exe"):
        cfg2 = dict(cfg)
        cfg2["paths"] = dict(paths)
        cfg2["paths"]["ffmpeg"] = paths["ffmpeg_exe"]
        return resolve_exe(cfg2, "ffmpeg", "ffmpeg")
    return resolve_exe(cfg, "ffmpeg", "ffmpeg")


def run_cmd(cmd: Union[List[str], str], cwd: Optional[str] = None, check: bool = True) -> str:
    """
    Run a command and return combined stdout/stderr text.
    Used by audio/video ffmpeg helpers.
    """
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    out = proc.stdout or ""
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (code {proc.returncode}). Output:\n{out}")
    return out

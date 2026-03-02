from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .subs_whisper import transcribe_whisper as _whisper_cli


def transcribe_whisper(cfg: dict, audio_path: str, out: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Compatibility wrapper.

    Supports:
      - transcribe_whisper(cfg, audio_path, out_srt_path)
      - transcribe_whisper(cfg, audio_path, job_dir)  -> writes job_dir/subs.srt
    Returns dict with metadata and out_srt path.
    """
    out_path = Path(out)
    if out_path.is_dir() or str(out_path).endswith(os.sep) or (not str(out_path).lower().endswith(".srt") and not out_path.suffix):
        out_srt = out_path / "subs.srt"
    else:
        out_srt = out_path

    return _whisper_cli(cfg, audio_path, str(out_srt))

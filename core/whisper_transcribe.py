from pathlib import Path
from core.subs_whisper import transcribe_whisper as _whisper_cli
from core.subs_simple_srt import make_srt_from_text
from core.path_utils import resolve_exe

def transcribe_whisper(cfg: dict, audio_path: str, out_srt: str, fallback_text: str | None = None) -> str:
    """Transcribe using Whisper CLI; if not configured, fallback to a naive SRT."""
    try:
        # will raise if not configured
        resolve_exe(cfg, "whisper_exe", fallback_name=None)
        return _whisper_cli(cfg, audio_path, out_srt)
    except Exception:
        # fallback: simple SRT from text
        total_seconds = float((cfg.get("video") or {}).get("seconds", 60))
        return make_srt_from_text(fallback_text or "", out_srt, total_seconds=total_seconds)

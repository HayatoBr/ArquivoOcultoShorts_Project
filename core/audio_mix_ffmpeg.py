from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, Union

from .ffmpeg_utils import ffmpeg_path, run_cmd


def _cfg_audio(cfg: Dict[str, Any]) -> Dict[str, Any]:
    a = cfg.get("audio") or {}
    return a if isinstance(a, dict) else {}


def _extract_music_path(music: Any) -> Optional[str]:
    """Accept str | PathLike | dict and return a usable file path."""
    if music is None:
        return None
    if isinstance(music, (str, bytes)):
        s = music.decode() if isinstance(music, bytes) else music
        return s.strip() if s.strip() else None
    if isinstance(music, Path):
        return str(music)
    if isinstance(music, dict):
        # common keys
        for k in ("path", "file", "music_path", "selected", "value", "audio_path"):
            v = music.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # sometimes nested { "music": {"path": ...} }
        for v in music.values():
            if isinstance(v, dict):
                p = _extract_music_path(v)
                if p:
                    return p
        return None
    return None


def mix_audio(cfg: Dict[str, Any], narration_wav: str, music_path: Any, out_wav: str) -> str:
    """
    Mix narration + optional music into a single WAV using ffmpeg.
    Robust: does NOT require cfg['audio'] keys to exist.
    Accepts music_path as str or dict (from selector).
    """
    narration = Path(narration_wav)
    if not narration.exists():
        raise FileNotFoundError(f"Narração não encontrada: {narration}")

    outp = Path(out_wav)
    outp.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = ffmpeg_path(cfg)
    a = _cfg_audio(cfg)

    voice_gain_db = float(a.get("voice_gain_db", 0.0))
    music_gain_db = float(a.get("music_gain_db", -14.0))
    ducking = bool(a.get("ducking", True))

    mpath = _extract_music_path(music_path)
    if not mpath or not Path(mpath).exists():
        cmd = [
            ffmpeg, "-y",
            "-i", str(narration),
            "-filter:a", f"volume={voice_gain_db}dB",
            "-ac", "2",
            "-ar", "44100",
            str(outp),
        ]
        run_cmd(cmd, check=True)
        return str(outp)

    music = Path(mpath)

    if ducking:
        flt = (
            f"[0:a]volume={voice_gain_db}dB[a0];"
            f"[1:a]volume={music_gain_db}dB[a1];"
            f"[a1][a0]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=250[a1duck];"
            f"[a0][a1duck]amix=inputs=2:duration=longest:dropout_transition=2,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11"
        )
    else:
        flt = (
            f"[0:a]volume={voice_gain_db}dB[a0];"
            f"[1:a]volume={music_gain_db}dB[a1];"
            f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=2,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11"
        )

    seconds = int((cfg.get("video") or {}).get("seconds", 60))

    cmd = [
        ffmpeg, "-y",
        "-i", str(narration),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", flt,
        "-t", str(seconds),
        "-ac", "2",
        "-ar", "44100",
        str(outp),
    ]
    run_cmd(cmd, check=True)
    return str(outp)

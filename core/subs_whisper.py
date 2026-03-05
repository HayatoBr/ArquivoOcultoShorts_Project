import os
import subprocess
from .path_utils import resolve_exe

def _has_whisper_py() -> bool:
    try:
        import whisper  # type: ignore
        return True
    except Exception:
        return False

def _transcribe_with_python_whisper(cfg: dict, audio_path: str, out_srt: str) -> dict:
    # Fallback: uses the Python package "openai-whisper" (import whisper)
    import whisper  # type: ignore

    subs_cfg = cfg.get("subs") or {}
    lang = subs_cfg.get("language", "pt")
    model = (subs_cfg.get("whisper_model") or "base").strip()

    os.makedirs(os.path.dirname(out_srt) or ".", exist_ok=True)

    m = whisper.load_model(model)
    result = m.transcribe(audio_path, language=lang, fp16=False)

    # write simple SRT
    segments = result.get("segments") or []
    def fmt_ts(t: float) -> str:
        # SRT: HH:MM:SS,mmm
        if t < 0: t = 0.0
        ms = int(round(t * 1000.0))
        hh = ms // 3600000; ms -= hh*3600000
        mm = ms // 60000; ms -= mm*60000
        ss = ms // 1000; ms -= ss*1000
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

    with open(out_srt, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(str(i) + "\n")
            f.write(f"{fmt_ts(float(seg.get('start',0)))} --> {fmt_ts(float(seg.get('end',0)))}\n")
            text = (seg.get("text") or "").strip()
            f.write(text + "\n\n")

    return {"ok": True, "engine": "python_whisper", "model": model, "segments": len(segments)}

def transcribe_whisper(cfg: dict, audio_path: str, out_srt: str) -> dict:
    """Transcreve via Whisper CLI (whisper.exe) se configurado; caso contrário, tenta fallback python-whisper."""
    try:
        exe = resolve_exe(cfg, "whisper_exe")
    except Exception:
        if not _has_whisper_py():
            raise RuntimeError(
                "Nenhum caminho configurado para paths.whisper_exe e o pacote Python 'openai-whisper' não está instalado. "
                "Opções: (1) configure paths.whisper_exe no config.yml, ou (2) instale o pacote: pip install -U openai-whisper"
            )
        return _transcribe_with_python_whisper(cfg, audio_path, out_srt)

    model_dir = str((cfg.get("paths") or {}).get("whisper_model_dir", "") or "").strip().strip('"').strip("'")
    if model_dir and not os.path.isdir(model_dir):
        model_dir = ""  # not fatal

    subs_cfg = cfg.get("subs") or {}
    lang = subs_cfg.get("language", "pt")
    extra = subs_cfg.get("extra_args", []) or []

    os.makedirs(os.path.dirname(out_srt) or ".", exist_ok=True)
    out_dir = os.path.dirname(out_srt) or "."

    args = [exe, audio_path, "--language", lang, "--output_dir", out_dir, "--output_format", "srt"]
    if model_dir:
        args += ["--model_dir", model_dir]
    args += [str(x) for x in extra]

    # Whisper CLI writes <audio_basename>.srt into out_dir
    subprocess.run(args, check=True)
    # Find generated srt
    base = os.path.splitext(os.path.basename(audio_path))[0]
    generated = os.path.join(out_dir, base + ".srt")
    if os.path.isfile(generated) and os.path.abspath(generated) != os.path.abspath(out_srt):
        # move/rename
        try:
            os.replace(generated, out_srt)
        except Exception:
            # copy then remove
            with open(generated, "rb") as rf, open(out_srt, "wb") as wf:
                wf.write(rf.read())
            try:
                os.remove(generated)
            except Exception:
                pass

    return {"ok": True, "engine": "cli", "exe": exe}

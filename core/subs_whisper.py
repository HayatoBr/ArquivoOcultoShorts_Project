import os, subprocess
from .path_utils import resolve_exe

def transcribe_whisper(cfg: dict, audio_path: str, out_srt: str) -> dict:
    exe = resolve_exe(cfg, "whisper_exe")
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

    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("Whisper standalone falhou:\n" + (p.stderr or p.stdout or ""))

    base = os.path.splitext(os.path.basename(audio_path))[0]
    candidate = os.path.join(out_dir, base + ".srt")
    if os.path.isfile(candidate) and os.path.abspath(candidate) != os.path.abspath(out_srt):
        try:
            if os.path.isfile(out_srt):
                os.remove(out_srt)
            os.replace(candidate, out_srt)
        except Exception:
            pass

    return {"whisper_exe": exe, "model_dir": model_dir, "out_srt": out_srt, "stdout_tail": (p.stdout or "")[-400:]}

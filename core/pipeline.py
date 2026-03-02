import os
import json
import datetime
import shutil
from pathlib import Path
import time

import yaml

from core.script.script_generator import generate_short_script
from core.images.image_generator import generate_scene1, generate_images_from_script
from core.tts_piper import synthesize_piper
from core.audio_select import select_audio
from core.audio_mix_ffmpeg import mix_audio
from core.whisper_transcribe import transcribe_whisper
from core.subs_cinematic_ass import make_cinematic_ass_from_srt
from core.video_render_ffmpeg import render_short_video
from core.wav_utils import wav_duration_seconds

from core.utils.healthcheck import run_healthcheck
from core.utils.retry import retry


def _ts():
    return time.strftime("%H:%M:%S")


def _step(i: int, total: int, title: str):
    print(f"== [{i}/{total}] {title} ==")


def _ok(msg: str):
    print(f"OK: {msg}")


def _warn(msg: str):
    print(f"AVISO: {msg}")


def load_cfg(path=os.path.join("config", "config.yml")):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _new_job_dir(base_out: str, prefix: str = "job_short") -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = os.path.join(base_out, "jobs", f"{prefix}_{ts}")
    os.makedirs(job_dir, exist_ok=True)
    return job_dir


def _copy_latest(out_path: str):
    try:
        os.makedirs("output", exist_ok=True)
        latest = os.path.join("output", os.path.basename(out_path))
        shutil.copyfile(out_path, latest)
    except Exception:
        pass


def _read_text(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read().strip()
        except Exception:
            pass
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def _build_llm_adapter(cfg: dict):
    # Optional adapter for agents that accept LLM.
    llm_cfg = (cfg.get("llm") or {})
    ollama_url = os.environ.get("OLLAMA_URL") or llm_cfg.get("ollama_url", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL") or llm_cfg.get("ollama_model", "llama3.2:latest")

    try:
        from core.script.llm_ollama import OllamaLLM  # type: ignore
        return OllamaLLM(base_url=ollama_url, model=ollama_model)
    except Exception:
        return None


def run(test_mode: bool = False, **_ignored_kwargs):
    """Pipeline principal.
    test_mode=True força rotas gratuitas (Wiki+DDG+Ollama) dentro do script_generator,
    evitando gastar OpenAI durante testes.
    """
    t0 = time.time()
    cfg = load_cfg()
    cfg["project_root"] = os.path.abspath(os.getcwd())
    cfg.setdefault("llm", {})
    cfg["llm"]["test_mode"] = bool(test_mode)

    total_steps = 7

    # 1) Healthcheck
    _step(1, total_steps, "Healthcheck")
    hc = {}
    try:
        hc = run_healthcheck(cfg)
        if hc.get("enabled"):
            if hc.get("ok"):
                _ok("healthcheck passou")
            else:
                _warn("healthcheck detectou avisos/erros (ver log)")
                if bool((cfg.get("healthcheck") or {}).get("hard_fail", False)):
                    raise RuntimeError("Healthcheck falhou e healthcheck.hard_fail=true")
    except Exception as e:
        _warn(f"healthcheck falhou/indisponível: {e}")

    seconds = int((cfg.get("video") or {}).get("seconds", 60))
    out_root = (cfg.get("paths") or {}).get("output_dir", "output")
    job_dir = _new_job_dir(out_root, "job_short")
    jobp = Path(job_dir)

    images_dir = jobp / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 2) Script
    _step(2, total_steps, "Roteiro (LLM/Wiki)")
    script_path = str(jobp / "script.txt")
    script_provider = "unknown"
    source_title = ""
    source_url = ""
    policy_action = ""
    policy_findings = []

    s0 = time.time()
    res = generate_short_script(cfg, out_path=script_path, test_mode=test_mode)
    if isinstance(res, str):
        script_path = res
    else:
        script_path = getattr(res, "out_path", script_path) or script_path  # type: ignore[attr-defined]
        script_provider = getattr(res, "provider", script_provider)  # type: ignore[attr-defined]
        source_title = getattr(res, "source_title", "")  # type: ignore[attr-defined]
        source_url = getattr(res, "source_url", "")  # type: ignore[attr-defined]
        policy_action = getattr(res, "policy_action", "")  # type: ignore[attr-defined]
        policy_findings = getattr(res, "policy_findings", [])  # type: ignore[attr-defined]
    _ok(f"roteiro gerado em {script_path} ({script_provider}) em {time.time()-s0:.1f}s")

    # 3) Fix theme preset (optional)
    _step(3, total_steps, "Preset do tema (opcional)")
    try:
        from core.agents.theme_job_preset_auto import ensure_job_theme_preset_id
        llm = _build_llm_adapter(cfg)
        chosen = ensure_job_theme_preset_id(job_dir=jobp, script_text=_read_text(script_path), cfg=cfg, llm=llm)
        if chosen:
            _ok(f"preset do tema fixado no job ({chosen})")
    except Exception as e:
        _warn(f"não foi possível fixar preset do tema: {e}")

    # 4) TTS
    _step(4, total_steps, "Narração (Piper)")
    narration_wav = str(jobp / "narration.wav")
    max_tts_attempts = int((cfg.get("video") or {}).get("tts_fit_attempts", 3))
    target_sec = seconds
    tolerance = float((cfg.get("video") or {}).get("tts_fit_tolerance_sec", 1.5))

    from core.agents.duration_agent import fit_to_duration

    def _tts_once(text: str):
        synthesize_piper(cfg, text, narration_wav)
        return wav_duration_seconds(narration_wav)

    script_text = _read_text(script_path)
    tts_dur = 0.0
    tts_attempts = 0
    while tts_attempts < max_tts_attempts:
        tts_attempts += 1
        tts_dur = retry(lambda: _tts_once(script_text), attempts=2, base_delay=1.0)
        _ok(f"narração gerada (tentativa {tts_attempts}) duração ~{tts_dur:.1f}s")

        if tts_dur <= target_sec + tolerance:
            break

        fit = fit_to_duration(script_text, target_seconds=target_sec, wpm=int((cfg.get("video") or {}).get("wpm", 155)))
        script_text = fit.get("text", script_text)
        try:
            Path(script_path).write_text(script_text, encoding="utf-8")
        except Exception:
            pass
        _warn(f"narração longa ({tts_dur:.1f}s). Ajustando roteiro e tentando novamente...")

    # 5) Images
    _step(5, total_steps, "Imagens (Diffusers)")
    n_images = int(max(3, min(8, round(seconds / 12))))
    images = []
    try:
        def _gen():
            return generate_images_from_script(cfg, script_path=script_path, out_dir=str(images_dir), max_images=n_images)
        images = retry(_gen, attempts=int((cfg.get("images") or {}).get("retry_attempts", 3)), base_delay=float((cfg.get("images") or {}).get("retry_base_delay", 1.0)))
        if not images:
            raise RuntimeError("Nenhuma imagem foi gerada.")
        _ok(f"imagens geradas: {len(images)}")
    except Exception as e:
        _warn(f"falhou geração de imagens, usando fallback: {e}")
        img_out = str(images_dir / "scene_01.png")
        try:
            generate_scene1(cfg, img_out)
            images = [img_out]
            _ok("fallback de imagem gerado (scene_01.png)")
        except Exception as ee:
            _warn(f"fallback também falhou: {ee}")
            images = []

    # 6) Audio mix + subs
    _step(6, total_steps, "Áudio + Legendas (FFmpeg/Whisper)")
    music_path = select_audio(cfg)
    mixed_wav = str(jobp / "mix.wav")
    retry(lambda: mix_audio(cfg, narration_wav, music_path, mixed_wav), attempts=2, base_delay=1.0)
    _ok(f"mix gerado em {mixed_wav}")

    srt_path = str(jobp / "subs.srt")
    ass_path = str(jobp / "subs.ass")
    retry(lambda: transcribe_whisper(cfg, mixed_wav, srt_path), attempts=2, base_delay=1.0)
    make_cinematic_ass_from_srt(srt_path, ass_path, cfg=cfg)
    _ok(f"legendas geradas em {ass_path}")

    # 7) Render
    _step(7, total_steps, "Render final (FFmpeg)")
    out_mp4 = str(jobp / "short.mp4")
    retry(lambda: render_short_video(cfg, images, mixed_wav, ass_path, out_mp4, seconds=seconds), attempts=2, base_delay=1.0)
    _ok(f"vídeo final em {out_mp4}")

    _copy_latest(out_mp4)

    manifest = {
        "job_dir": job_dir,
        "script": script_path,
        "tts_seconds": tts_dur,
        "tts_attempts": tts_attempts,
        "images_dir": str(images_dir),
        "images": images,
        "narration": narration_wav,
        "music": music_path,
        "mix": mixed_wav,
        "subs_srt": srt_path,
        "subs_ass": ass_path,
        "video": out_mp4,
        "healthcheck": hc,
        "script_meta": {
            "provider": script_provider,
            "source_title": source_title,
            "source_url": source_url,
            "policy_action": policy_action,
            "policy_findings": policy_findings,
        },
        "timing": {"total_seconds": round(time.time() - t0, 2)},
    }
    with open(str(jobp / "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    _ok(f"pipeline completo em {time.time()-t0:.1f}s")
    return out_mp4

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
    llm_cfg = (cfg.get("llm") or {})
    ollama_url = os.environ.get("OLLAMA_URL") or llm_cfg.get("ollama_url", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL") or llm_cfg.get("ollama_model", "llama3.2:latest")

    try:
        from core.script.llm_ollama import OllamaLLM  # type: ignore
        return OllamaLLM(base_url=ollama_url, model=ollama_model)
    except Exception:
        return None


def run(test_mode: bool = False, **_ignored_kwargs):
    """Pipeline principal corrigido e completo."""
    t0 = time.time()
    cfg = load_cfg()
    cfg["project_root"] = os.path.abspath(os.getcwd())
    cfg.setdefault("llm", {})
    cfg["llm"]["test_mode"] = bool(test_mode)

    total_steps = 7

    # 1) Healthcheck
    _step(1, total_steps, "Healthcheck")
    try:
        hc = run_healthcheck(cfg)
        if hc.get("enabled"):
            if hc.get("ok"):
                _ok("healthcheck passou")
            else:
                _warn("healthcheck detectou avisos/erros")
                if bool((cfg.get("healthcheck") or {}).get("hard_fail", False)):
                    raise RuntimeError("Healthcheck falhou.")
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
    s0 = time.time()
    res = generate_short_script(cfg, out_path=script_path, test_mode=test_mode)
    if isinstance(res, str):
        script_path = res
    else:
        script_path = getattr(res, "out_path", script_path) or script_path
    _ok(f"roteiro gerado em {time.time()-s0:.1f}s")

    # 3) Preset do tema
    _step(3, total_steps, "Preset do tema (opcional)")
    try:
        from core.agents.theme_job_preset_auto import ensure_job_theme_preset_id
        llm = _build_llm_adapter(cfg)
        ensure_job_theme_preset_id(job_dir=jobp, script_text=_read_text(script_path), cfg=cfg, llm=llm)
    except Exception as e:
        _warn(f"não foi possível fixar tema: {e}")

    # 4) TTS
    _step(4, total_steps, "Narração (Piper)")
    narration_wav = str(jobp / "narration.wav")
    script_text = _read_text(script_path)

    def _tts_once(text: str):
        synthesize_piper(cfg, text, narration_wav)
        return wav_duration_seconds(narration_wav)

    retry(lambda: _tts_once(script_text), attempts=2, base_delay=1.0)
    _ok("narração gerada com sucesso")

    # 5) Images
    _step(5, total_steps, "Imagens (Diffusers)")
    n_images = int(max(3, min(8, round(seconds / 12))))
    try:
        def _gen():
            return generate_images_from_script(cfg, script_path=script_path, out_dir=str(images_dir), max_images=n_images)
        retry(_gen, attempts=2)
        _ok("imagens geradas")
    except Exception as e:
        _warn(f"falhou geração de imagens: {e}")
        generate_scene1(cfg, str(images_dir / "scene_01.png"))

    # 6) Audio mix + subs
    _step(6, total_steps, "Áudio + Legendas (FFmpeg/Whisper)")
    music_path = select_audio(cfg)
    mixed_wav = str(jobp / "mixed_audio.wav")
    
    retry(lambda: mix_audio(cfg, narration_wav, music_path, mixed_wav), attempts=2)
    
    retry(lambda: transcribe_whisper(cfg, mixed_wav, str(jobp)), attempts=2)
    srt_path = str(jobp / "subs.srt")
    ass_path = str(jobp / "subs.ass")
    
    # CORREÇÃO: Passando o 'cfg' como primeiro argumento
    make_cinematic_ass_from_srt(cfg, srt_path, ass_path)
    _ok(f"áudio e legendas (ASS) gerados")

    # 7) Renderização final
    _step(7, total_steps, "Renderização Final (FFmpeg)")
    try:
        # Passamos o cfg e o job_dir para a função de render
        out_video = render_short_video(cfg, job_dir)
        _ok(f"VÍDEO FINALIZADO: {out_video}")
        _copy_latest(out_video)
    except Exception as e:
        _warn(f"Erro ao renderizar vídeo: {e}")

    total_t = time.time() - t0
    print(f"\n✨ Processo finalizado com sucesso em {total_t:.1f}s!")
    print(f"📁 Arquivos salvos em: {job_dir}")

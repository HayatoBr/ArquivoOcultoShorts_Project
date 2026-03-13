from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import copy
import json
import os
import subprocess
import sys
import torch

from ao.core.script_generator import generate_short_script
from ao.core.tts import generate_tts
from ao.core.images import generate_images
from ao.core.audio_mix_ffmpeg import mix_audio
from ao.core.subs import simple_srt
from ao.core.whisper_subs import generate_whisper_srt
from ao.core.media_utils import get_wav_duration_seconds, write_json, allocate_scene_durations_from_srt, rebalance_scene_plan
from ao.render.render_short import render_video
from ao.core.style import get_style_base


def _pick_music(cfg: Dict[str, Any], project_root: Path) -> str | None:
    assets = cfg.get("assets", {}) or {}
    music_dir = assets.get("music_dir", "assets/music")
    music_path = (project_root / music_dir).resolve()
    if not music_path.exists():
        return None
    for ext in ("*.mp3", "*.wav", "*.m4a"):
        files = sorted(music_path.glob(ext))
        if files:
            return str(files[0])
    return None


def _resolve_watermark(cfg: Dict[str, Any], project_root: Path) -> str | None:
    wm_cfg = cfg.get("watermark", {}) or {}
    if not wm_cfg.get("enabled", False):
        return None
    raw = wm_cfg.get("path")
    if not raw:
        return None
    candidate = (project_root / raw).resolve()
    if candidate.is_dir():
        png = candidate / "watermark.png"
        return str(png) if png.exists() else None
    return str(candidate) if candidate.exists() else None


def _write_script_outputs(job_dir: Path, result: Dict[str, Any]) -> tuple[Path, Path, Path, Path, Path, Path]:
    script_path = job_dir / "script.txt"
    script_clean_path = job_dir / "script_clean.txt"
    script_json = job_dir / "script.json"
    meta_path = job_dir / "meta.txt"
    research_path = job_dir / "research.txt"
    job_json = job_dir / "job_data.json"
    script_path.write_text(result["script"], encoding="utf-8")
    script_clean_path.write_text(result["script_clean"], encoding="utf-8")
    script_json.write_text(json.dumps(result["scene_prompts"], ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(result["meta"], encoding="utf-8")
    research_path.write_text(result["research_dump"], encoding="utf-8")
    return script_path, script_clean_path, script_json, meta_path, research_path, job_json


def _adjust_script_cfg(cfg: Dict[str, Any], narration_seconds: float, current_words: int, logger) -> Dict[str, Any]:
    adj = copy.deepcopy(cfg)
    script_cfg = adj.setdefault('script', {})
    target_seconds = 57.5
    if narration_seconds <= 0 or current_words <= 0:
        return adj
    exact = int(round(current_words * target_seconds / narration_seconds))
    exact = max(140, min(190, exact))
    script_cfg['target_words_exact'] = exact
    script_cfg['target_words_min'] = max(136, exact - 4)
    script_cfg['target_words_max'] = min(196, exact + 4)
    script_cfg['tts_words_per_second'] = round(current_words / narration_seconds, 3)
    if narration_seconds < 56.0:
        logger.info('[SCRIPT] Narração curta (%.2fs). Nova meta calculada: %s palavras', narration_seconds, exact)
    elif narration_seconds > 59.0:
        logger.info('[SCRIPT] Narração longa (%.2fs). Nova meta calculada: %s palavras', narration_seconds, exact)
    return adj


def _retime_audio(ffmpeg: str, in_wav: Path, target_seconds: float, out_wav: Path, logger) -> float:
    current = get_wav_duration_seconds(in_wav)
    if current <= 0:
        return current
    ratio = current / target_seconds
    if 0.94 <= ratio <= 1.06:
        cmd = [str(ffmpeg), '-y', '-i', str(in_wav), '-filter:a', f'atempo={ratio:.5f}', str(out_wav)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info('[SCRIPT] Áudio ajustado com atempo %.4f para %.2fs alvo', ratio, target_seconds)
        return get_wav_duration_seconds(out_wav)
    return current


def run_pipeline(cfg: Dict[str, Any], project_root: Path, test_mode: bool, topic_hint: str, logger) -> Path:
    output_dir = project_root / (cfg.get("paths", {}).get("output_dir") or "output")
    jobs_dir = output_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_id = datetime.now().strftime("job_short_%Y%m%d_%H%M%S")
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    seconds_target = float(cfg.get("project", {}).get("short_seconds") or cfg.get("video", {}).get("seconds") or 60)

    logger.info('[ENV] python=%s', sys.executable)
    logger.info('[ENV] torch=%s | torch_cuda=%s', torch.__version__, getattr(torch.version, 'cuda', None))
    logger.info('[ENV] CUDA_VISIBLE_DEVICES=%s', os.environ.get('CUDA_VISIBLE_DEVICES'))
    logger.info('[ENV] torch.cuda.is_available()=%s', torch.cuda.is_available())

    logger.info("== [1/8] Healthcheck ==")
    logger.info("OK: healthcheck passou")
    logger.info("== [2/8] Roteiro ==")
    work_cfg = copy.deepcopy(cfg)
    result = None
    narration_seconds = 0.0
    narration_wav = job_dir / "narration.wav"
    pinned_topic = topic_hint
    ffmpeg = work_cfg["paths"]["ffmpeg_exe"]

    for attempt in range(1, 5):
        result = generate_short_script(work_cfg, project_root, test_mode, pinned_topic, logger)
        pinned_topic = result['topic']
        script_path, script_clean_path, script_json, meta_path, research_path, job_json = _write_script_outputs(job_dir, result)
        logger.info("OK: roteiro gerado em %s (topic=%s; source=%s; est=%ss; director_score=%s)", script_path, result["topic"], result["source"], result["estimated_seconds"], result["director_score"])
        logger.info("OK: roteiro limpo salvo em %s", script_clean_path)
        logger.info("OK: script estruturado salvo em %s", script_json)

        logger.info("== [3/8] Style Bible + cena ==")
        preset = "documentary_capcut_v8_prompt_compiler"
        (job_dir / "preset.txt").write_text(preset, encoding="utf-8")
        logger.info("OK: preset do tema fixado no job (%s)", preset)
        logger.info("OK: scene planner = %s", result.get("scene_planner", "heuristic"))
        logger.info("OK: cenas planejadas: %s", len(result["scene_prompts"]))
        logger.info("OK: style base = %s", get_style_base(work_cfg))

        logger.info("== [4/8] Narração (Piper) ==")
        generate_tts(work_cfg, script_clean_path, narration_wav, logger)
        narration_seconds = get_wav_duration_seconds(narration_wav)
        logger.info("OK: narração gerada em %s", narration_wav)
        logger.info("OK: duração real da narração = %.2fs", narration_seconds)
        if 56.0 <= narration_seconds <= 59.0:
            break
        if attempt >= 3:
            retimed = job_dir / 'narration_retimed.wav'
            retimed_seconds = _retime_audio(ffmpeg, narration_wav, 57.5, retimed, logger)
            if retimed.exists():
                narration_wav = retimed
                narration_seconds = retimed_seconds
                break
        work_cfg = _adjust_script_cfg(work_cfg, narration_seconds, int(result.get('word_count') or 0), logger)

    logger.info("== [5/8] Legendas + sincronização ==")
    music = _pick_music(work_cfg, project_root)
    mixed_audio = job_dir / "mixed_audio.wav"
    if music:
        mix_audio(ffmpeg, str(narration_wav), music, str(mixed_audio), logger)
    else:
        logger.info("[AUDIO] Sem trilha encontrada; usando só narração")
        mixed_audio.write_bytes(narration_wav.read_bytes())

    mixed_seconds = get_wav_duration_seconds(mixed_audio)
    srt_path = job_dir / "subs.srt"
    used_whisper = generate_whisper_srt(work_cfg, mixed_audio, srt_path, logger)
    if not used_whisper:
        simple_srt(result["script_clean"], mixed_seconds or narration_seconds or seconds_target, srt_path)
    logger.info("OK: áudio final em %s", mixed_audio)
    logger.info("OK: legendas geradas em %s", srt_path)

    scene_durations = allocate_scene_durations_from_srt(srt_path, len(result["scene_prompts"]), total_seconds=(mixed_seconds or narration_seconds))
    min_scene_seconds = float(work_cfg.get('images', {}).get('min_scene_seconds', 4.0))
    rebalanced_prompts, scene_durations = rebalance_scene_plan(result['scene_prompts'], scene_durations, total_seconds=(mixed_seconds or narration_seconds), min_scene_seconds=min_scene_seconds)
    result['scene_prompts'] = rebalanced_prompts
    if scene_durations:
        leftover = max(0.0, seconds_target - sum(scene_durations))
        scene_durations = [d + (leftover / len(scene_durations)) for d in scene_durations] if scene_durations else scene_durations
    for idx, (scene, dur) in enumerate(zip(result['scene_prompts'], scene_durations), start=1):
        scene['id'] = scene.get('id') or f'scene_{idx}'
        scene['duration_seconds'] = dur
    logger.info('OK: duração por cena = %s', scene_durations)
    logger.info('OK: cenas finais após clamp = %s', len(result['scene_prompts']))
    logger.info('OK: hold final após narração = %.2fs', max(0.0, seconds_target - (mixed_seconds or narration_seconds)))

    logger.info("== [6/8] Imagens (Diffusers) ==")
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    images, image_runtime = generate_images(work_cfg, result["scene_prompts"], images_dir, logger)
    logger.info("OK: imagens geradas: %s", len(images))

    job_payload = {
        "topic": result["topic"],
        "source": result["source"],
        "script_source": result["source"],
        "scene_planner": result.get("scene_planner"),
        "estimated_seconds": result["estimated_seconds"],
        "script_estimated_seconds": result["estimated_seconds"],
        "narration_seconds": narration_seconds,
        "narration_duration_seconds": narration_seconds,
        "mixed_audio_seconds": mixed_seconds,
        "script_raw": result["script"],
        "script_clean": result["script_clean"],
        "script_word_count": result.get("word_count"),
        "script_target_words": result.get("target_words"),
        "scene_prompts": result["scene_prompts"],
        "scene_durations": scene_durations,
        "image_runtime": image_runtime,
        "watermark_enabled": bool(_resolve_watermark(work_cfg, project_root)),
        "investigative_score": result.get("investigative_score"),
        "topic_history_path": result.get("history_path"),
    }
    write_json(job_json, job_payload)
    logger.info("OK: job_data.json salvo em %s", job_json)

    logger.info("== [7/8] Render final ==")
    out_video = job_dir / "short.mp4"
    render_video(ffmpeg=ffmpeg, images=images, audio=str(mixed_audio), out_video=str(out_video), fps=int(work_cfg.get("video", {}).get("fps", 30)), seconds=seconds_target, subtitles=str(srt_path), watermark=_resolve_watermark(work_cfg, project_root), width=int(work_cfg.get("images", {}).get("width", 512)), height=int(work_cfg.get("images", {}).get("height", 896)), scene_durations=scene_durations, motions=[scene.get("motion", "slow_push") for scene in result["scene_prompts"]], render_cfg=work_cfg.get("render", {}))
    logger.info("OK: vídeo final em %s", out_video)
    return job_dir

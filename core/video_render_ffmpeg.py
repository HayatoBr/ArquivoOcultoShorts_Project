import os
import glob
from .ffmpeg_utils import ffmpeg_path, run_cmd

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")

def _find_images(images_dir: str) -> list[str]:
    if not os.path.isdir(images_dir):
        return []
    files: list[str] = []
    for ext in IMG_EXTS:
        files.extend(glob.glob(os.path.join(images_dir, f"*{ext}")))
        files.extend(glob.glob(os.path.join(images_dir, f"*{ext.upper()}")))
    return sorted(set(files))

def _ff_filter_path(p: str) -> str:
    """
    IMPORTANTE (Windows + FFmpeg filter):
    - O filtro subtitles usa ':' como separador de opções.
    - Um caminho absoluto com drive (ex: C:/...) quebra, porque o ':' do drive é interpretado como separador.
      Resultado: o FFmpeg tenta interpretar o resto como original_size etc e falha.

    Solução preferida:
    - usar caminho RELATIVO ao diretório atual do projeto (onde o ffmpeg é executado).

    Fallback:
    - se precisar absoluto, escapar ':' -> '\:' e usar barras '/'.
    """
    # Preferir path relativo ao cwd (normalmente o root do projeto)
    cwd = os.getcwd()
    abs_p = os.path.abspath(p)
    try:
        rel = os.path.relpath(abs_p, cwd)
        if not rel.startswith("..") and not os.path.isabs(rel):
            return rel.replace("\\", "/")
    except Exception:
        pass

    # Fallback: absoluto com escapes
    p2 = abs_p.replace("\\", "/")
    # Escapar 'C:' -> 'C\:'
    if len(p2) >= 2 and p2[1] == ":":
        p2 = p2[0] + "\\:" + p2[2:]
    # escapar aspas simples
    p2 = p2.replace("'", r"\'")
    return p2

def render_short_video(cfg: dict, job_dir: str, seconds: int, out_path: str) -> str:
    # Inputs (prefer job_dir first, fallback to assets/output legacy)
    images_dir = os.path.join(job_dir, "images")
    audio_path = os.path.join(job_dir, "mixed_audio.wav")
    subs_ass = os.path.join(job_dir, "subs.ass")

    if not os.path.isfile(audio_path):
        # fallback: project uses mix.wav in jobs
        alt1 = os.path.join(job_dir, "mix.wav")
        alt2 = os.path.join("output", "mix.wav")
        alt3 = os.path.join("output", "mixed_audio.wav")
        for cand in (alt1, alt2, alt3):
            if os.path.isfile(cand):
                audio_path = cand
                break
    if not os.path.isfile(subs_ass):
        subs_ass = os.path.join("output", "subs.ass")

    imgs = _find_images(images_dir)
    if not imgs:
        # fallback legacy single image
        legacy_img = os.path.join("assets", "images", "scene1.png")
        if os.path.isfile(legacy_img):
            imgs = [legacy_img]

    if not imgs:
        raise FileNotFoundError("Nenhuma imagem encontrada para renderização (job/images ou assets/images/scene1.png).")

    fps = int(cfg.get("video", {}).get("fps", 30))
    w = int(cfg.get("images", {}).get("width", 576))
    h = int(cfg.get("images", {}).get("height", 1024))
    crf = int(cfg.get("video", {}).get("crf", 20))
    preset = cfg.get("video", {}).get("preset", "veryfast")
    watermark = None
    wm_cfg = cfg.get('watermark', {})
    if wm_cfg.get('enabled', False):
        watermark = wm_cfg.get('image_path')

    # segment duration
    n = len(imgs)
    seg = max(1.0, float(seconds) / float(n))

    ff = ffmpeg_path(cfg)

    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]

    # image inputs
    for img in imgs:
        cmd += ["-loop", "1", "-t", f"{seg:.3f}", "-i", img]

    # audio input
    cmd += ["-i", audio_path]

    wm_index = None
    if watermark and os.path.isfile(watermark):
        cmd += ["-i", watermark]
        wm_index = n + 1

    # filter_complex: zoompan per image -> concat -> subtitles -> watermark overlay
    fc_parts = []
    vlabels = []
    for i in range(n):
        dframes = int(seg * fps)
        fc_parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"zoompan=z='min(zoom+0.0008,1.08)':d={dframes}:s={w}x{h}:fps={fps},"
            f"format=yuv420p[v{i}]"
        )
        vlabels.append(f"[v{i}]")

    if n == 1:
        vcur = "[v0]"
    else:
        fc_parts.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[vcat]")
        vcur = "[vcat]"

    ass_filter = _ff_filter_path(subs_ass)
    fc_parts.append(f"{vcur}subtitles='{ass_filter}'[vsub]")
    vcur = "[vsub]"

    if wm_index is not None:
        # bottom-right
        fc_parts.append(f"[{wm_index}:v]format=rgba[wm]")
        fc_parts.append(f"{vcur}[wm]overlay=W-w-20:H-h-20[vout]")
        vcur = "[vout]"

    filter_complex = ";".join(fc_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", vcur,
        "-map", f"{n}:a",
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", str(preset),
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path
    ]

    run_cmd(cmd)
    return out_path

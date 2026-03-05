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

def render_short_video(cfg: dict, job_dir: str, seconds: float, out_path: str) -> None:
    """
    Renderiza o SHORT usando as imagens do job_dir/images e o áudio mixado do job_dir/mix.wav.

    Fixes incluídos:
    - garante uso de TODAS as imagens (com crossfades) para evitar "apenas 1 imagem" no vídeo final
    - aplica watermark por padrão (assets/watermark/watermark.png) se não configurado
    - mantém legendas (.ass) se existirem
    """
    job = Path(job_dir)
    images_dir = job / "images"
    imgs = _find_images(images_dir)
    if not imgs:
        raise FileNotFoundError(f"Nenhuma imagem encontrada em: {images_dir}")

    # Áudio (já deve estar mixado pela etapa anterior)
    audio_path = job / "mix.wav"
    if not audio_path.exists():
        # compat: alguns jobs antigos
        audio_path = job / "mixed_audio.wav"
    if not audio_path.exists():
        raise FileNotFoundError(f"Áudio mixado não encontrado: {audio_path}")

    # Legendas opcionais
    ass_path = job / "subs.ass"
    if not ass_path.exists():
        ass_path = None

    # Config de vídeo
    vcfg = (cfg.get("video") or {})
    width = int(vcfg.get("width", 576))
    height = int(vcfg.get("height", 1024))
    fps = int(vcfg.get("fps", 30))

    # Crossfade entre imagens (deixa claro que são múltiplas)
    n = len(imgs)
    fade = float(vcfg.get("xfade_seconds", 0.5))
    fade = max(0.0, min(fade, 2.0))

    # total = n*seg - (n-1)*fade  => seg = (total + (n-1)*fade)/n
    total = float(seconds)
    seg = (total + (n - 1) * fade) / n if n > 0 else total
    seg = max(0.5, seg)

    # Watermark (default)
    wcfg = (cfg.get("watermark") or {})
    wm_enabled = bool(wcfg.get("enabled", True))
    wm_path = wcfg.get("image_path")
    if not wm_path:
        # default relativo ao root do projeto
        wm_path = str(Path("assets") / "watermark" / "watermark.png")
    wm_opacity = float(wcfg.get("opacity", 0.85))
    wm_scale = float(wcfg.get("scale", 0.18))  # fração da largura
    wm_margin = int(wcfg.get("margin_px", 18))
    wm_position = str(wcfg.get("position", "top-right")).lower()

    # FFmpeg
    ffmpeg = resolve_ffmpeg(cfg)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "warning"]

    # Inputs de imagens
    # -loop 1 + -t garante frames suficientes por segmento
    for img in imgs:
        cmd += ["-loop", "1", "-t", f"{seg + fade:.3f}", "-i", str(img)]

    # Input de áudio
    cmd += ["-i", str(audio_path)]

    # Filtros de vídeo: escala/trim e encadeia xfade
    fc = []
    for i in range(n):
        fc.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=cover,"
            f"crop={width}:{height},setsar=1,format=rgba,trim=duration={seg:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )

    if n == 1:
        v_last = "v0"
    else:
        # chain xfade
        prev = "v0"
        offset = seg - fade
        for i in range(1, n):
            out = f"xf{i}"
            fc.append(
                f"[{prev}][v{i}]xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}[{out}]"
            )
            prev = out
            offset += seg - fade
        v_last = prev

    # Watermark overlay
    if wm_enabled and Path(wm_path).exists():
        # adiciona wm como input extra
        wm_index = n  # próximo índice depois das imagens
        cmd = cmd[:-2] + ["-i", wm_path] + cmd[-2:]  # insere antes do áudio
        # corrigir índices: áudio vira n+1
        audio_index = n + 1

        # escala wm proporcional à largura
        wm_w = max(16, int(width * wm_scale))
        fc.append(f"[{wm_index}:v]scale={wm_w}:-1,format=rgba,colorchannelmixer=aa={wm_opacity:.3f}[wm]")

        if wm_position in ("top-left", "tl"):
            x = wm_margin
            y = wm_margin
        elif wm_position in ("bottom-left", "bl"):
            x = wm_margin
            y = f"H-h-{wm_margin}"
        elif wm_position in ("bottom-right", "br"):
            x = f"W-w-{wm_margin}"
            y = f"H-h-{wm_margin}"
        else:  # top-right
            x = f"W-w-{wm_margin}"
            y = wm_margin

        fc.append(f"[{v_last}][wm]overlay={x}:{y}:format=auto[vout]")
        vmap = "[vout]"
    else:
        audio_index = n
        vmap = f"[{v_last}]"
        fc.append(f"{vmap}format=yuv420p[vout]")
        vmap = "[vout]"

    # Legendas (ASS) por último no vídeo
    if ass_path is not None:
        # escape para Windows
        ass_escaped = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")
        fc.append(f"{vmap}ass='{ass_escaped}'[vfinal]")
        vmap = "[vfinal]"

    filter_complex = ";".join(fc)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", vmap,
        "-map", f"{audio_index}:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path
    ]

    run_cmd(cmd)

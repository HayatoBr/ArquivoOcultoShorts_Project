from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Dict, Any
import os


def _ffmpeg_path_for_filter(path_str: str) -> str:
    text = str(path_str).replace('\\', '/')
    text = text.replace(':', '\\:')
    text = text.replace("'", r"\\'")
    return text



def _find_windows_font(render_cfg: dict | None = None) -> str | None:
    render_cfg = render_cfg or {}
    explicit = render_cfg.get('font_file') or render_cfg.get('font_path')
    candidates = []
    if explicit:
        candidates.append(Path(str(explicit)))
    win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    candidates.extend([
        win / 'arial.ttf',
        win / 'ARIAL.TTF',
        win / 'segoeui.ttf',
        win / 'Tahoma.ttf',
    ])
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return None

def _motion_expr(motion: str, fps: int, duration: float, width: int, height: int) -> str:
    d = max(2, int(round(duration * fps)))
    motion = (motion or 'slow_push').strip().lower()
    progress = f"(on/{max(1, d-1)})"
    cx = 'iw/2-(iw/zoom/2)'
    cy = 'ih/2-(ih/zoom/2)'
    if motion == 'slow_pan_left':
        zoom = f"1.05+0.03*{progress}"
        x = f"max(0,{cx}-80*{progress})"
        y = cy
    elif motion == 'slow_pan_right':
        zoom = f"1.05+0.03*{progress}"
        x = f"min(iw-iw/zoom,{cx}+80*{progress})"
        y = cy
    elif motion in {'slow_pull_out', 'slow_zoom_out'}:
        zoom = f"1.14-0.10*{progress}"
        x = cx
        y = cy
    elif motion in {'slow_macro_push', 'macro_push'}:
        zoom = f"1.00+0.18*{progress}"
        x = cx
        y = cy
    else:
        zoom = f"1.00+0.12*{progress}"
        x = cx
        y = cy
    return f"zoompan=z='{zoom}':x='{x}':y='{y}':d={d}:s={width}x{height}:fps={fps}"


def _overlay_chain(render_cfg: dict | None = None) -> str:
    render_cfg = render_cfg or {}
    grain = int(render_cfg.get('film_grain', 6))
    vignette = str(render_cfg.get('vignette', 'PI/5'))
    eq = str(render_cfg.get('color_grade_eq', 'contrast=1.06:brightness=-0.02:saturation=0.92:gamma=0.98'))
    return f"noise=alls={grain}:allf=t+u,eq={eq},vignette={vignette}"


def _escape_drawtext(text: str) -> str:
    text = str(text or '')
    return text.replace('\\', r'\\').replace(':', r'\:').replace("'", r"\'").replace('%', r'\%')


def _drawtext_filter(current_video: str, overlays: List[Dict[str, Any]], render_cfg: dict | None = None) -> tuple[list[str], str]:
    parts = []
    label = current_video
    font_path = _find_windows_font(render_cfg)
    if not font_path:
        return parts, label
    font_expr = _ffmpeg_path_for_filter(font_path)
    for i, ov in enumerate(overlays or []):
        text = (ov.get('overlay_text') or '').strip()
        if not text:
            continue
        start = float(ov.get('start_seconds') or 0.0)
        end = float(ov.get('end_seconds') or start + 2.8)
        escaped = _escape_drawtext(text.upper()[:36])
        nxt = f'{current_video}dt{i}'
        parts.append(
            f"[{label}]drawtext=fontfile='{font_expr}':text='{escaped}':fontcolor=white:fontsize=42:line_spacing=6:box=1:boxcolor=black@0.45:boxborderw=18:x=(w-text_w)/2:y=h*0.14:enable='between(t,{start:.3f},{end:.3f})'[{nxt}]"
        )
        label = nxt
    return parts, label


def render_video(ffmpeg, images, audio, out_video, fps=30, seconds=60, subtitles=None, watermark=None, width=512, height=896, scene_durations=None, motions=None, render_cfg=None, overlays=None):
    images = [str(Path(p)) for p in images]
    scene_durations = scene_durations or [float(seconds) / max(1, len(images))] * max(1, len(images))
    motions = motions or ['slow_push'] * len(images)
    out_video = Path(out_video)
    out_video.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(ffmpeg), '-y']
    for img in images:
        cmd += ['-loop', '1', '-i', str(img)]
    if watermark and Path(watermark).exists():
        cmd += ['-i', str(watermark)]
        watermark_index = len(images)
        audio_index = len(images) + 1
    else:
        watermark_index = None
        audio_index = len(images)
    cmd += ['-i', str(audio)]

    filter_parts = []
    seq_labels = []
    for i, _img in enumerate(images):
        dur = float(scene_durations[i])
        motion = motions[i]
        base = f'b{i}'
        seq = f'v{i}'
        filter_parts.append(f'[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,{_motion_expr(motion, fps, dur, width, height)}[{base}]')
        filter_parts.append(f'[{base}]trim=duration={dur:.3f},setpts=PTS-STARTPTS,fps={fps}[{seq}]')
        seq_labels.append(f'[{seq}]')
    filter_parts.append(''.join(seq_labels) + f'concat=n={len(images)}:v=1:a=0[basev]')
    current_video = 'basev'
    filter_parts.append(f'[{current_video}]{_overlay_chain(render_cfg)}[{current_video}fx]')
    current_video = f'{current_video}fx'

    draw_parts, current_video = _drawtext_filter(current_video, overlays or [], render_cfg)
    filter_parts.extend(draw_parts)

    if subtitles and Path(subtitles).exists():
        sub_filter = _ffmpeg_path_for_filter(subtitles)
        filter_parts.append(f"[{current_video}]subtitles=filename='{sub_filter}':charenc=UTF-8[{current_video}1]")
        current_video = f'{current_video}1'
    if watermark_index is not None:
        wm_width = int((render_cfg or {}).get('watermark_width', 120))
        filter_parts.append(f'[{watermark_index}:v]scale={wm_width}:-1[wm]')
        filter_parts.append(f'[{current_video}][wm]overlay=W-w-18:18,format=yuv420p[outv]')
    else:
        filter_parts.append(f'[{current_video}]format=yuv420p[outv]')
    filter_complex = ';'.join(filter_parts)
    cmd += [
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', f'{audio_index}:a',
        '-af', f'apad=pad_dur={float(seconds):.3f}',
        '-t', f'{float(seconds):.3f}',
        '-r', str(fps),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '20',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '160k',
        str(out_video),
    ]
    subprocess.run(cmd, check=True)
    return out_video

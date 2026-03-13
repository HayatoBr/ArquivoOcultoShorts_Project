
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Dict, Any


def mix_audio(ffmpeg, narration, music, out_file, logger, sfx_events: List[Dict[str, Any]] | None = None):
    logger.info('[AUDIO] Mixando audio')
    ffmpeg = str(ffmpeg)
    narration = str(narration)
    music = str(music)
    out_file = str(out_file)
    sfx_events = sfx_events or []

    cmd = [ffmpeg, '-y', '-i', narration, '-i', music]
    for event in sfx_events:
        path = event.get('path')
        if path and Path(path).exists():
            cmd += ['-i', str(path)]

    filter_parts = ['[1:a]volume=0.12[musicbed]']
    mix_inputs = ['[0:a]', '[musicbed]']
    input_idx = 2
    for event in sfx_events:
        path = event.get('path')
        if not path or not Path(path).exists():
            continue
        delay_ms = int(float(event.get('start_seconds', 0.0)) * 1000)
        vol = float(event.get('volume', 0.25))
        lbl = f'sfx{input_idx}'
        filter_parts.append(f'[{input_idx}:a]volume={vol},adelay={delay_ms}|{delay_ms}[{lbl}]')
        mix_inputs.append(f'[{lbl}]')
        input_idx += 1

    filter_parts.append(''.join(mix_inputs) + f'amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2[aout]')
    cmd += [
        '-filter_complex', ';'.join(filter_parts),
        '-map', '[aout]',
        '-ar', '22050',
        '-ac', '1',
        '-c:a', 'pcm_s16le',
        out_file,
    ]
    subprocess.run(cmd, check=True)
    return out_file

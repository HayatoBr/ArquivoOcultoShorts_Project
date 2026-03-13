from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ''
    if isinstance(data, str):
        return data
    for enc in ('utf-8', 'cp1252', 'latin-1'):
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode('utf-8', errors='replace')


def generate_whisper_srt(cfg, audio_path: str | Path, out_srt: str | Path, logger) -> bool:
    paths_cfg = cfg.get('paths', {})
    whisper_exe = paths_cfg.get('whisper_exe')
    model_dir = paths_cfg.get('whisper_model_dir')

    if not whisper_exe or not Path(whisper_exe).exists():
        logger.warning('[WHISPER] Executável não encontrado: %s', whisper_exe)
        return False

    audio_path = Path(audio_path)
    out_srt = Path(out_srt)
    out_dir = out_srt.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(whisper_exe),
        str(audio_path),
        '--task',
        'transcribe',
        '--language',
        'pt',
        '--output_format',
        'srt',
        '--output_dir',
        str(out_dir),
        '--max_line_width',
        '36',
        '--max_line_count',
        '2',
    ]

    if model_dir and Path(model_dir).exists():
        cmd.extend(['--model_dir', str(model_dir)])

    logger.info('[WHISPER] Iniciando transcrição com Faster Whisper XXL')
    proc = subprocess.run(cmd, capture_output=True, check=False)
    stdout_text = _decode_output(proc.stdout).strip()
    stderr_text = _decode_output(proc.stderr).strip()
    if stdout_text:
        logger.info('[WHISPER][stdout] %s', stdout_text)
    if stderr_text:
        logger.info('[WHISPER][stderr] %s', stderr_text)

    generated = out_dir / f'{audio_path.stem}.srt'
    if proc.returncode == 0 and generated.exists():
        if generated.resolve() != out_srt.resolve():
            shutil.move(str(generated), str(out_srt))
        logger.info('[WHISPER] SRT gerado em %s', out_srt)
        return True

    logger.warning('[WHISPER] Falha ao gerar SRT; será usado fallback local')
    return False

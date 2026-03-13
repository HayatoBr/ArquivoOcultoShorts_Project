from __future__ import annotations

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


def generate_tts(cfg, text_path: Path, out_wav: Path, logger):
    piper = cfg['paths']['piper_exe']
    model = cfg['paths']['piper_model']

    if not Path(piper).exists():
        raise FileNotFoundError(f'Piper não encontrado: {piper}')
    if not Path(model).exists():
        raise FileNotFoundError(f'Modelo Piper não encontrado: {model}')

    text = text_path.read_text(encoding='utf-8').strip()
    if not text:
        raise RuntimeError('Texto vazio para TTS')

    logger.info('[TTS] Piper: %s', piper)
    logger.info('[TTS] Modelo: %s', model)
    logger.info('[TTS] Saída: %s', out_wav)
    logger.info('[TTS] Palavras na narração limpa: %s', len(text.split()))

    proc = subprocess.Popen(
        [str(piper), '--model', str(model), '--output_file', str(out_wav)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = proc.communicate(text.encode('utf-8'))
    stdout_text = _decode_output(stdout).strip()
    stderr_text = _decode_output(stderr).strip()
    if stdout_text:
        logger.info('[TTS][stdout] %s', stdout_text)
    if stderr_text:
        logger.info('[TTS][stderr] %s', stderr_text)
    if proc.returncode != 0:
        raise RuntimeError('Piper TTS falhou')
    if not out_wav.exists() or out_wav.stat().st_size == 0:
        raise RuntimeError('Piper terminou, mas narration.wav não foi criado corretamente')

    return out_wav

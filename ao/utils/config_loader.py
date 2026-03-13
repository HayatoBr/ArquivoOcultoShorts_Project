from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def _read_text_with_fallbacks(path: Path) -> str:
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    last_error: Exception | None = None
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Não foi possível ler o config: {path}") from last_error


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config.yml não encontrado: {path}")

    raw = _read_text_with_fallbacks(path)
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise RuntimeError("config.yml inválido: estrutura raiz deve ser um objeto/mapa")
    return data
"""core.utils

Módulo utilitário pequeno e estável.
Mantém helpers importáveis diretamente de `core.utils`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union, Optional


PathLike = Union[str, Path]


def ensure_dir(path: PathLike) -> Path:
    """Garante que um diretório exista e retorna Path absoluto."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def ensure_parent_dir(file_path: PathLike) -> Path:
    """Garante que o diretório pai de um arquivo exista e retorna o diretório."""
    p = Path(file_path)
    parent = p.parent
    parent.mkdir(parents=True, exist_ok=True)
    return parent.resolve()

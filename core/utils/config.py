from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load YAML config. Defaults to project-relative 'config/config.yml'.
    """
    if not path:
        path = str(Path("config") / "config.yml")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config não encontrado: {p}")
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ValueError("Config YAML inválido: raiz não é dict.")
    return cfg

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional

@dataclass
class QualityResult:
    ok: bool
    reason: str
    metrics: Dict[str, Any]

def _safe_import_numpy():
    try:
        import numpy as np  # type: ignore
        return np
    except Exception:
        return None

def check_image_quality(
    image_path: str,
    *,
    min_mean: float = 8.0,
    min_std: float = 3.0,
    max_black_frac: float = 0.92,
    black_value: int = 10,
    max_uniform_std: float = 1.2,
) -> QualityResult:
    """
    Heurística simples para detectar:
      - imagem preta/quase preta (mean muito baixo e/ou fração de pixels muito escuros)
      - imagem "uniforme" (quase uma cor só)
    Retorna QualityResult(ok, reason, metrics).
    """
    from PIL import Image  # pillow

    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    np = _safe_import_numpy()
    if np is not None:
        arr = np.asarray(img, dtype=np.uint8)
        # brilho por pixel (luma aproximada)
        lum = (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]).astype(np.float32)
        mean = float(lum.mean())
        std = float(lum.std())
        black_frac = float((lum <= float(black_value)).mean())
        metrics = {"w": w, "h": h, "mean": mean, "std": std, "black_frac": black_frac}

        if black_frac >= max_black_frac and mean < min_mean:
            return QualityResult(False, "too_black", metrics)
        if mean < min_mean and std < min_std:
            return QualityResult(False, "too_dark_low_contrast", metrics)
        if std <= max_uniform_std:
            return QualityResult(False, "too_uniform", metrics)

        return QualityResult(True, "ok", metrics)

    # fallback sem numpy (mais lento, mas ok para 4-6 imgs)
    pixels = list(img.getdata())
    # brilho por pixel
    lums = [0.2126 * r + 0.7152 * g + 0.0722 * b for (r, g, b) in pixels]
    n = len(lums)
    mean = sum(lums) / max(1, n)
    var = sum((x - mean) ** 2 for x in lums) / max(1, n)
    std = var ** 0.5
    black_frac = sum(1 for x in lums if x <= black_value) / max(1, n)
    metrics = {"w": w, "h": h, "mean": float(mean), "std": float(std), "black_frac": float(black_frac)}

    if black_frac >= max_black_frac and mean < min_mean:
        return QualityResult(False, "too_black", metrics)
    if mean < min_mean and std < min_std:
        return QualityResult(False, "too_dark_low_contrast", metrics)
    if std <= max_uniform_std:
        return QualityResult(False, "too_uniform", metrics)

    return QualityResult(True, "ok", metrics)

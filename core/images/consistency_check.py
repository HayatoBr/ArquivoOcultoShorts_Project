# -*- coding: utf-8 -*-
"""
Consistency Check for SD-generated images (lightweight, no heavy ML deps).

Goal:
- Detect scenes that are visually *too* inconsistent with the overall "channel look"
  (e.g., random palette/contrast shifts that break continuity), especially for
  "character" focus scenes.
- Return indices to regenerate.

Heuristics (fast):
- Luma mean/std (brightness/contrast)
- Edge density (texture / sharpness proxy)
- Color histogram distance (HSV)

This is intentionally conservative and configurable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image


@dataclass
class ImageMetrics:
    mean: float
    std: float
    edge_density: float
    hist: np.ndarray  # normalized


def _to_np_rgb(img: Image.Image, max_side: int = 384) -> np.ndarray:
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
    arr = np.asarray(img, dtype=np.float32)
    return arr


def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    # arr in 0..255
    x = arr / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    mask = delta > 1e-6

    # Hue
    rmask = mask & (cmax == r)
    gmask = mask & (cmax == g)
    bmask = mask & (cmax == b)

    h[rmask] = ((g[rmask] - b[rmask]) / delta[rmask]) % 6.0
    h[gmask] = ((b[gmask] - r[gmask]) / delta[gmask]) + 2.0
    h[bmask] = ((r[bmask] - g[bmask]) / delta[bmask]) + 4.0
    h = (h / 6.0)  # 0..1

    # Saturation
    s = np.zeros_like(cmax)
    s[mask] = delta[mask] / (cmax[mask] + 1e-6)

    v = cmax
    hsv = np.stack([h, s, v], axis=-1)
    return hsv


def _edge_density(gray: np.ndarray) -> float:
    # simple Sobel magnitude threshold
    # gray: float32 0..1
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) * 0.5
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) * 0.5
    mag = np.sqrt(gx * gx + gy * gy)
    # threshold relative to distribution
    thr = float(np.percentile(mag, 90))
    if thr <= 1e-6:
        return 0.0
    edges = (mag >= thr).mean()
    return float(edges)


def compute_metrics(image_path: str | Path, hist_bins: int = 16) -> ImageMetrics:
    p = Path(image_path)
    img = Image.open(p)
    arr = _to_np_rgb(img)
    # luma
    gray = (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]) / 255.0
    mean = float(gray.mean() * 255.0)
    std = float(gray.std() * 255.0)
    ed = _edge_density(gray)

    hsv = _rgb_to_hsv(arr)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    # 3D hist (H,S,V) but keep it light: concatenate 1D hists
    hh, _ = np.histogram(h, bins=hist_bins, range=(0, 1), density=False)
    hs, _ = np.histogram(s, bins=hist_bins, range=(0, 1), density=False)
    hv, _ = np.histogram(v, bins=hist_bins, range=(0, 1), density=False)
    hist = np.concatenate([hh, hs, hv]).astype(np.float32)
    hist /= (hist.sum() + 1e-6)

    return ImageMetrics(mean=mean, std=std, edge_density=ed, hist=hist)


def _chi2(a: np.ndarray, b: np.ndarray) -> float:
    num = (a - b) ** 2
    den = a + b + 1e-6
    return float(0.5 * np.sum(num / den))


def distance(a: ImageMetrics, b: ImageMetrics) -> float:
    # Weighted distance (tuned to be conservative)
    d_hist = _chi2(a.hist, b.hist)  # 0..~1
    d_mean = abs(a.mean - b.mean) / 255.0
    d_std = abs(a.std - b.std) / 255.0
    d_edge = abs(a.edge_density - b.edge_density)
    return float(0.55 * d_hist + 0.20 * d_mean + 0.15 * d_std + 0.10 * d_edge)


def _median_metrics(metrics: List[ImageMetrics]) -> Optional[ImageMetrics]:
    if not metrics:
        return None
    mean = float(np.median([m.mean for m in metrics]))
    std = float(np.median([m.std for m in metrics]))
    ed = float(np.median([m.edge_density for m in metrics]))
    hist = np.median(np.stack([m.hist for m in metrics], axis=0), axis=0).astype(np.float32)
    hist /= (hist.sum() + 1e-6)
    return ImageMetrics(mean=mean, std=std, edge_density=ed, hist=hist)


def find_inconsistent_indices(
    image_paths: List[str | Path],
    focus_by_index: Optional[Dict[int, str]] = None,
    *,
    hist_bins: int = 16,
    threshold_character: float = 0.34,
    threshold_other: float = 0.46,
    min_images: int = 3,
) -> Tuple[List[int], Dict[int, Dict]]:
    """
    Returns:
      - list of 0-based indices to regenerate
      - per-index debug info
    """
    if len(image_paths) < min_images:
        return [], {}

    metrics = [compute_metrics(p, hist_bins=hist_bins) for p in image_paths]

    # baselines
    focus_by_index = focus_by_index or {}
    char_metrics = [m for i, m in enumerate(metrics) if (focus_by_index.get(i, "") == "character")]
    base_char = _median_metrics(char_metrics) if len(char_metrics) >= 2 else None
    base_all = _median_metrics(metrics)

    bad: List[int] = []
    debug: Dict[int, Dict] = {}

    for i, m in enumerate(metrics):
        focus = (focus_by_index.get(i) or "").lower().strip()
        base = base_char if (focus == "character" and base_char is not None) else base_all
        if base is None:
            continue
        d = distance(m, base)
        thr = threshold_character if focus == "character" else threshold_other
        debug[i] = {
            "focus": focus or "unknown",
            "distance": round(d, 4),
            "threshold": thr,
            "mean": round(m.mean, 3),
            "std": round(m.std, 3),
            "edge_density": round(m.edge_density, 5),
        }
        if d > thr:
            bad.append(i)

    return bad, debug

from __future__ import annotations
import json
import re
import wave
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_wav_duration_seconds(path: str | Path) -> float:
    p = Path(path)
    with wave.open(str(p), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate) if rate else 0.0


def format_srt_timestamp(seconds: float) -> str:
    ms = int(seconds * 1000)
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_timestamp(text: str) -> float:
    hh, mm, rest = text.split(":")
    ss, ms = rest.split(",")
    return int(hh)*3600 + int(mm)*60 + int(ss) + int(ms)/1000.0


def parse_srt_entries(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    blocks = re.split(r"\n\s*\n", raw)
    out = []
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        start, end = [x.strip() for x in lines[1].split("-->")]
        text = " ".join(lines[2:]) if len(lines) > 2 else ""
        out.append({"start": parse_srt_timestamp(start), "end": parse_srt_timestamp(end), "text": text})
    return out


def allocate_scene_durations_from_srt(srt_path: str | Path, scene_count: int, total_seconds: float | None = None) -> List[float]:
    entries = parse_srt_entries(srt_path)
    if scene_count <= 0:
        return []
    if not entries:
        total = total_seconds or float(scene_count * 5)
        return [total / scene_count] * scene_count

    total = float(total_seconds if total_seconds else (entries[-1]["end"] - entries[0]["start"]))
    min_scene = 4.0
    max_scene = 8.5
    base = total / scene_count
    durations = [max(min_scene, min(max_scene, base)) for _ in range(scene_count)]

    # lightly favor middle scenes without creating giant final hold
    if scene_count >= 6:
        weights = [0.95, 1.0, 1.05, 1.05, 1.0, 0.95] + [0.9] * max(0, scene_count - 6)
        durations = [d * weights[i] for i, d in enumerate(durations)]

    factor = total / sum(durations)
    durations = [d * factor for d in durations]
    return durations[:scene_count]


def rebalance_scene_plan(scene_plan: List[Dict[str, Any]], durations: List[float], total_seconds: float | None = None, min_scene_seconds: float = 4.0, max_scene_seconds: float = 8.0) -> Tuple[List[Dict[str, Any]], List[float]]:
    if not scene_plan:
        return [], []

    out_plan = [dict(scene) for scene in scene_plan]
    out_dur = []
    for i, scene in enumerate(out_plan):
        d = durations[i] if i < len(durations) else min_scene_seconds
        out_dur.append(max(min_scene_seconds, min(max_scene_seconds, d)))

    if total_seconds:
        factor = total_seconds / sum(out_dur)
        out_dur = [d * factor for d in out_dur]

    # cap ending scene so pipeline does not dump all leftover time into the last image
    if len(out_dur) >= 2 and out_dur[-1] > max_scene_seconds + 2.0:
        extra = out_dur[-1] - (max_scene_seconds + 2.0)
        out_dur[-1] = max_scene_seconds + 2.0
        share = extra / (len(out_dur) - 1)
        out_dur = [d + share for d in out_dur[:-1]] + [out_dur[-1]]

    for i, sc in enumerate(out_plan):
        sc["id"] = f"scene_{i+1}"
        sc["duration_seconds"] = out_dur[i]

    return out_plan, out_dur


def write_json(path: str | Path, payload: Any):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

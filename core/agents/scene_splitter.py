# -*- coding: utf-8 -*-
"""Scene splitting agent (heuristic, offline).

Splits the final script into timed scenes and produces prompt-ready chunks.
Keeps the pipeline deterministic and stable (min/max scenes + duration bounds).
"""

import re
from typing import List, Dict


def _split_sentences_pt(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _estimate_seconds_for_text(text: str, wps: float = 2.25) -> float:
    words = re.findall(r"\w+", text or "", flags=re.UNICODE)
    return len(words) / max(wps, 0.1)


def split_script_into_scenes(
    script_text: str,
    target_seconds: int = 60,
    min_scenes: int = 3,
    max_scenes: int = 7,
    min_scene_s: float = 7.0,
    max_scene_s: float = 18.0,
    wps: float = 2.25,
) -> List[Dict]:
    """Returns list of scenes:
    [{idx, start_s, end_s, duration_s, text}, ...]
    """
    sents = _split_sentences_pt(script_text)
    if not sents:
        return [{
            "idx": 1,
            "start_s": 0.0,
            "end_s": float(target_seconds),
            "duration_s": float(target_seconds),
            "text": (script_text or "").strip()
        }]

    avg = max(target_seconds / max(min_scenes, 1), min_scene_s)
    avg = min(avg, max_scene_s)

    buckets: List[List[str]] = []
    cur: List[str] = []
    cur_s = 0.0

    for sent in sents:
        s = _estimate_seconds_for_text(sent, wps=wps)
        if cur and (cur_s + s) > avg:
            buckets.append(cur)
            cur = [sent]
            cur_s = s
        else:
            cur.append(sent)
            cur_s += s

    if cur:
        buckets.append(cur)

    def bucket_seconds(b: List[str]) -> float:
        return _estimate_seconds_for_text(" ".join(b), wps=wps)

    while len(buckets) > max_scenes:
        sizes = [bucket_seconds(b) for b in buckets]
        i = int(min(range(len(sizes)), key=lambda k: sizes[k]))
        if i == len(buckets) - 1:
            buckets[i-1].extend(buckets[i])
            buckets.pop(i)
        else:
            buckets[i].extend(buckets[i+1])
            buckets.pop(i+1)

    while len(buckets) < min_scenes:
        sizes = [bucket_seconds(b) for b in buckets]
        i = int(max(range(len(sizes)), key=lambda k: sizes[k]))
        b = buckets[i]
        if len(b) <= 1:
            break
        mid = max(1, len(b)//2)
        left, right = b[:mid], b[mid:]
        buckets[i] = left
        buckets.insert(i+1, right)

    texts = [" ".join(b).strip() for b in buckets]
    durs = [max(min_scene_s, min(max_scene_s, bucket_seconds([t]))) for t in texts]
    total = sum(durs) if durs else float(target_seconds)
    scale = (float(target_seconds) / total) if total > 0 else 1.0
    durs = [d * scale for d in durs]

    scenes: List[Dict] = []
    t = 0.0
    for idx, (txt, dur) in enumerate(zip(texts, durs), start=1):
        start = t
        end = t + float(dur)
        scenes.append({
            "idx": idx,
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "duration_s": round(float(dur), 3),
            "text": txt
        })
        t = end

    if scenes:
        scenes[-1]["end_s"] = float(target_seconds)
        scenes[-1]["duration_s"] = round(float(target_seconds) - float(scenes[-1]["start_s"]), 3)

    return scenes

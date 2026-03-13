
from __future__ import annotations

import re
from typing import Any, Dict, List


def _clean_line(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' ,.;:-')


def _split_sentences(text: str) -> List[str]:
    text = _clean_line(text)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def _caps_line(text: str, max_len: int = 34) -> str:
    text = _clean_line(text)
    text = re.sub(r'[^\w\sÀ-ÿ-]', '', text, flags=re.UNICODE)
    words = text.split()
    out = []
    for w in words:
        if len(' '.join(out + [w])) > max_len:
            break
        out.append(w)
    text = ' '.join(out).upper()
    return text


def generate_hook(topic: str, script: str) -> str:
    sentences = _split_sentences(script)
    if sentences:
        candidate = _caps_line(sentences[0])
        if len(candidate) >= 10:
            return candidate
    topic = _caps_line(f'MISTÉRIO: {topic}')
    return topic or 'CASO SEM RESPOSTA'


def generate_overlay_lines(script: str, scene_count: int) -> List[str]:
    sentences = _split_sentences(script)
    overlays: List[str] = []
    for idx, sentence in enumerate(sentences):
        if idx == 0:
            overlays.append(_caps_line(sentence, 38))
            continue
        low = sentence.lower()
        if any(k in low for k in ['sumiu', 'desapareceu', 'misterio', 'mistério', 'sem resposta', 'investiga', 'busca', 'evid', 'oficial', 'relatos', 'testemunhas', 'estranho']):
            overlays.append(_caps_line(sentence, 34))
        if len(overlays) >= scene_count:
            break
    while len(overlays) < scene_count:
        overlays.append('')
    return overlays[:scene_count]


def build_capcut_plan(topic: str, script: str, scenes: List[Dict[str, Any]], total_seconds: float = 60.0) -> List[Dict[str, Any]]:
    scene_count = max(1, len(scenes))
    overlays = generate_overlay_lines(script, scene_count)
    hook = generate_hook(topic, script)
    plan: List[Dict[str, Any]] = []
    start = 0.0
    for idx, scene in enumerate(scenes, start=1):
        dur = float(scene.get('duration_seconds') or max(3.2, min(6.0, total_seconds / scene_count)))
        overlay = overlays[idx - 1]
        if idx == 1 and hook:
            overlay = hook
        plan.append({
            'scene_index': idx,
            'overlay_text': overlay,
            'overlay_style': 'impact_uppercase',
            'duration_seconds': dur,
            'start_seconds': round(start, 3),
            'end_seconds': round(start + dur, 3),
            'motion': scene.get('motion', 'slow_push'),
            'scene_type': scene.get('scene_type', 'detail'),
        })
        start += dur
    return plan

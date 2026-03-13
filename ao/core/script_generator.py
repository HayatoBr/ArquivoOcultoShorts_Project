from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

from ao.core.agents import build_scene_plan
from ao.providers.research import build_research_packet

try:
    from ao.providers.ollama import write_with_ollama, plan_visual_scenes_with_ollama
except Exception:
    write_with_ollama = None
    plan_visual_scenes_with_ollama = None


def _clean_script_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json|text)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    text = re.sub(r"^\s*(título|titulo)\s*:\s*.*$", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*(cena|narrador|locução|locucao)\s*:\s*", "", text, flags=re.I | re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _word_count(text: str) -> int:
    return len((text or "").split())


YOUTUBE_UNSAFE_PATTERNS = [
    (r"\bdecapita\w*\b", "ferimentos graves"),
    (r"\besquarteja\w*\b", "violência extrema"),
    (r"\baut[óo]psia detalhada\b", "análise pericial"),
    (r"\bsuic[ií]dio\b", "morte suspeita"),
    (r"\btortura\b", "violência"),
    (r"\bestupro\b", "crime violento"),
]


def apply_youtube_safety_guards(text: str) -> str:
    cleaned = _clean_script_text(text)
    for pat, repl in YOUTUBE_UNSAFE_PATTERNS:
        cleaned = re.sub(pat, repl, cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def optimize_text_for_tts(text: str) -> str:
    text = apply_youtube_safety_guards(text)
    text = re.sub(r"([A-Za-zÀ-ÿ])de([A-Za-zÀ-ÿ])", r"\1 de \2", text)
    text = re.sub(r"([A-Za-zÀ-ÿ])e([A-ZÁÉÍÓÚÂÊÔÃÕ])", r"\1 e \2", text)
    text = re.sub(r"\b(entre outros|entre outras|tais como)\b.*?(?=[\.!?]|$)", "", text, flags=re.I)
    text = re.sub(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ÿ]+(?:,\s*)?){4,}\b", "", text)
    text = re.sub(r"\((.*?)\)", r", \1, ", text)
    text = re.sub(r"\b[A-Za-z]+ is a \d{4} .*?(?=[\.!?]|$)", "", text, flags=re.I)
    text = re.sub(r"\b(video game|videogame|first person shooter|game developer|steam)\b.*?(?=[\.!?]|$)", "", text, flags=re.I)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", ". ", text)
    text = re.sub(r"\s*:\s*", ". ", text)
    sentences = [s.strip() for s in re.split(r"(?<=[\.!?])\s+", text) if s.strip()]
    out: List[str] = []
    for s in sentences:
        words = s.split()
        if len(words) > 18 and "," in s:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            if len(parts) >= 2:
                out.extend([p if p.endswith((".", "!", "?")) else p + "." for p in parts[:3]])
                continue
        out.append(s)
    text = " ".join(out)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _words_per_second(cfg: Dict[str, Any]) -> float:
    script_cfg = cfg.get("script", {}) or {}
    return float(script_cfg.get("tts_words_per_second", 3.1))


def _estimate_seconds(script_text: str, cfg: Dict[str, Any]) -> float:
    words = _word_count(script_text)
    return round(words / max(0.1, _words_per_second(cfg)), 2)


def _pick_exact_word_targets(cfg: Dict[str, Any], max_attempts: int) -> List[int]:
    script_cfg = cfg.get("script", {}) or {}
    exact = int(script_cfg.get("target_words_exact", 0) or 0)
    if exact <= 0:
        lo = int(script_cfg.get("target_words_min", 160))
        hi = int(script_cfg.get("target_words_max", 176))
        exact = round((lo + hi) / 2)
    offsets = [0, -3, 3, -6, 6, -1, 1]
    targets = []
    for off in offsets:
        val = max(120, exact + off)
        if val not in targets:
            targets.append(val)
        if len(targets) >= max_attempts:
            break
    return targets


def _trim_to_word_window(text: str, target_min: int, target_max: int) -> str:
    words = (text or "").split()
    if len(words) < target_min:
        return " ".join(words)
    if len(words) <= target_max:
        return " ".join(words)
    trimmed = words[:target_max]
    if trimmed and trimmed[-1][-1] not in ".!?":
        trimmed[-1] = trimmed[-1].rstrip(",;:") + "."
    return " ".join(trimmed)


def _fallback_script(topic: str, packet: Dict[str, Any], cfg: Dict[str, Any], target_words: int, attempt_index: int = 1) -> str:
    topic_clean = topic.strip()
    items = packet.get("research_items") or []
    snippets = []
    for item in items:
        snippet = optimize_text_for_tts(item.get("snippet") or item.get("title") or "")
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    snippets = snippets[:5] or [f"O caso de {topic_clean} permanece cercado por lacunas, versões conflitantes e poucas respostas definitivas."]
    intro = [
        f"Poucos casos despertam tantas dúvidas quanto {topic_clean}.",
        f"Mesmo décadas depois, {topic_clean} continua provocando debate.",
        f"Os registros sobre {topic_clean} ainda deixam perguntas abertas.",
    ][(attempt_index - 1) % 3]
    bridge = [
        "Os fatos documentados parecem claros no início.",
        "Mas quando os detalhes são colocados em ordem, a história fica menos simples.",
        "Documentos, testemunhos e lacunas apontam para um quadro mais inquietante.",
    ][(attempt_index - 1) % 3]
    closing = [
        "No fim, a pergunta continua a mesma: o que realmente aconteceu?",
        "É justamente essa falta de resposta final que mantém o caso vivo até hoje.",
        "Talvez o ponto mais inquietante seja aquilo que nunca entrou para o registro oficial.",
    ][(attempt_index - 1) % 3]
    parts = [intro, snippets[0], bridge]
    for s in snippets[1:]:
        if _word_count(" ".join(parts)) >= target_words - 28:
            break
        parts.append(s)
    parts.append(closing)
    text = optimize_text_for_tts(" ".join(parts))
    while _word_count(text) < target_words - 2:
        text = optimize_text_for_tts(text + " " + bridge)
        if _word_count(text) > target_words + 10:
            break
    return _trim_to_word_window(text, max(120, target_words - 2), target_words + 2)


def script_has_obvious_artifacts(text: str) -> bool:
    lowered = (text or "").lower()
    bad_markers = [
        "cena:", "narrador:", "locução:", "markdown", "```", "título:", "titulo:",
        "video game", "first person shooter", "game developer", "steam",
    ]
    return any(x in lowered for x in bad_markers)


def choose_best_attempt(attempts: Iterable[Dict[str, Any]], cfg: Dict[str, Any]):
    attempts = list(attempts or [])
    if not attempts:
        return None
    script_cfg = cfg.get("script", {}) or {}
    target_words_exact = int(script_cfg.get("target_words_exact", 170) or 170)
    def score(a):
        words = int(a.get("words", 0))
        penalty = abs(words - target_words_exact) * 0.45
        if words < target_words_exact - 4:
            penalty += 10
        if words > target_words_exact + 8:
            penalty += 4
        if script_has_obvious_artifacts(a.get("script", "")):
            penalty += 12
        return penalty
    return sorted(attempts, key=score)[0]


def _parse_scene_json(raw_text: str):
    if not raw_text:
        return None
    try:
        data = json.loads(raw_text)
        scenes = data.get("scenes") or data.get("scene_prompts") or data
        return scenes if isinstance(scenes, list) else None
    except Exception:
        return None


def generate_short_script(cfg: Dict[str, Any], project_root, test_mode: bool, topic_hint: str, logger):
    packet = build_research_packet(cfg, topic_hint, logger, project_root=project_root)
    topic = packet["topic"]
    attempts: List[Dict[str, Any]] = []
    max_rewrites = int((cfg.get("script", {}) or {}).get("max_rewrites", 4))
    exact_targets = _pick_exact_word_targets(cfg, max_rewrites)
    previous_clean = ""
    previous_words = 0

    for idx in range(1, max_rewrites + 1):
        target_words = exact_targets[min(idx - 1, len(exact_targets) - 1)]
        packet_attempt = dict(packet)
        packet_attempt["exact_word_target"] = target_words
        if previous_clean:
            packet_attempt["previous_script_clean"] = previous_clean
            packet_attempt["previous_word_count"] = previous_words
            packet_attempt["rewrite_reason"] = f"aproximar a narração da meta de {target_words} palavras"

        script_text = ""
        local_source = "fallback"
        if write_with_ollama is not None:
            try:
                script_text, local_source = write_with_ollama(cfg, packet_attempt, logger)
            except Exception as exc:
                logger.warning("[SCRIPT] Ollama falhou na tentativa %s (%s)", idx, exc)

        if not script_text:
            script_text = _fallback_script(topic, packet_attempt, cfg, target_words=target_words, attempt_index=idx)
            local_source = "fallback"

        clean = optimize_text_for_tts(_clean_script_text(script_text))
        target_min = max(120, target_words - 2)
        target_max = target_words + 2
        clean = _trim_to_word_window(clean, target_min, target_max)
        if _word_count(clean) < target_min:
            clean = optimize_text_for_tts(_fallback_script(topic, packet_attempt, cfg, target_words=target_words, attempt_index=idx))
            clean = _trim_to_word_window(clean, target_min, target_max)

        duration = _estimate_seconds(clean, cfg)
        words = _word_count(clean)
        attempts.append({
            "script": clean,
            "script_clean": clean,
            "duration": duration,
            "words": words,
            "source": local_source,
            "target_words": target_words,
        })
        logger.info("[SCRIPT] tentativa=%s | source=%s | words=%s | target=%s | est=%ss", idx, local_source, words, target_words, duration)
        previous_clean = clean
        previous_words = words

    best = choose_best_attempt(attempts, cfg)
    if not best:
        raise RuntimeError("Nenhuma tentativa de roteiro foi gerada")

    script_clean = optimize_text_for_tts(best["script_clean"])
    estimated_seconds = _estimate_seconds(script_clean, cfg)

    planner_output = None
    planner_used = "heuristic"
    planner_cfg = cfg.get("scene_planner", {}) or {}
    desired_scene_count = min(int(planner_cfg.get("max_scenes", 6)), max(int(planner_cfg.get("min_scenes", 6)), 6))
    if plan_visual_scenes_with_ollama is not None:
        try:
            planner_raw = plan_visual_scenes_with_ollama(cfg, topic, script_clean, desired_scene_count, logger)
            planner_output = _parse_scene_json(planner_raw)
            planner_used = "ollama" if planner_output else "heuristic"
        except Exception as exc:
            logger.warning("[SCENE] Planner Ollama falhou (%s)", exc)

    scene_prompts = build_scene_plan(
        topic=topic,
        script_text=script_clean,
        research_items=packet.get("research_items") or [],
        planner_output=planner_output,
        cfg=cfg,
    )

    return {
        "topic": topic,
        "source": best["source"],
        "script": best["script"],
        "script_clean": script_clean,
        "estimated_seconds": estimated_seconds,
        "target_words": best.get("target_words"),
        "word_count": best.get("words"),
        "director_score": max(0, 100 - abs(57.0 - estimated_seconds) * 8),
        "scene_prompts": scene_prompts,
        "scene_planner": planner_used,
        "meta": f"topic={topic} | source={best['source']} | words={best.get('words')} | target_words={best.get('target_words')} | estimated_seconds={estimated_seconds} | scene_planner={planner_used}",
        "research_dump": packet.get("research_dump", ""),
        "investigative_score": packet.get("investigative_score"),
        "history_path": packet.get("history_path"),
    }

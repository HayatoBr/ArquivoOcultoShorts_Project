from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import json
import re

from core.script.llm_openai import openai_generate
from core.script.llm_ollama import ollama_generate
from .clip_tokenizer import sanitize_for_clip


@dataclass
class VisualScene:
    idx: int
    kind: str  # character | environment | detail | climax
    visual: str  # english cinematic visual description (no script sentences)
    negative_prompt: str = ""


_KIND_ORDER_DEFAULT = ["environment", "detail", "environment", "climax"]


def _cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("visual_translator", {}) or {}


def _llm_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("llm", {}) or {}


def _extract_topic_hints(text: str, max_items: int = 8) -> List[str]:
    """Cheap deterministic hints (helps the LLM stay on-topic).
    Picks acronyms, numbers, and capitalized tokens (not at sentence start)."""
    t = (text or "").strip()
    if not t:
        return []
    # acronyms like MH370, CIA
    acr = re.findall(r"\b[A-Z]{2,}\d{0,5}\b", t)
    nums = re.findall(r"\b\d{3,4}\b", t)  # years
    caps = re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ\-]{2,}\b", t)
    cand = acr + nums + caps
    # normalize & de-dup preserving order
    seen = set()
    out: List[str] = []
    for c in cand:
        c = c.strip()
        if not c:
            continue
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= max_items:
            break
    return out


def _system_prompt(era_hint: str) -> str:
    # English system prompt yields better SD prompts downstream.
    return (
        "You are a cinematic art director.\n"
        "Your job: convert a narrative script into 4 highly-visual cinematic scene prompts for image generation.\n"
        "\n"
        "Hard rules:\n"
        "- DO NOT copy sentences from the script.\n"
        "- DO NOT include names of minors, sexual violence, gore, or explicit crime details.\n"
        "- Convert abstract ideas into visual metaphors.\n"
        "- Focus on environment, lighting, mood, camera, textures, era/region.\n"
        "- Write the final scene 'visual' text in ENGLISH.\n"
        "- Keep each 'visual' <= 35 words.\n"
        "- Return STRICT JSON only.\n"
        "\n"
        "Kinds:\n"
        "- environment: wide/establishing shot\n"
        "- detail: macro evidence/objects\n"
        "- character: ONLY if a key adult public figure is central; otherwise avoid\n"
        "- climax: dramatic reveal moment (not a portrait by default)\n"
        "\n"
        f"Era hint: {era_hint}\n"
    )


def _user_prompt(script_text: str, topic_hints: List[str], kinds: List[str]) -> str:
    hints = ", ".join(topic_hints) if topic_hints else "none"
    kinds_str = ", ".join(kinds)
    return (
        "Create exactly 4 scenes in this kind order: "
        f"{kinds_str}.\n"
        "Each scene must include 2-4 concrete visual elements tied to the topic.\n"
        f"Topic hints: {hints}\n"
        "\n"
        "Return JSON as:\n"
        "{\n"
        '  "scenes": [\n'
        '    {"idx": 1, "kind": "environment", "visual": "...", "negative_prompt": "..."},\n'
        "    ...\n"
        "  ]\n"
        "}\n"
        "\n"
        "SCRIPT (for reference only, do not copy sentences):\n"
        f"{script_text}\n"
    )


def _choose_provider(cfg: Optional[Dict[str, Any]], test_mode: bool) -> str:
    vc = _cfg(cfg)
    forced = str(vc.get("provider") or "auto").lower().strip()
    if forced in ("openai", "ollama"):
        return forced
    # auto
    if test_mode:
        return "ollama"
    # production prefers openai if available
    return "openai"


def _call_llm(cfg: Dict[str, Any], provider: str, system: str, user: str) -> str:
    llm = _llm_cfg(cfg)
    if provider == "openai":
        model = llm.get("openai_model", "gpt-4o-mini")
        return openai_generate(system=system, user=user, model=str(model), temperature=0.4)
    # ollama
    model = llm.get("ollama_model", "llama3.2:latest")
    url = llm.get("ollama_url", "http://127.0.0.1:11434")
    return ollama_generate(system=system, user=user, model=str(model), base_url=str(url), temperature=0.4)


def _parse_scenes(txt: str) -> List[VisualScene]:
    # try find first JSON object
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    blob = m.group(0) if m else txt
    data = json.loads(blob)
    raw = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError("invalid scenes json")
    scenes: List[VisualScene] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("idx") or (len(scenes) + 1))
        kind = str(item.get("kind") or "environment").lower().strip()
        visual = str(item.get("visual") or "").strip()
        neg = str(item.get("negative_prompt") or "").strip()
        if not visual:
            continue
        scenes.append(VisualScene(idx=idx, kind=kind, visual=visual, negative_prompt=neg))
    return scenes


def _postprocess(scenes: List[VisualScene], kinds_order: List[str]) -> List[VisualScene]:
    # enforce exactly 4 scenes and kinds order
    out: List[VisualScene] = []
    for i, kind in enumerate(kinds_order, start=1):
        # pick first matching, else fallback to ith
        chosen = None
        for sc in scenes:
            if sc.kind == kind and sc not in out:
                chosen = sc
                break
        if chosen is None:
            # fallback: reuse by index
            if i-1 < len(scenes):
                chosen = scenes[i-1]
            elif scenes:
                chosen = scenes[-1]
            else:
                chosen = VisualScene(idx=i, kind=kind, visual="moody documentary still, film grain, high contrast, mystery", negative_prompt="")
        chosen = VisualScene(idx=i, kind=kind, visual=chosen.visual, negative_prompt=chosen.negative_prompt)
        out.append(chosen)

    # avoid too many character prompts: only allow 1 character max
    char_count = sum(1 for s in out if s.kind == "character")
    if char_count > 1:
        first = True
        for s in out:
            if s.kind == "character":
                if first:
                    first = False
                else:
                    s.kind = "environment"

    # sanitize lengths
    for s in out:
        s.visual = sanitize_for_clip(s.visual, max_words=35)
        if s.negative_prompt:
            s.negative_prompt = sanitize_for_clip(s.negative_prompt, max_words=25)
    return out


def translate_scenes(script_text: str, cfg: Optional[Dict[str, Any]] = None, test_mode: bool = False) -> Tuple[List[VisualScene], str]:
    """Return (scenes, provider_used)."""
    cfg = cfg or {}
    vc = _cfg(cfg)
    era_hint = str(vc.get("era_hint") or "archival documentary, 1970s–2000s, Brazil/world").strip()
    kinds = list(vc.get("kinds_order") or _KIND_ORDER_DEFAULT)
    kinds = [str(k).lower().strip() for k in kinds][:4]
    if len(kinds) < 4:
        kinds = (_KIND_ORDER_DEFAULT)[:4]

    provider = _choose_provider(cfg, test_mode=test_mode)
    system = _system_prompt(era_hint=era_hint)
    hints = _extract_topic_hints(script_text, max_items=int(vc.get("max_topic_hints", 8)))
    user = _user_prompt(script_text=script_text, topic_hints=hints, kinds=kinds)

    # try provider, then fallback
    try:
        txt = _call_llm(cfg, provider=provider, system=system, user=user)
        scenes = _postprocess(_parse_scenes(txt), kinds_order=kinds)
        return scenes, provider
    except Exception:
        fb = "ollama" if provider == "openai" else "openai"
        try:
            txt = _call_llm(cfg, provider=fb, system=system, user=user)
            scenes = _postprocess(_parse_scenes(txt), kinds_order=kinds)
            return scenes, fb
        except Exception as e:
            # deterministic fallback
            fallback = [
                VisualScene(1, "environment", "Wide shot: foggy airport control room, radar screens glow, film grain, documentary lighting, tense silence", ""),
                VisualScene(2, "detail", "Macro: worn flight manifest papers, stamped passport, coffee stains, harsh desk lamp shadows, gritty texture", ""),
                VisualScene(3, "environment", "Aerial: empty ocean search grid, rescue ships as tiny silhouettes, overcast sky, muted palette, suspense", ""),
                VisualScene(4, "climax", "Dramatic reveal: pinboard of evidence, red thread lines, flashing news headline shapes, venetian blind shadows, high contrast", ""),
            ]
            return _postprocess(fallback, kinds_order=kinds), "fallback"


def to_json_list(scenes: List[VisualScene]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in scenes]

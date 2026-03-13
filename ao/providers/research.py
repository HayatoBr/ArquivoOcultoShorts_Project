from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import json
import random
import re
from pathlib import Path

import wikipedia
from ddgs import DDGS

try:
    import bs4
    import wikipedia.wikipedia as _wikipedia_module
    _wikipedia_module.BeautifulSoup = lambda html, *args, **kwargs: bs4.BeautifulSoup(html, features="lxml")
except Exception:
    pass

try:
    from ao.core.agents import dedupe_research_items
except Exception:
    dedupe_research_items = None


CATEGORY_QUERIES = [
    "desaparecimentos misteriosos wikipedia",
    "crimes não resolvidos wikipedia",
    "incidentes aéreos misteriosos wikipedia",
    "eventos históricos controversos wikipedia",
    "casos investigativos wikipedia",
    "fenômenos inexplicados wikipedia",
]

SEED_TOPICS = [
    "mistério do homem de Somerton",
    "incidente de Tunguska",
    "colônia perdida de Roanoke",
    "desaparecimento do voo MH370",
    "caso do passo Dyatlov",
    "criptograma de Beale",
    "sinal Wow",
    "desaparecimento de Percy Fawcett",
    "caso Elisa Lam",
    "desaparecimento do voo 19",
    "Incidente de Varginha",
]

INVESTIGATIVE_TERMS = {
    "controvérsia": 2.2, "controversia": 2.2, "controversy": 2.2,
    "paradeiro desconhecido": 3.2, "whereabouts unknown": 3.2,
    "evidência": 1.6, "evidencias": 1.6, "evidence": 1.6,
    "teoria": 1.4, "theory": 1.4, "hipótese": 1.3, "hipotese": 1.3, "hypothesis": 1.3,
    "oficial": 1.3, "official": 1.3,
    "mistério": 1.9, "misterio": 1.9, "mystery": 1.9,
    "investigação": 1.8, "investigacao": 1.8, "investigation": 1.8,
    "não resolvido": 2.8, "nao resolvido": 2.8, "unresolved": 2.8, "unsolved": 2.8,
    "desaparecimento": 2.2, "disappearance": 2.2, "desapareceu": 1.8,
    "testemunha": 1.1, "witness": 1.1,
    "documento": 1.0, "document": 1.0,
    "perícia": 1.3, "pericia": 1.3, "forensic": 1.3,
    "causa desconhecida": 2.4, "unknown cause": 2.4,
    "explicação oficial": 2.0, "official explanation": 2.0,
    "ovni": 1.8, "ufo": 1.8,
}

STRONG_MYSTERY_TERMS = [
    "mistério", "misterio", "mystery", "desaparecimento", "disappearance",
    "não resolvido", "nao resolvido", "unsolved", "unresolved", "controvers",
    "paradeiro desconhecido", "unknown", "conspiracy", "teoria", "hipótese",
    "ovni", "ufo", "explicação oficial", "official explanation",
]

BIOGRAPHY_BLOCK_TERMS = [
    "foi um navegador", "foi um explorador", "foi um rei", "foi uma rainha",
    "foi um cientista", "foi um político", "foi um militar", "foi um escritor",
    "biografia", "nascido em", "born in", "was a portuguese", "was a spanish",
    "foi um compositor", "foi um pintor", "foi um inventor",
]

ALLOW_BIOGRAPHY_IF = [
    "desapare", "morte mister", "morte suspeit", "assassinato não resolvido",
    "assassinato nao resolvido", "desaparecimento", "controvers", "unknown cause",
]

YOUTUBE_BLOCK_TERMS = [
    "massacre", "decapitation", "beheading", "torture", "sexual assault",
    "child abuse", "suicide method", "bomb making", "terrorist manifesto",
    "graphic gore", "necrophilia",
]

BAD_RESEARCH_TERMS = [
    "video game", "videogame", "game developer", "first person shooter", "fps game",
    "steam", "walkthrough", "gameplay", "pc game", "windows game", "review",
    "patch notes", "download now", "cheats", "persecutum informática", "persecutum informatica",
]

def _clean_text(text: str) -> str:
    text = (text or "").replace("\n", " ").replace("\r", " ").strip()
    return re.sub(r"\s+", " ", text)

def _slug(text: str) -> str:
    text = _clean_text(text).lower()
    text = re.sub(r"[^a-z0-9à-ÿ]+", "_", text)
    return text.strip("_")

def _topic_tokens(topic: str) -> set[str]:
    toks = re.findall(r"[a-z0-9à-ÿ]+", _clean_text(topic).lower())
    return {t for t in toks if len(t) >= 4}

_TOPIC_KEY_STOPWORDS = {"voo","flight","caso","incidente","desaparecimento","desaparecimento_do","misterio","mistério","o","a","de","do","da","das","dos","the","of","and","airlines","airline"}

def _topic_key(topic: str) -> str:
    tokens = [t for t in sorted(_topic_tokens(topic)) if t not in _TOPIC_KEY_STOPWORDS]
    return "_".join(tokens[:6])

def _topic_in_history(topic: str, history: set[str]) -> bool:
    slug = _slug(topic)
    key = _topic_key(topic)
    norm = _clean_text(topic).lower()
    compact = re.sub(r"[^a-z0-9à-ÿ]+", "", norm)
    candidates = {slug, key, norm, compact}
    tokens = _topic_tokens(topic)
    for item in history:
        if not item:
            continue
        item_norm = _clean_text(item).lower()
        item_compact = re.sub(r"[^a-z0-9à-ÿ]+", "", item_norm)
        item_tokens = set(re.findall(r"[a-z0-9à-ÿ]+", item_norm))
        if item in candidates or item_norm in candidates or item_compact in candidates:
            return True
        if key and item.startswith(key):
            return True
        if tokens and item_tokens and len(tokens & item_tokens) >= max(2, min(len(tokens), len(item_tokens))):
            return True
    return False

def _load_history(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        out: set[str] = set()
        if isinstance(data, list):
            for x in data:
                if isinstance(x, str):
                    value = _clean_text(x)
                    if value:
                        out.update({_slug(value), _topic_key(value), value.lower(), re.sub(r"[^a-z0-9à-ÿ]+", "", value.lower())})
                elif isinstance(x, dict):
                    for k in ("slug", "title", "key"):
                        value = _clean_text(str(x.get(k) or ""))
                        if value:
                            out.update({_slug(value), _topic_key(value), value.lower(), re.sub(r"[^a-z0-9à-ÿ]+", "", value.lower())})
        return {x for x in out if x}
    except Exception:
        return set()

def _save_history(path: Path, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    slug = _slug(title)
    key = _topic_key(title)
    title_norm = _clean_text(title)
    compact = re.sub(r"[^a-z0-9à-ÿ]+", "", title_norm.lower())
    existing = set()
    for x in data:
        if isinstance(x, str):
            existing.update({_slug(x), _topic_key(x), _clean_text(x).lower(), re.sub(r"[^a-z0-9à-ÿ]+", "", _clean_text(x).lower())})
        elif isinstance(x, dict):
            for k in ("slug","title","key"):
                v = _clean_text(str(x.get(k) or ""))
                if v:
                    existing.update({_slug(v), _topic_key(v), v.lower(), re.sub(r"[^a-z0-9à-ÿ]+", "", v.lower())})
    if not ({slug, key, title_norm.lower(), compact} & existing):
        data.append({"title": title_norm, "slug": slug, "key": key})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _topic_is_blocked(topic: str) -> bool:
    lowered = _clean_text(topic).lower()
    return any(term in lowered for term in YOUTUBE_BLOCK_TERMS)

def _is_list_page(title: str) -> bool:
    title_l = _clean_text(title).lower()
    return title_l.startswith("lista de ") or title_l.startswith("list of ") or "lista de " in title_l or "list of " in title_l

def _looks_like_generic_biography(title: str, text: str) -> bool:
    lowered = f"{title} {text}".lower()
    if _is_list_page(title):
        return False
    has_allow = any(k in lowered for k in ALLOW_BIOGRAPHY_IF)
    has_block = any(k in lowered for k in BIOGRAPHY_BLOCK_TERMS)
    return has_block and not has_allow

def _investigative_score(title: str, text: str) -> float:
    lowered = f"{title} {text}".lower()
    score = min(7.0, len(lowered) / 900.0)
    for term, weight in INVESTIGATIVE_TERMS.items():
        if term in lowered:
            score += weight
    if _is_list_page(title):
        score += 1.2
    if _looks_like_generic_biography(title, lowered):
        score -= 8.0
    if any(term in lowered for term in BAD_RESEARCH_TERMS):
        score -= 12.0
    if not any(term in lowered for term in STRONG_MYSTERY_TERMS):
        score -= 4.0
    return round(score, 2)

def _is_bad_research_result(topic: str, title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    if any(term in text for term in BAD_RESEARCH_TERMS):
        return True
    topic_toks = _topic_tokens(topic)
    if topic_toks:
        overlap = sum(1 for t in topic_toks if t in text)
        if overlap == 0 and not any(k in text for k in STRONG_MYSTERY_TERMS):
            return True
    return False

def _relevant_sections(content: str, topic: str = "") -> str:
    if not content:
        return ""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    kept: List[str] = []
    for p in paragraphs:
        low = p.lower()
        if any(bad in low for bad in BAD_RESEARCH_TERMS):
            continue
        if any(k in low for k in INVESTIGATIVE_TERMS.keys()):
            kept.append(p)
        elif len(kept) < 2 and len(p) > 180:
            kept.append(p)
        if len(" ".join(kept)) > 5500:
            break
    if not kept:
        kept = [p for p in paragraphs[:10] if not any(bad in p.lower() for bad in BAD_RESEARCH_TERMS)]
    return "\n\n".join(kept)[:6000]

def _wiki_page_content(topic: str) -> Tuple[str, str, str]:
    wikipedia.set_lang("pt")
    for auto in (False, True):
        try:
            page = wikipedia.page(topic, auto_suggest=auto)
            content = _relevant_sections(page.content or "", page.title)
            summary = _clean_text(page.summary or "")
            if any(bad in f"{page.title} {summary} {content}".lower() for bad in BAD_RESEARCH_TERMS):
                continue
            return page.title, summary, content
        except Exception:
            continue
    return topic, "", ""

def _ddgs_results(query: str, max_results: int, topic: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            for idx, item in enumerate(results or [], start=1):
                title = _clean_text(item.get("title") or "")
                body = _clean_text(item.get("body") or "")
                href = _clean_text(item.get("href") or "")
                if not (title or body):
                    continue
                if _is_bad_research_result(topic, title, body):
                    continue
                out.append({
                    "id": f"ddgs_{idx}",
                    "title": title,
                    "snippet": body,
                    "href": href,
                    "source": "ddgs",
                    "score": max(0.1, 1.0 - (idx * 0.08)),
                })
    except Exception:
        pass
    return out

def _wiki_chunks(title: str, content: str, topic: str) -> List[Dict[str, Any]]:
    if not content:
        return []
    chunks = [x.strip() for x in re.split(r"(?<=[\.!?])\s+", content) if x.strip()]
    out = []
    for i, x in enumerate(chunks[:40], start=1):
        if _is_bad_research_result(topic, title, x):
            continue
        out.append({
            "id": f"wiki_{i}",
            "title": title,
            "snippet": x,
            "source": "wikipedia",
            "score": max(0.2, 1.0 - (i * 0.03)),
        })
    return out

def _extract_list_candidates(title: str, content: str) -> List[str]:
    cands: List[str] = []
    if not _is_list_page(title):
        return cands
    lines = re.split(r"[\n\.;]", content)
    for line in lines:
        line = _clean_text(line)
        if not line:
            continue
        m = re.findall(r"([A-ZÁÉÍÓÚÂÊÔÃÕ][\wÁÉÍÓÚÂÊÔÃÕç'\-]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÁÉÍÓÚÂÊÔÃÕç'\-]+){1,4})", line)
        for name in m:
            if len(name.split()) >= 2 and len(name) < 70:
                cands.append(name)
    out: List[str] = []
    seen = set()
    for c in cands:
        k = c.lower()
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out[:25]

def _safe_wikipedia_search(query: str, results: int = 12) -> List[str]:
    """
    Busca opcional na Wikipedia com tolerância a falhas.
    Desativada por padrão porque a lib wikipedia pode travar em alguns ambientes Windows.
    """
    try:
        return list(wikipedia.search(query, results=results) or [])
    except Exception:
        return []


def _extract_topic_candidates(cfg: Dict[str, Any], channel_desc: str) -> List[str]:
    candidates: List[str] = []
    seen = set()

    def add(x: str):
        x = _clean_text(x)
        if not x or _topic_is_blocked(x):
            return
        key = x.lower()
        if key not in seen:
            seen.add(key)
            candidates.append(x)

    for seed in SEED_TOPICS:
        add(seed)

    research_cfg = cfg.get("research", {}) or {}

    # IMPORTANTE:
    # A busca por categorias via wikipedia.search pode travar em alguns ambientes
    # Windows/venv. Por segurança, agora ela fica DESLIGADA por padrão.
    if research_cfg.get("use_wikipedia_search", False):
        for query in CATEGORY_QUERIES:
            for item in _safe_wikipedia_search(query, results=12):
                add(item)

    if research_cfg.get("use_ddgs", True):
        for query in CATEGORY_QUERIES[:4]:
            for item in _ddgs_results(query, max_results=8, topic=query):
                add(item.get("title") or "")

    return candidates[:80]

def _choose_topic(cfg: Dict[str, Any], channel_desc: str, history_path: Path, logger) -> str:
    history = _load_history(history_path)
    candidates = _extract_topic_candidates(cfg, channel_desc)
    scored: List[Tuple[float, str]] = []
    for cand in candidates:
        slug = _slug(cand)
        if _topic_in_history(cand, history):
            continue
        title, summary, content = _wiki_page_content(cand)
        if not content and not summary:
            continue
        text = f"{summary} {content[:3000]}"
        if _is_list_page(title):
            for sub in _extract_list_candidates(title, content):
                sslug = _slug(sub)
                if _topic_in_history(sub, history):
                    continue
                stitle, ssummary, scontent = _wiki_page_content(sub)
                stext = f"{ssummary} {scontent[:2500]}"
                score = _investigative_score(stitle, stext)
                if score >= float(cfg.get("research", {}).get("min_investigative_score", 5.0)) and not _looks_like_generic_biography(stitle, stext):
                    scored.append((score, stitle))
            continue
        score = _investigative_score(title, text)
        if score >= float(cfg.get("research", {}).get("min_investigative_score", 5.0)) and not _looks_like_generic_biography(title, text):
            scored.append((score, title))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    for seed in SEED_TOPICS:
        if not _topic_in_history(seed, history):
            return seed
    return random.choice(SEED_TOPICS)

def _format_dump(topic: str, wiki_summary: str, wiki_content: str, items: Iterable[Dict[str, Any]], investigative_score: float) -> str:
    blocks = []
    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        href = item.get("href", "")
        block = f"TÍTULO: {title}\nRESUMO: {snippet}"
        if href:
            block += f"\nLINK: {href}"
        blocks.append(block)
    return (
        f"TEMA: {topic}\n"
        f"INVESTIGATIVE_SCORE: {investigative_score}\n\n"
        f"WIKIPEDIA_SUMMARY:\n{wiki_summary or '[sem resumo]'}\n\n"
        f"WIKIPEDIA_CONTENT:\n{wiki_content or '[sem conteúdo]'}\n\n"
        f"RESULTADOS_COMPLEMENTARES:\n" + ("\n\n".join(blocks) if blocks else "[sem resultados]")
    )

def build_research_packet(cfg: Dict[str, Any], topic_hint: str, logger, project_root=None) -> Dict[str, Any]:
    history_path = Path(project_root or ".") / "output" / "topic_history.json"
    channel_desc = str((cfg.get("channel") or {}).get("description") or "")
    topic = _clean_text(topic_hint)
    if not topic:
        topic = _choose_topic(cfg, channel_desc, history_path, logger)
    title, wiki_summary, wiki_content = _wiki_page_content(topic)
    ddgs_items = _ddgs_results(title, max_results=int(cfg.get("research", {}).get("ddgs_results", 8) or 8), topic=title)
    wiki_items = _wiki_chunks(title, wiki_content, title)
    research_items = wiki_items + ddgs_items
    if dedupe_research_items is not None:
        try:
            research_items = dedupe_research_items(research_items)
        except Exception:
            pass
    research_items = [x for x in research_items if not _is_bad_research_result(title, x.get("title",""), x.get("snippet",""))][:28]
    investigative_score = _investigative_score(title, f"{wiki_summary} {wiki_content[:3000]}")
    structured_text = " ".join([
        wiki_summary or "",
        wiki_content[:5000] if wiki_content else "",
        " ".join([f"{x.get('title','')}. {x.get('snippet','')}" for x in research_items[:18]])
    ]).strip()
    research_dump = build_clean_research_dump(structured_text)
    _save_history(history_path, title)
    logger.info(
        "Pesquisa pronta para tema: %s | wiki=%s | itens=%s | score=%s | history=%s",
        title, bool(wiki_summary or wiki_content), len(research_items), investigative_score, history_path,
    )
    return {
        "topic": title,
        "wiki_summary": wiki_summary,
        "wiki_content": wiki_content,
        "research_items": research_items,
        "research_dump": research_dump,
        "investigative_score": investigative_score,
        "history_path": str(history_path),
    }



def _build_structured_blocks(text: str) -> dict:
    text = text or ""
    sentences = re.split(r'(?<=[\.\!\?])\s+', text)
    buckets = {
        "contexto": [],
        "evento": [],
        "anomalias": [],
        "buscas": [],
        "evidencias": [],
        "sem_resposta": []
    }

    for s in sentences:
        low = s.lower()
        if any(k in low for k in ["desaparec", "incidente", "aconteceu", "evento", "ocorreu"]):
            buckets["evento"].append(s)
        elif any(k in low for k in ["investiga", "busca", "resgate", "opera", "equipes"]):
            buckets["buscas"].append(s)
        elif any(k in low for k in ["evid", "destro", "document", "registro", "radar"]):
            buckets["evidencias"].append(s)
        elif any(k in low for k in ["mistério", "desconhecid", "sem explicação", "não se sabe"]):
            buckets["sem_resposta"].append(s)
        elif any(k in low for k in ["estranho", "anomalia", "inexplic", "incomum"]):
            buckets["anomalias"].append(s)
        else:
            buckets["contexto"].append(s)

    for k in buckets:
        buckets[k] = buckets[k][:4]

    return buckets


# sanitized research export

def build_clean_research_dump(raw_text: str) -> str:
    blocks = _build_structured_blocks(raw_text)
    parts = []
    for k,v in blocks.items():
        if v:
            parts.append(k.upper()+": " + " ".join(v))
    return " ".join(parts)

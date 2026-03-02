from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.script.wikipedia_source import WikiDoc, fetch_extract, search_titles


@dataclass
class SourceItem:
    title: str
    url: str
    extract: str


def build_wiki_dossier(cfg: Optional[Dict[str, Any]] = None, *, lang: str = "pt", seed_title: Optional[str] = None, max_items: int = 3) -> List[SourceItem]:
    """Monta um mini-dossiê a partir da Wikipédia (1 item principal + 0-2 relacionados).

    Objetivo:
      - dar mais contexto ao roteiro quando Gemini falhar
      - reduzir "script poluído" (extratos curtos e organizados)
    """
    max_items = max(1, min(int(max_items), 5))

    # Se já tiver um título sugerido, tenta usar; senão busca.
    title = (seed_title or "").strip()
    if not title:
        # usa a mesma lógica do get_wiki_doc_for_channel, mas aqui só precisamos de um título base
        queries_pt = [
            "caso não resolvido",
            "desaparecimento misterioso",
            "mistério histórico",
            "evento histórico controverso",
            "investigação criminal famosa",
        ]
        queries_en = [
            "unsolved case",
            "mysterious disappearance",
            "historical mystery",
            "controversial historical event",
            "famous criminal investigation",
        ]
        q = random.choice(queries_en if (lang or "pt").lower().startswith("en") else queries_pt)
        titles = search_titles(q, cfg=cfg, limit=8, lang=lang)
        title = titles[0] if titles else ""

    items: List[SourceItem] = []
    if title:
        main = fetch_extract(title, cfg=cfg, lang=lang, sentences=10)
        if main and main.extract:
            extract_txt = (main.extract or "").strip()
            if len(extract_txt) > 1400:
                extract_txt = extract_txt[:1400].rsplit(' ',1)[0] + '...'
            items.append(SourceItem(title=main.title or title, url=main.url or "", extract=extract_txt))

    # relacionados: tenta buscar mais títulos com palavras-chave do título principal
    if len(items) < max_items:
        key = (items[0].title if items else title) or ""
        key_terms = [t for t in key.replace("(", " ").replace(")", " ").split() if len(t) > 4][:3]
        if key_terms:
            q2 = " ".join(key_terms)
            rel = search_titles(q2, cfg=cfg, limit=6, lang=lang)
            for t in rel:
                if len(items) >= max_items:
                    break
                if t.lower() == title.lower():
                    continue
                doc = fetch_extract(t, cfg=cfg, lang=lang, sentences=7)
                if doc and doc.extract:
                    extract_txt = (doc.extract or "").strip()
                if len(extract_txt) > 900:
                    extract_txt = extract_txt[:900].rsplit(' ',1)[0] + '...'
                items.append(SourceItem(title=doc.title or t, url=doc.url or "", extract=extract_txt))

    return items


def format_dossier(items: List[SourceItem]) -> str:
    """Texto compacto para alimentar LLMs."""
    if not items:
        return ""
    parts: List[str] = []
    for i, it in enumerate(items, 1):
        parts.append(f"[{i}] {it.title}\n{(it.extract or '').strip()}")
    return "\n\n".join(parts).strip()

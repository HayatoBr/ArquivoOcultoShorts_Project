from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str


def ddg_search(query: str, max_results: int = 5, *, safesearch: str = "moderate") -> Optional[List[WebResult]]:
    """Busca via DuckDuckGo (ddgs). Retorna None se o pacote não estiver instalado."""
    q = (query or "").strip()
    if not q:
        return None
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        return None

    out: List[WebResult] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=int(max_results), safesearch=safesearch):
                title = str(r.get("title") or "").strip()
                url = str(r.get("href") or r.get("url") or "").strip()
                snippet = str(r.get("body") or r.get("snippet") or "").strip()
                if title and url:
                    out.append(WebResult(title=title, url=url, snippet=snippet))
        return out or None
    except Exception:
        return None

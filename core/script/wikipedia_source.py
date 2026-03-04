import time
import random
from typing import Optional, Dict, Any, List

import requests
from urllib.parse import quote as _quote

DEFAULT_API_PT = "https://pt.wikipedia.org/w/api.php"
DEFAULT_API_EN = "https://en.wikipedia.org/w/api.php"


class WikiDoc(str):
    """Compatibilidade com o script_generator.

    O pipeline espera:
      - doc.title  (str)
      - doc.url    (str)
      - doc.extract (str)

    Ao mesmo tempo, em alguns lugares o doc pode ser tratado como string.
    Por isso, WikiDoc é uma subclasse de `str` e também expõe atributos.
    """

    def __new__(cls, extract: str, title: str = "", url: str = ""):
        obj = str.__new__(cls, extract or "")
        obj.title = title or ""
        obj.url = url or ""
        obj.extract = extract or ""
        return obj


def _user_agent(cfg: Optional[Dict[str, Any]] = None) -> str:
    ua = None
    if cfg:
        ua = (
            (cfg.get("script", {}) or {}).get("wikipedia_user_agent")
            or cfg.get("wikipedia_user_agent")
            or ((cfg.get("wikipedia", {}) or {}).get("user_agent"))
        )
    if not ua:
        ua = "ArquivoOcultoShorts/1.0 (contact: local-user; purpose: YouTube shorts generation)"
    return ua


def _api_url(lang: str) -> str:
    lang = (lang or "pt").lower().strip()
    if lang.startswith("en"):
        return DEFAULT_API_EN
    return DEFAULT_API_PT


def _wiki_page_url(title: str, lang: str) -> str:
    lang = (lang or "pt").lower().strip()
    domain = "en.wikipedia.org" if lang.startswith("en") else "pt.wikipedia.org"
    safe = (title or "").replace(" ", "_")
    return f"https://{domain}/wiki/{_quote(safe)}"


def _session(cfg: Optional[Dict[str, Any]] = None) -> requests.Session:
    s = requests.Session()
    ua = _user_agent(cfg)
    s.headers.update({
        "User-Agent": ua,
        "Api-User-Agent": ua,
        "Accept": "application/json",
    })
    return s


def _request_json(sess: requests.Session, url: str, params: Dict[str, Any], retries: int = 3, backoff: float = 1.3) -> Dict[str, Any]:
    last_err = None
    for i in range(retries):
        try:
            r = sess.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep((backoff ** i) + random.random() * 0.3)
    raise last_err


def search_titles(query: str, cfg: Optional[Dict[str, Any]] = None, limit: int = 5, lang: str = "pt") -> List[str]:
    sess = _session(cfg)
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": int(limit),
        "format": "json",
        "utf8": 1,
    }
    data = _request_json(sess, _api_url(lang), params)
    results = ((data.get("query") or {}).get("search") or [])
    return [r.get("title") for r in results if r.get("title")]


def fetch_extract(title: str, cfg: Optional[Dict[str, Any]] = None, sentences: int = 8, lang: str = "pt") -> str:
    sess = _session(cfg)
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "exintro": 1,
        "titles": title,
        "format": "json",
        "utf8": 1,
    }
    data = _request_json(sess, _api_url(lang), params)
    pages = ((data.get("query") or {}).get("pages") or {})
    text = ""
    for _, page in pages.items():
        text = page.get("extract") or ""
        break
    if not text:
        return ""
    if sentences and sentences > 0:
        parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
        text = ". ".join(parts[:sentences]).strip()
        if text and not text.endswith("."):
            text += "."
    return text


def get_wiki_doc_for_channel(cfg: Optional[Dict[str, Any]] = None, lang: str = "pt", **kwargs) -> WikiDoc:
    """Retorna um documento base para alimentar o roteirista.

    Objetivo: puxar temas "investigativos", mas seguros para Shorts (monetização).
    Faz um filtro best-effort por título + extrato para evitar temas sensíveis.
    """
    from core.agents.safety_gate import scan_text, should_block

    # Prefer "mistérios" e "arquivos" (evitar crimes pesados/menores).
    queries_pt = [
        "mistério histórico",
        "documentos secretos história",
        "projeto secreto governo",
        "fenômeno inexplicável",
        "desaparecimento de navio avião mistério",
        "tesouro perdido lenda",
        "fraude histórica famosa",
        "golpe famoso história",
        "espionagem caso histórico",
        "código cifrado enigma",
        "incidente misterioso arquivo",
        "cidade perdida arqueologia",
    ]
    queries_en = [
        "historical mystery",
        "declassified secret project",
        "unsolved historical enigma",
        "unexplained phenomenon",
        "mysterious ship disappearance",
        "lost treasure legend",
        "famous historical fraud",
        "classic heist mystery",
        "espionage historical case",
        "cipher code mystery",
        "declassified incident",
        "lost city archaeology",
    ]
    queries = queries_en if (lang or "pt").lower().startswith("en") else queries_pt

    # Hard blacklist for titles (fast filter)
    blacklist = [
        "abuso", "abuso sexual", "estupro", "pedof", "porn", "pornografia", "criança", "infantil",
        "necrof", "decapit", "desmembr", "tortur", "massacre",
    ]

    # Try multiple picks until we find a safe extract
    tries = 0
    max_tries = 12
    sess_titles: list[str] = []
    while tries < max_tries:
        tries += 1
        pick = random.choice(queries)
        titles = search_titles(pick, cfg=cfg, limit=10, lang=lang)
        if not titles:
            continue
        sess_titles = titles

        # Filter titles
        filtered = []
        for t in titles:
            tl = (t or "").lower()
            if any(b in tl for b in blacklist):
                continue
            filtered.append(t)

        # If everything filtered, try again with another query
        if not filtered:
            continue

        # Try top few candidates
        for title in filtered[:6]:
            extract = fetch_extract(title, cfg=cfg, sentences=10, lang=lang).strip()
            url = _wiki_page_url(title, lang=lang) if title else ""
            doc_txt = f"Título: {title}\n{extract}".strip()
            findings = scan_text(cfg, doc_txt)
            if should_block(cfg, findings):
                continue
            # If warnings exist (crime hints) we still accept, but script prompt already forbids gore.
            return WikiDoc(doc_txt, title=title, url=url)

    # Fallback: first available title, no filtering (still better than empty)
    if sess_titles:
        title = sess_titles[0]
        extract = fetch_extract(title, cfg=cfg, sentences=10, lang=lang).strip()
        url = _wiki_page_url(title, lang=lang) if title else ""
        return WikiDoc(f"Título: {title}\n{extract}".strip(), title=title, url=url)

    return WikiDoc("", title="", url="")

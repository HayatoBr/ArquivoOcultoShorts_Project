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
    """Retorna um documento base para alimentar o roteirista (Gemini/Ollama).

    IMPORTANTE:
    - Para evitar "script poluído" no fallback (quando Gemini/Ollama não estiverem disponíveis),
      retornamos APENAS 1 título + extrato.
    - Também evitamos termos altamente sensíveis (ex.: abuso sexual envolvendo menores) já na seleção.
    """
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
    queries = queries_en if (lang or "pt").lower().startswith("en") else queries_pt

    blacklist = [
        "abuso", "abuso sexual", "pedof", "porn", "estupro", "criança", "infantil",
    ]

    pick = random.choice(queries)
    titles = search_titles(pick, cfg=cfg, limit=8, lang=lang)
    if not titles:
        return WikiDoc("", title="", url="")

    # Filter obviously sensitive titles (best-effort; policy agent still enforces later)
    filtered = []
    for t in titles:
        tl = (t or "").lower()
        if any(b in tl for b in blacklist):
            continue
        filtered.append(t)
    if not filtered:
        filtered = titles  # if everything filtered, fall back to original list

    title = filtered[0]
    extract = fetch_extract(title, cfg=cfg, sentences=10, lang=lang).strip()
    url = _wiki_page_url(title, lang=lang) if title else ""
    return WikiDoc(f"Título: {title}\n{extract}".strip(), title=title, url=url)

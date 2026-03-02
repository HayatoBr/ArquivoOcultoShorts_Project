from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass
class LLMCallResult:
    text: Optional[str]
    provider: str
    model: str
    error: Optional[str] = None


def _get_llm_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("llm", {}) or {}


def call_gemini(prompt: str, cfg: Optional[Dict[str, Any]] = None) -> LLMCallResult:
    llm_cfg = _get_llm_cfg(cfg)
    api_key = os.environ.get("GEMINI_API_KEY") or llm_cfg.get("gemini_api_key") or ""
    model = os.environ.get("GEMINI_MODEL") or llm_cfg.get("gemini_model") or "gemini-2.0-flash"
    try:
        from core.script.llm_gemini import gemini_generate
        txt = gemini_generate(prompt, api_key=str(api_key), model=str(model)) if api_key else None
        return LLMCallResult(text=txt, provider="gemini", model=str(model), error=None if txt else "empty_or_failed")
    except Exception as e:
        return LLMCallResult(text=None, provider="gemini", model=str(model), error=str(e))


def call_ollama(prompt: str, cfg: Optional[Dict[str, Any]] = None) -> LLMCallResult:
    llm_cfg = _get_llm_cfg(cfg)
    base_url = os.environ.get("OLLAMA_URL") or llm_cfg.get("ollama_url") or "http://127.0.0.1:11434"
    model = os.environ.get("OLLAMA_MODEL") or llm_cfg.get("ollama_model") or "llama3.2:latest"
    timeout = int(os.environ.get("OLLAMA_TIMEOUT") or llm_cfg.get("ollama_timeout") or 120)
    try:
        from core.script.llm_ollama import ollama_generate
        url = str(base_url).rstrip("/") + "/api/generate"
        txt = ollama_generate(prompt, model=str(model), url=url, timeout=timeout)
        return LLMCallResult(text=txt, provider="ollama", model=str(model), error=None if txt else "empty_or_failed")
    except Exception as e:
        return LLMCallResult(text=None, provider="ollama", model=str(model), error=str(e))


def call_best(prompt: str, cfg: Optional[Dict[str, Any]] = None) -> LLMCallResult:
    """Gemini principal -> Ollama fallback."""
    g = call_gemini(prompt, cfg)
    if g.text:
        return g
    o = call_ollama(prompt, cfg)
    if o.text:
        return o
    return LLMCallResult(text=None, provider="none", model="", error="no_provider_available")


def call_best_with_wiki_fallback(prompt: str, wiki_fallback: str, cfg: Optional[Dict[str, Any]] = None) -> LLMCallResult:
    res = call_best(prompt, cfg)
    if res.text:
        return res
    # last resort
    return LLMCallResult(text=wiki_fallback or "", provider="wikipedia", model="", error=None)

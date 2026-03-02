from __future__ import annotations
from typing import Optional
import requests

def ollama_generate(prompt: str, model: str = "llama3.2:latest", url: str = "http://127.0.0.1:11434/api/generate", timeout: int = 120) -> Optional[str]:
    try:
        payload = {"model": model, "prompt": prompt, "stream": False}
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json() or {}
        txt = data.get("response")
        return str(txt).strip() if txt else None
    except Exception:
        return None


class OllamaLLM:
    """Wrapper simples para Ollama (/api/generate)."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama3.2:latest", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = int(timeout)

    def generate(self, prompt: str) -> str:
        url = self.base_url + "/api/generate"
        out = ollama_generate(prompt, model=self.model, url=url, timeout=self.timeout)
        return out or ""

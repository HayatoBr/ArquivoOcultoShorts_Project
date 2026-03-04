from __future__ import annotations

from typing import Optional
import os
import requests


def ollama_generate(
    prompt: Optional[str] = None,
    *,
    system: Optional[str] = None,
    user: Optional[str] = None,
    model: str = "llama3.2:latest",
    # legacy params:
    url: Optional[str] = None,
    timeout: int = 120,
    # new params:
    base_url: Optional[str] = None,
    temperature: float = 0.7,
) -> Optional[str]:
    """Gera texto via Ollama.

    Compatibilidade:
    - modo antigo (/api/generate): ollama_generate(prompt="...", url="http://127.0.0.1:11434/api/generate")
    - modo novo (/api/chat): ollama_generate(system="...", user="...", base_url="http://127.0.0.1:11434")

    Observação: /api/chat costuma ser mais estável para prompts com instruções + JSON.
    """
    if user is None and prompt is not None:
        user = prompt

    if not user:
        return None

    # prefer /api/chat when system is provided or base_url is provided
    if base_url or system:
        bu = (base_url or "http://127.0.0.1:11434").rstrip("/")
        chat_url = bu + "/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
        try:
            r = requests.post(chat_url, json=payload, timeout=int(timeout))
            r.raise_for_status()
            data = r.json() or {}
            msg = (data.get("message") or {})
            txt = msg.get("content")
            return str(txt).strip() if txt else None
        except Exception as e:
            if os.environ.get("AO_DEBUG") == "1":
                print("[Ollama/chat] erro:", e)
            # fall through to /api/generate as last resort

    gen_url = url or ((base_url or "http://127.0.0.1:11434").rstrip("/") + "/api/generate")
    try:
        payload = {"model": model, "prompt": user, "stream": False, "options": {"temperature": float(temperature)}}
        r = requests.post(gen_url, json=payload, timeout=int(timeout))
        r.raise_for_status()
        data = r.json() or {}
        txt = data.get("response")
        return str(txt).strip() if txt else None
    except Exception as e:
        if os.environ.get("AO_DEBUG") == "1":
            print("[Ollama/generate] erro:", e)
        return None


class OllamaLLM:
    """Wrapper simples para Ollama."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama3.2:latest", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = int(timeout)

    def generate(self, prompt: str) -> str:
        out = ollama_generate(prompt, model=self.model, base_url=self.base_url, timeout=self.timeout)
        return out or ""

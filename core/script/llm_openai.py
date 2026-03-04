import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def openai_generate(
    prompt: Optional[str] = None,
    *,
    system: Optional[str] = None,
    user: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> Optional[str]:
    """Gera texto via OpenAI Chat Completions (SDK oficial).

    Compatibilidade:
    - modo antigo: openai_generate(prompt="...")
    - modo novo: openai_generate(system="...", user="...")

    Requer OPENAI_API_KEY no ambiente.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None

    # Back-compat: if prompt provided, treat as user message.
    if user is None and prompt is not None:
        user = prompt

    if not user:
        return None

    if system is None:
        system = "Você é um assistente profissional e objetivo. Responda com clareza."

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or None
    except Exception as e:
        if os.environ.get("AO_DEBUG") == "1":
            print("[OpenAI] erro:", e)
        return None

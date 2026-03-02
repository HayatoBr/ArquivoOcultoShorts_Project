from __future__ import annotations

from typing import Optional
import os
import sys

def _normalize_model_name(model: str) -> str:
    m = (model or "").strip()
    if not m:
        return "gemini-2.0-flash"
    # SDK often prints/list models as "models/<id>", but generate_content expects "<id>"
    if m.startswith("models/"):
        m = m.split("/", 1)[1]
    return m

def gemini_generate(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> Optional[str]:
    """Generate text using Google Gemini via the new `google-genai` SDK.

    Returns None on failure to allow graceful fallback (Ollama/Wikipedia).
    Set AO_DEBUG=1 to print the underlying exception.
    """
    try:
        from google import genai  # type: ignore
    except Exception as e:
        if os.environ.get("AO_DEBUG") == "1":
            print(f"[Gemini] SDK import failed: {e}", file=sys.stderr)
        return None

    mname = _normalize_model_name(model)
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=mname, contents=prompt)
        txt = getattr(resp, "text", None)
        if txt:
            return str(txt).strip()

        # Fallback extraction (in case response shape changes)
        cands = getattr(resp, "candidates", None) or []
        for c in cands:
            content = getattr(c, "content", None)
            parts = getattr(content, "parts", None) or []
            for p in parts:
                t = getattr(p, "text", None)
                if t:
                    return str(t).strip()
        return None
    except Exception as e:
        if os.environ.get("AO_DEBUG") == "1":
            print(f"[Gemini] generate_content failed ({mname}): {e}", file=sys.stderr)
        return None

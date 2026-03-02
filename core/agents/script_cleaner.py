from __future__ import annotations

from typing import Any, Dict, Tuple

# keep actual implementation in script_cleaner_agent.py
from .script_cleaner_agent import clean_script_text as _clean_impl

def clean_script_text(text: str, cfg: Dict[str, Any] | None = None) -> Tuple[str, Dict[str, Any]]:
    """
    Compat wrapper.

    The implementation returns a dict with a 'text' field.
    The pipeline expects: (cleaned_text, report_dict)
    """
    rep = _clean_impl(text, cfg)
    cleaned = (rep or {}).get("text", "") if isinstance(rep, dict) else ""
    if not isinstance(rep, dict):
        rep = {"changed": False, "text": cleaned}
    return cleaned, rep

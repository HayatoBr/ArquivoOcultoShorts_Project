from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CharacterAnchor:
    """Stable character description reused across scenes to improve consistency."""
    description: str


_NAME_RE = re.compile(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)\b", re.UNICODE)


def build_character_anchor(script_text: str) -> CharacterAnchor:
    t = (script_text or "").strip()

    # Try to guess a name (first proper-looking token). If none, use generic.
    name = None
    for m in _NAME_RE.finditer(t[:800]):
        cand = m.group(1)
        # avoid month names/common words
        if cand.lower() in {"domingo","segunda","terça","terca","quarta","quinta","sexta","sábado","sabado","janeiro","fevereiro","março","marco","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"}:
            continue
        name = cand
        break

    # Generic but consistent cinematic anchor
    if name:
        desc = f"{name}, close-up cinematic portrait, shoulders up, realistic face, consistent identity"
    else:
        desc = "close-up cinematic portrait, shoulders up, realistic face, consistent identity"

    # Add safety: avoid hands
    desc += ", hands out of frame"
    return CharacterAnchor(description=desc)

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


@dataclass
class VisualPromptResult:
    prompt: str
    negative_prompt: str
    token_count: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _truncate_with_tokenizer(tokenizer, text: str, max_tokens: int) -> Tuple[str, int]:
    if tokenizer is None:
        words = (text or "").split()
        approx = min(len(words), max_tokens)
        return " ".join(words[:approx]), approx

    enc = tokenizer(
        text,
        truncation=True,
        max_length=max_tokens + 2,
        return_tensors=None,
        add_special_tokens=True,
    )
    ids = enc.get("input_ids")
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    special = set(getattr(tokenizer, "all_special_ids", []))
    ids_wo = [i for i in ids if i not in special]
    if len(ids_wo) > max_tokens:
        ids_wo = ids_wo[:max_tokens]
    txt = tokenizer.decode(ids_wo, skip_special_tokens=True)
    return _clean(txt), len(ids_wo)


class PromptVisualAgent:
    def __init__(
        self,
        style_base: str,
        negative_base: str,
        *,
        max_tokens: int = 70,
        global_profile: str = "",
        global_negative: str = "",
    ):
        self.style_base = _clean(style_base)
        self.negative_base = _clean(negative_base)
        self.global_profile = _clean(global_profile)
        self.global_negative = _clean(global_negative)
        self.max_tokens = int(max_tokens)

    def build(
        self,
        scene_text: str,
        *,
        tokenizer=None,
        kind: str = "auto",
        character_anchor: str = "",
        character_reinforce: str = "",
        extra_positive: str = "",
        extra_negative: str = "",
    ) -> VisualPromptResult:
        scene_text = _clean(scene_text)

        k = (kind or "auto").lower()
        if k == "auto":
            if re.search(r"\b(rosto|testemunha|investigador|suspeito|ela|ele)\b", scene_text, flags=re.I):
                k = "character"
            elif re.search(r"\b(local|rua|casa|floresta|noite|cidade|interior)\b", scene_text, flags=re.I):
                k = "environment"
            else:
                k = "detail"

        anchor = _clean(character_anchor) if k == "character" else ""
        reinforce = _clean(character_reinforce) if k == "character" else ""

        if k == "character":
            guidance = "close-up cinematográfico, rosto em foco, sem mãos"
        elif k == "environment":
            guidance = "ambiente cinematográfico, plano geral, atmosfera investigativa"
        elif k == "detail":
            guidance = "detalhe cinematográfico, evidência, macro"
        else:
            guidance = "cena cinematográfica investigativa"

        pieces = [
            self.style_base,
            self.global_profile,
            guidance,
            anchor,
            reinforce,
            extra_positive,
            scene_text,
        ]
        prompt = _clean(", ".join([p for p in pieces if p]))
        prompt, tok = _truncate_with_tokenizer(tokenizer, prompt, self.max_tokens)

        neg_parts = [self.negative_base, self.global_negative, extra_negative]
        neg = _clean(", ".join([p for p in neg_parts if p]))
        return VisualPromptResult(
            prompt=prompt,
            negative_prompt=neg,
            token_count=tok,
            meta={"kind": k, "max_tokens": self.max_tokens},
        )

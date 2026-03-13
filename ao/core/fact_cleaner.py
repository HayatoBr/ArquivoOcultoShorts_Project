from __future__ import annotations

import json
import re
from typing import Any, Dict, List

try:
    from ao.providers.ollama import _llm_cfg, _request
except Exception:
    _llm_cfg = None
    _request = None


def _clean_line(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.strip(' ,;:-')
    if text and text[-1] not in '.!?':
        text += '.'
    return text


def _shorten(text: str, max_words: int = 14) -> str:
    words = (text or '').split()
    if len(words) <= max_words:
        return _clean_line(' '.join(words))
    short = ' '.join(words[:max_words]).rstrip(',;:')
    return _clean_line(short)


def _heuristic_clean(extracted: Dict[str, Any]) -> Dict[str, Any]:
    facts = [_shorten(x) for x in (extracted.get('facts') or []) if x]
    mysteries = [_shorten(x, 12) for x in (extracted.get('mysteries') or []) if x]
    story_facts: List[str] = []
    for line in facts:
        low = line.lower()
        if any(bad in low for bad in ['wikipedia', 'download', 'steam', 'game', 'software', 'review', 'loja']):
            continue
        story_facts.append(line)
    if mysteries:
        for item in mysteries[:2]:
            if item not in story_facts:
                story_facts.append(item)
    seen = set()
    deduped = []
    for line in story_facts:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(line)
    return {
        'story_facts': deduped[:8],
        'mystery_hooks': mysteries[:3],
    }


def clean_story_facts(cfg: Dict[str, Any], extracted: Dict[str, Any], logger) -> Dict[str, Any]:
    if _request is None or _llm_cfg is None:
        logger.info('[FACT_CLEANER] Ollama indisponível; usando limpeza heurística')
        return _heuristic_clean(extracted)

    llm_cfg = _llm_cfg(cfg)
    model = llm_cfg.get('fact_cleaner_model') or llm_cfg.get('local_model') or llm_cfg.get('ollama_model') or 'qwen2.5:7b-instruct-q4_K_M'
    timeout = int(llm_cfg.get('timeout_seconds') or llm_cfg.get('ollama_timeout_sec') or 180)
    temperature = float(llm_cfg.get('fact_cleaner_temperature', 0.25))
    top_p = float(llm_cfg.get('fact_cleaner_top_p', 0.74))
    num_predict = int(llm_cfg.get('fact_cleaner_num_predict', 260))

    prompt = f"""
Você é um roteirista investigativo especializado em condensar fatos.

Transforme os fatos abaixo em pontos narrativos curtos e limpos para locução.

REGRAS:
- responda SOMENTE em JSON válido
- português do Brasil
- máximo 8 frases em story_facts
- cada frase com até 14 palavras
- tom documental e investigativo
- sem linguagem enciclopédica
- sem copiar trechos brutos
- sem inventar fatos novos
- sem inglês
- pode incluir até 3 mystery_hooks curtos

Formato exato:
{{
  "story_facts": ["..."],
  "mystery_hooks": ["..."]
}}

FATOS EXTRAÍDOS:
{json.dumps(extracted, ensure_ascii=False, indent=2)}
""".strip()

    try:
        data = _request(
            cfg,
            {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'format': 'json',
                'options': {
                    'temperature': temperature,
                    'top_p': top_p,
                    'num_predict': num_predict,
                    'repeat_penalty': 1.08,
                },
            },
            timeout,
        )
        raw = (data.get('response') or '').strip()
        parsed = json.loads(raw)
        story_facts = [_shorten(x) for x in (parsed.get('story_facts') or []) if x]
        mystery_hooks = [_shorten(x, 10) for x in (parsed.get('mystery_hooks') or []) if x]
        if not story_facts:
            raise ValueError('JSON sem story_facts')
        return {
            'story_facts': story_facts[:8],
            'mystery_hooks': mystery_hooks[:3],
        }
    except Exception as exc:
        logger.warning('[FACT_CLEANER] Falha ao limpar fatos com Ollama (%s). Usando heurística.', exc)
        return _heuristic_clean(extracted)

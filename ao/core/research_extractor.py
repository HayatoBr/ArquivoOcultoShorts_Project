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
    text = re.sub(r'^[\-•\*\d\)\.\(\s]+', '', text)
    return text.strip(' ,;:-')


def _split_sentences(text: str) -> List[str]:
    text = (text or '').replace('\r', ' ')
    parts = re.split(r'(?<=[\.!?])\s+', text)
    out: List[str] = []
    seen = set()
    for part in parts:
        line = _clean_line(part)
        if len(line) < 32:
            continue
        low = line.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(line)
    return out


def _heuristic_extract(topic: str, research_dump: str, research_items: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    text_parts: List[str] = []
    if research_dump:
        text_parts.append(research_dump)
    for item in research_items or []:
        chunk = ' '.join(x for x in [item.get('title', ''), item.get('snippet', '')] if x)
        if chunk:
            text_parts.append(chunk)
    text = ' '.join(text_parts)
    sentences = _split_sentences(text)
    fact_keywords = [
        'desaparec', 'sumiu', 'perdeu contato', 'último contato', 'mudou de rota', 'radar', 'registro',
        'busca', 'investiga', 'destro', 'evid', 'caixa-preta', 'testemunha', 'comunica', 'sinal',
    ]
    mystery_keywords = ['mistério', 'sem resposta', 'desconhec', 'incerto', 'hipótese', 'questiona', 'dúvida', 'inexplic']
    facts: List[str] = []
    mysteries: List[str] = []
    chronology: List[str] = []
    for sent in sentences:
        low = sent.lower()
        if any(k in low for k in fact_keywords):
            facts.append(sent)
        if any(k in low for k in mystery_keywords):
            mysteries.append(sent)
        if any(k in low for k in ['antes', 'depois', 'horas', 'dias', 'mais tarde', 'em seguida', 'após']):
            chronology.append(sent)
    if not facts:
        facts = sentences[:8]
    if not mysteries:
        mysteries = sentences[:3]
    if not chronology:
        chronology = facts[:3]
    return {
        'topic': topic,
        'facts': facts[:8],
        'mysteries': mysteries[:4],
        'timeline': chronology[:4],
    }


def extract_research_facts(
    cfg: Dict[str, Any],
    topic: str,
    research_dump: str,
    research_items: List[Dict[str, Any]] | None,
    logger,
) -> Dict[str, Any]:
    if _request is None or _llm_cfg is None:
        logger.info('[RESEARCH_EXTRACTOR] Ollama indisponível; usando extração heurística')
        return _heuristic_extract(topic, research_dump, research_items)

    llm_cfg = _llm_cfg(cfg)
    model = llm_cfg.get('research_model') or llm_cfg.get('local_model') or llm_cfg.get('ollama_model') or 'qwen2.5:7b-instruct-q4_K_M'
    timeout = int(llm_cfg.get('timeout_seconds') or llm_cfg.get('ollama_timeout_sec') or 180)
    temperature = float(llm_cfg.get('research_temperature', 0.2))
    top_p = float(llm_cfg.get('research_top_p', 0.72))
    num_predict = int(llm_cfg.get('research_num_predict', 420))

    prompt = f"""
Você é um pesquisador investigativo.

Analise a base documental e extraia apenas fatos realmente úteis para um short investigativo.

REGRAS:
- responda SOMENTE em JSON válido
- escreva em português do Brasil
- não copie frases literais longas da base
- não inclua jogos, softwares, lojas, reviews ou páginas irrelevantes
- foque no evento central, evidências, buscas, anomalias e perguntas sem resposta
- fatos curtos, claros e verificáveis
- no máximo 8 fatos
- no máximo 4 mistérios
- no máximo 4 itens de cronologia

Formato exato:
{{
  "topic": "{topic}",
  "facts": ["..."],
  "mysteries": ["..."],
  "timeline": ["..."]
}}

TEMA: {topic}

BASE DOCUMENTAL:
{research_dump}
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
                    'repeat_penalty': 1.05,
                },
            },
            timeout,
        )
        raw = (data.get('response') or '').strip()
        parsed = json.loads(raw)
        facts = [_clean_line(x) for x in parsed.get('facts') or [] if _clean_line(x)]
        mysteries = [_clean_line(x) for x in parsed.get('mysteries') or [] if _clean_line(x)]
        timeline = [_clean_line(x) for x in parsed.get('timeline') or [] if _clean_line(x)]
        if not facts:
            raise ValueError('JSON sem fatos úteis')
        return {
            'topic': parsed.get('topic') or topic,
            'facts': facts[:8],
            'mysteries': mysteries[:4],
            'timeline': timeline[:4],
        }
    except Exception as exc:
        logger.warning('[RESEARCH_EXTRACTOR] Falha ao extrair fatos com Ollama (%s). Usando heurística.', exc)
        return _heuristic_extract(topic, research_dump, research_items)

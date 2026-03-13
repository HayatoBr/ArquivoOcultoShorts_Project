
from __future__ import annotations

from typing import Any, Dict, Tuple
import requests

SCRIPT_TEMPERATURE_FALLBACK = 0.28
SCENE_TEMPERATURE_FALLBACK = 0.18
SCRIPT_NUM_PREDICT_FALLBACK = 240
SCENE_NUM_PREDICT_FALLBACK = 420

SCENE_JSON_SCHEMA_HINT = """
Return ONLY valid JSON in this exact format:
{
  "scenes": [
    {
      "scene_index": 1,
      "scene_type": "establishing",
      "subject_en": "short concrete visible subject in English, max 8 words",
      "location_en": "specific location in English, max 8 words",
      "era_en": "specific year or historical era in English, max 6 words",
      "action_en": "single visible action in English, max 10 words",
      "details_en": "3 to 5 short physical details in English, comma separated"
    }
  ]
}
""".strip()


def _llm_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("llm", {}) or {}


def _get_script_word_target(cfg: Dict[str, Any], packet: Dict[str, Any]) -> int:
    script_cfg = cfg.get("script", {}) or {}
    exact_from_packet = int(packet.get("exact_word_target") or 0)
    if exact_from_packet > 0:
        return exact_from_packet
    exact_from_cfg = int(script_cfg.get("target_words_exact", 0) or 0)
    if exact_from_cfg > 0:
        return exact_from_cfg
    lo = int(script_cfg.get("target_words_min", 138))
    hi = int(script_cfg.get("target_words_max", 146))
    return max(lo, round((lo + hi) / 2))


def _get_timeout_seconds(cfg: Dict[str, Any]) -> int:
    llm_cfg = _llm_cfg(cfg)
    return int(llm_cfg.get("timeout_seconds") or llm_cfg.get("ollama_timeout_sec") or 180)


def _build_script_prompt(cfg: Dict[str, Any], packet: Dict[str, Any]) -> str:
    channel_desc = cfg.get("channel", {}).get("description", "")
    target_words = _get_script_word_target(cfg, packet)
    target_min = max(120, target_words - 2)
    target_max = target_words + 2
    previous_words = int(packet.get("previous_word_count") or 0)
    rewrite_reason = (packet.get("rewrite_reason") or "").strip()
    previous_script = (packet.get("previous_script_clean") or "").strip()

    feedback_block = ""
    if previous_words and rewrite_reason:
        feedback_block = f"""
Resultado anterior:
- palavras anteriores: {previous_words}
- nova meta: exatamente {target_words} palavras
- faixa aceita: {target_min} a {target_max}
- motivo: {rewrite_reason}

Reescreva do zero. Preserve apenas os fatos centrais, mas ajuste o texto para bater a meta.
Texto anterior:
{previous_script}
""".strip()

    return f"""
Você é roteirista do canal Arquivo Oculto.

Escreva APENAS a narração final de um short investigativo em português do Brasil.

Canal:
{channel_desc}

Tema:
{packet['topic']}

Base documental profunda:
{packet['research_dump']}

Regras obrigatórias:
- escreva apenas UM parágrafo
- escreva entre {target_min} e {target_max} palavras
- alvo ideal: {target_words} palavras
- sem título
- sem markdown
- sem listas
- sem marcas como Cena:, Narrador:, Locução:
- use frases curtas e naturais para locução
- priorize ritmo de narração, clareza e impacto
- não faça introdução enciclopédica de biografia
- não liste muitos nomes próprios em sequência
- não empilhe datas e lugares na mesma frase
- ignore totalmente jogos, softwares, páginas de download, reviews, lojas e produtos não relacionados ao caso
- explique os fatos como narração documental, não como verbete da Wikipedia
- diferencie fato documentado de hipótese quando necessário
- evite descrições gráficas de violência, gore, sexualização, instruções perigosas e conteúdo chocante detalhado
- trate mortes, vítimas e menores com linguagem neutra, respeitosa e segura para YouTube
- comece com um gancho factual forte
- feche com uma pergunta curta ou reflexão curta
- não explique sua lógica
- não mencione contagem de palavras

{feedback_block}

Escreva agora a narração final.
""".strip()


def _build_scene_prompt(topic: str, script_clean: str, scene_count: int) -> str:
    return f"""
You are a historical documentary visual planner for short videos.

Create exactly {scene_count} scenes for SDXL Lightning.
Each scene must be visually different from the previous one.

Hard rules:
- Every field must be short and concrete.
- subject_en must be a visible person, object, vehicle, building, landscape, document, or evidence.
- action_en must describe one visible action only.
- details_en must contain 3 to 5 short physical details only.
- Do not copy raw narration text into any field.
- Do not use long phrases, parentheses, dates in sentence form, or biography sentences.
- Ignore unrelated games, software, reviews, products, stores, or download pages.
- Do not use abstract words such as mystery, enigma, truth, fear, tragedy, question mark, case, story.
- Do not use negative descriptions.
- Keep the same era and location unless the narration clearly changes them.
- Prefer historically grounded documentary images.
- At least 2 scenes must show people or investigators.
- At least 2 scenes must focus on physical evidence, documents, maps, objects, or traces.
- Use only these scene_type values: establishing, character, detail, evidence, investigation, reenactment, ending.

{SCENE_JSON_SCHEMA_HINT}

Topic: {topic}
Narration (pt-BR):
{script_clean}
""".strip()


def _request(cfg: Dict[str, Any], payload: Dict[str, Any], timeout: int):
    llm_cfg = _llm_cfg(cfg)
    url = (llm_cfg.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/")
    resp = requests.post(f"{url}/api/generate", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def write_with_ollama(cfg: Dict[str, Any], packet: Dict[str, Any], logger) -> Tuple[str, str]:
    llm_cfg = _llm_cfg(cfg)
    model = llm_cfg.get("local_model") or llm_cfg.get("ollama_model") or "qwen2.5:7b-instruct-q4_K_M"
    timeout = _get_timeout_seconds(cfg)
    prompt = _build_script_prompt(cfg, packet)
    temperature = float(llm_cfg.get("script_temperature", SCRIPT_TEMPERATURE_FALLBACK))
    top_p = float(llm_cfg.get("script_top_p", 0.76))
    num_predict = int(llm_cfg.get("script_num_predict", SCRIPT_NUM_PREDICT_FALLBACK))
    logger.info("Ollama: gerando roteiro com %s", model)
    data = _request(cfg, {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temperature, "top_p": top_p, "num_predict": num_predict, "repeat_penalty": 1.12}}, timeout)
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama retornou roteiro vazio")
    return text, "ollama"


def plan_visual_scenes_with_ollama(cfg: Dict[str, Any], topic: str, script_clean: str, scene_count: int, logger) -> str:
    llm_cfg = _llm_cfg(cfg)
    model = llm_cfg.get("scene_planner_model") or llm_cfg.get("local_model") or llm_cfg.get("ollama_model") or "qwen2.5:7b-instruct-q4_K_M"
    timeout = _get_timeout_seconds(cfg)
    prompt = _build_scene_prompt(topic, script_clean, scene_count)
    temperature = float(llm_cfg.get("scene_temperature", SCENE_TEMPERATURE_FALLBACK))
    top_p = float(llm_cfg.get("scene_top_p", 0.7))
    num_predict = int(llm_cfg.get("scene_num_predict", SCENE_NUM_PREDICT_FALLBACK))
    logger.info("Ollama: planejando cenas visuais com %s", model)
    data = _request(cfg, {"model": model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": temperature, "top_p": top_p, "num_predict": num_predict, "repeat_penalty": 1.05}}, timeout)
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama retornou planejamento visual vazio")
    return text

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import traceback
from typing import Any, Dict, Optional, Tuple

from core.script.wikipedia_source import get_wiki_doc_for_channel
from core.agents.policy_agent import soften_text_for_youtube, scan_youtube_policy_risks
from core.agents.script_cleaner_agent import clean_script_text
from core.agents.duration_agent import fit_to_duration
from core.agents.image_prompt_agent import build_scene_prompts

from core.script.llm_ollama import ollama_generate
from core.script.llm_openai import openai_generate

def _llm_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return (cfg or {}).get("llm", {}) or {}

def _script_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return (cfg or {}).get("script", {}) or {}

def _research_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return (cfg or {}).get("research", {}) or {}

def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def _save_json(path: Path, obj: Any) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _build_channel_prompt(base_doc: str, cfg: Dict[str, Any]) -> str:
    channel = (cfg or {}).get("channel", {}) or {}
    niche = channel.get("niche", "mistério")
    lang = channel.get("language", "pt")
    region = channel.get("region", "BR")
    scfg = _script_cfg(cfg)
    target_seconds = int(scfg.get("target_seconds", 60))
    # Keep prompt compact & deterministic
    return (
        f"Você é roteirista de vídeos curtos investigativos do canal 'Arquivo Oculto'.\n"
        f"Nicho: {niche}. Idioma: {lang}-{region}.\n"
        f"Tarefa: escreva um roteiro narrativo cinematográfico para um SHORT de ~{target_seconds}s.\n"
        f"Regras: 1) Sem gore/detalhes gráficos; 2) Sem acusações diretas sem fonte; 3) Tom investigativo e documental;\n"
        f"4) Texto limpo, sem listas, sem markdown, sem headings; 5) Termine com uma pergunta curta para retenção.\n\n"
        f"Base documental (use apenas como referência factual):\n{base_doc}\n"
    )

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search wrapper (ddgs>=7). Returns list of {title, href, body}."""
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:
        return []
    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                if not isinstance(r, dict):
                    continue
                results.append({
                    "title": r.get("title") or "",
                    "href": r.get("href") or "",
                    "body": r.get("body") or "",
                })
    except Exception:
        return []
    return results


def _build_testmode_research_doc(cfg: Dict[str, Any], base_doc: str) -> str:
    """Enrich wikipedia doc with DDG snippets for better local fallback."""
    rcfg = _research_cfg(cfg)
    if not bool(rcfg.get("ddg_enabled", True)):
        return base_doc

    channel = (cfg or {}).get("channel", {}) or {}
    niche = channel.get("niche", "mistério")
    region = channel.get("region", "BR")
    q = rcfg.get("ddg_query") or f"{niche} caso real não resolvido {region}"
    max_results = int(rcfg.get("ddg_max_results", 5))

    hits = _ddg_search(str(q), max_results=max_results)
    if not hits:
        return base_doc

    bullets: list[str] = []
    for h in hits[:max_results]:
        title = (h.get("title") or "").strip()
        href = (h.get("href") or "").strip()
        body = (h.get("body") or "").strip()
        if not title and not body:
            continue
        bullets.append(f"- {title}\n  {body}\n  Fonte: {href}")

    ddg_block = "\n\nFontes adicionais (DuckDuckGo - snippets):\n" + "\n".join(bullets) + "\n"
    return base_doc.strip() + ddg_block


def _ollama_qa_pass(text: str, cfg: Dict[str, Any]) -> str:
    """QA final local para evitar desperdício e manter conformidade. Mantém o tamanho."""
    llm = _llm_cfg(cfg)
    if not bool(llm.get("ollama_qa_enabled", True)):
        return text

    omodel = llm.get("ollama_model") or os.environ.get("OLLAMA_MODEL") or "llama3.2:latest"
    ourl = llm.get("ollama_url") or "http://127.0.0.1:11434/api/generate"
    otimeout = int(llm.get("ollama_timeout", 120))

    qa_prompt = (
        "Você é um revisor (QA) de roteiro para YouTube Shorts investigativos.\n"
        "Tarefa: revise o texto abaixo para ficar LIMPO e CINEMATOGRÁFICO, sem gore, sem acusações diretas, "
        "sem listas/markdown e mantendo aproximadamente o mesmo tamanho (não aumentar).\n"
        "Corrija repetições, datas quebradas (ex: '1 9 7 3'), e finalize com UMA pergunta curta.\n\n"
        "TEXTO:\n"
        f"{text.strip()}\n"
    )
    out = ollama_generate(qa_prompt, model=str(omodel), url=str(ourl), timeout=otimeout)
    return (out or text).strip()


def _try_llm(prompt: str, cfg: Dict[str, Any], test_mode: bool = False) -> Tuple[Optional[str], str, Optional[str]]:
    llm = _llm_cfg(cfg)

    # TEST MODE: sem OpenAI
    if test_mode:
        omodel = llm.get("ollama_model") or os.environ.get("OLLAMA_MODEL") or "llama3.2:latest"
        ourl = llm.get("ollama_url") or "http://127.0.0.1:11434/api/generate"
        otimeout = int(llm.get("ollama_timeout", 120))
        out = ollama_generate(prompt, model=str(omodel), url=str(ourl), timeout=otimeout)
        if out:
            return out, "ollama_test_mode", str(omodel)
        return None, "none", None

    provider = str(llm.get("provider") or "openai").lower()

    # OPENAI primeiro
    if provider == "openai":
        model = str(llm.get("openai_model") or "gpt-4o-mini")
        temperature = float(llm.get("openai_temperature", 0.7))
        max_tokens = int(llm.get("openai_max_tokens", 900))
        out = openai_generate(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
        if out:
            return out, "openai", model

    # OLLAMA fallback (ou provider=ollama)
    omodel = llm.get("ollama_model") or os.environ.get("OLLAMA_MODEL") or "llama3.2:latest"
    ourl = llm.get("ollama_url") or "http://127.0.0.1:11434/api/generate"
    otimeout = int(llm.get("ollama_timeout", 120))
    out = ollama_generate(prompt, model=str(omodel), url=str(ourl), timeout=otimeout)
    if out:
        return out, "ollama", str(omodel)

    return None, "none", None


def generate_short_script(cfg: Dict[str, Any] | None = None, out_path: str | None = None, test_mode: bool = False) -> str:
    """Generate script.txt for the job.

    Returns the script path (string). Writes a script_report.json alongside the script.
    """
    cfg = cfg or {}
    report: Dict[str, Any] = {
        "provider": None,
        "provider_model": None,
        "policy_findings": [],
        "policy_softened": False,
        "cleaned": False,
        "duration_fit": False,
        "error": None,
    }

    # output
    if out_path is None:
        out_path = str(Path("output") / "script.txt")
    script_path = Path(out_path)
    report_path = script_path.with_name("script_report.json")

    try:
        # 1) Wikipedia base doc (free + stable)
        doc = get_wiki_doc_for_channel(cfg)
        base_doc = doc.text if hasattr(doc, "text") else str(doc)

        # 2) Ask LLM for a cinematic short (Gemini -> Ollama)
        prompt = _build_channel_prompt(base_doc, cfg)
        llm_text, provider, provider_model = _try_llm(prompt, cfg, test_mode=test_mode)

        if not llm_text:
            # hard fallback: use base doc itself (still pass through cleaners)
            llm_text = base_doc
            provider = "wikipedia"
            provider_model = None

        report["provider"] = provider
        report["provider_model"] = provider_model

        # 3) YouTube safety scan + soften (light)
        try:
            findings = scan_youtube_policy_risks(llm_text)
            report["policy_findings"] = [f.__dict__ for f in findings]
            if findings:
                llm_text = soften_text_for_youtube(llm_text)
                report["policy_softened"] = True
        except Exception:
            pass

        # 4) Clean script for TTS
        try:
            cleaned = clean_script_text(llm_text, cfg)
            llm_text = cleaned.get("text", llm_text)
            report["cleaned"] = True
        except Exception:
            pass

        # 5) Fit to duration
        try:
            scfg = _script_cfg(cfg)
            if bool(scfg.get("enforce", True)):
                target_seconds = int(scfg.get("target_seconds", 60))
                wpm = int(scfg.get("wpm", 155))
                max_words = scfg.get("max_words", None)
                max_words_int = int(max_words) if max_words is not None else None
                closing_question = bool(scfg.get("closing_question", True))
                fit = fit_to_duration(llm_text, target_seconds=target_seconds, wpm=wpm, max_words=max_words_int, closing_question=closing_question)
                llm_text = fit.get("text", llm_text)
                report["duration_fit"] = bool(fit.get("changed", False))
        except Exception:
            pass

        # 5.1) QA final (Ollama)
        try:
            llm_text = _ollama_qa_pass(llm_text, cfg)
        except Exception:
            pass

        _ensure_parent(script_path)
        script_path.write_text(llm_text.strip() + "\n", encoding="utf-8")
        _save_json(report_path, report)

        # Also create a minimal scenes.json for downstream image prompting (1 scene for now)
        try:
            scenes = build_scene_prompts(llm_text, max_scenes=1)
            scenes_path = script_path.with_name("scenes.json")
            _save_json(scenes_path, [s.__dict__ for s in scenes])
        except Exception:
            pass

        return str(script_path)

    except Exception as e:
        report["error"] = str(e)
        report["traceback"] = traceback.format_exc()
        _save_json(report_path, report)
        # still raise to surface in logs
        raise
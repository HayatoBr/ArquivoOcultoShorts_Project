from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from core.agents.theme_job_preset_auto import ensure_job_theme_preset_id


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return path.read_text(encoding=enc).strip()
        except Exception:
            pass
    return path.read_text(errors="ignore").strip()


def build_llm_adapter(cfg: dict):
    import os
    llm_cfg = (cfg.get("llm") or {})
    gem_key = os.environ.get("GEMINI_API_KEY") or llm_cfg.get("gemini_api_key")
    ollama_url = os.environ.get("OLLAMA_URL") or llm_cfg.get("ollama_url", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL") or llm_cfg.get("ollama_model", "llama3.1")

    gemini = None
    ollama = None
    if gem_key:
        try:
            from core.llm.llm_gemini import GeminiLLM
            gemini = GeminiLLM(api_key=gem_key, model=llm_cfg.get("gemini_model", "gemini-2.0-flash"))
        except Exception:
            gemini = None

    try:
        from core.llm.llm_ollama import OllamaLLM
        ollama = OllamaLLM(base_url=ollama_url, model=ollama_model)
    except Exception:
        ollama = None

    return gemini or ollama


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yml")
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--script", default="script.txt")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    job_dir = Path(args.job_dir)
    script_path = job_dir / args.script
    llm = build_llm_adapter(cfg)

    chosen = ensure_job_theme_preset_id(job_dir=job_dir, script_text=read_text(script_path), cfg=cfg, llm=llm)
    if chosen:
        print(f"OK: preset do tema fixado no job: {chosen}")
    else:
        print("Sem alteração (ou catálogo/tema desabilitado).")


if __name__ == "__main__":
    main()

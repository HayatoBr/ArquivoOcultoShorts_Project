import os, shutil

def _strip_quotes(s: str) -> str:
    return s.strip().strip('"').strip("'")

def _get_cfg_path(cfg: dict, key: str) -> str:
    """Resolve a path key from config.yml.

    Backwards compatible:
      - cfg.paths.<key> (preferred)
      - cfg.whisper.<key> (legacy for whisper_exe, whisper_model)
      - cfg.ffmpeg.<key> / cfg.piper.<key> (legacy)
    """
    paths = cfg.get("paths") or {}
    v = paths.get(key, "")
    if v:
        return str(v)

    # legacy sections
    for section in ("whisper", "ffmpeg", "piper"):
        sec = cfg.get(section) or {}
        if key in sec and sec.get(key):
            return str(sec.get(key))

    return ""

def resolve_exe(cfg: dict, key: str, fallback_name: str | None = None) -> str:
    p = _strip_quotes(_get_cfg_path(cfg, key))
    if p:
        if os.path.isfile(p):
            return p
        raise RuntimeError(f"Caminho configurado não existe para {key}: {p}")

    if fallback_name:
        found = shutil.which(fallback_name)
        if found:
            return found
        raise RuntimeError(
            f"{fallback_name} não encontrado no PATH e nenhum caminho foi configurado em config.yml ({key})."
        )

    raise RuntimeError(f"Nenhum caminho configurado para {key}.")

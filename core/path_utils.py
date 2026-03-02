import os, shutil

def _strip_quotes(s: str) -> str:
    return s.strip().strip('"').strip("'")

def resolve_exe(cfg: dict, key: str, fallback_name: str | None = None) -> str:
    paths = cfg.get('paths') or {}
    p = _strip_quotes(str(paths.get(key, '') or ''))
    if p:
        if os.path.isfile(p):
            return p
        raise RuntimeError(f"Caminho configurado não existe para paths.{key}: {p}")
    if fallback_name:
        found = shutil.which(fallback_name)
        if found:
            return found
        raise RuntimeError(f"{fallback_name} não encontrado no PATH e nenhum caminho foi configurado em config.yml (paths.{key}).")
    raise RuntimeError(f"Nenhum caminho configurado para paths.{key}.")

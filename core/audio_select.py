import os, random

AUDIO_EXTS = ('.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg')

def _list_audio(dirpath: str):
    if not dirpath:
        return []
    if not isinstance(dirpath, (str, bytes, os.PathLike)):
        return []
    if not os.path.isdir(dirpath):
        return []
    out = [os.path.join(dirpath, fn) for fn in os.listdir(dirpath) if fn.lower().endswith(AUDIO_EXTS)]
    out.sort()
    return out

def _pick_folder(val, *keys, default=None):
    """Aceita string OU dict (ex: {folder: 'assets/music'}) e devolve uma string de pasta."""
    if isinstance(val, (str, bytes, os.PathLike)):
        return str(val)
    if isinstance(val, dict):
        for k in keys:
            v = val.get(k)
            if isinstance(v, (str, bytes, os.PathLike)) and str(v).strip():
                return str(v)
    return default

def select_audio(cfg: dict) -> dict:
    audio_cfg = cfg.get('audio') or {}

    # Música (suporta formatos antigos e o atual: audio.music.folder)
    music_dir = audio_cfg.get('music_dir') or audio_cfg.get('music_folder')
    if not music_dir:
        music_dir = _pick_folder(audio_cfg.get('music'), 'folder', 'dir', 'path', default=None)
    if not music_dir:
        music_dir = os.path.join('assets', 'music')

    # SFX (suporta: audio.sfx.ambience_folder / transitions_folder etc, e também chaves antigas)
    sfx_cfg = audio_cfg.get('sfx') or {}
    ambience_dir    = sfx_cfg.get('ambience_folder')    or sfx_cfg.get('ambience')    or os.path.join('assets','sfx','ambience')
    transitions_dir = sfx_cfg.get('transitions_folder') or sfx_cfg.get('transitions') or os.path.join('assets','sfx','transitions')
    hits_dir        = sfx_cfg.get('hits_folder')        or sfx_cfg.get('hits')        or os.path.join('assets','sfx','hits')
    archive_dir     = sfx_cfg.get('archive_folder')     or sfx_cfg.get('archive')     or os.path.join('assets','sfx','archive')

    music = _list_audio(music_dir)
    ambience = _list_audio(ambience_dir)
    transitions = _list_audio(transitions_dir)
    hits = _list_audio(hits_dir)
    archive = _list_audio(archive_dir)

    # Limites (preferir config novo dentro de audio.sfx, mas aceitar antigos)
    max_trans = int(sfx_cfg.get('max_transitions') or (audio_cfg.get('limits', {}) or {}).get('max_transitions', 4))
    max_hits  = int(sfx_cfg.get('max_hits') or (audio_cfg.get('limits', {}) or {}).get('max_hits', 3))
    max_arch  = int(sfx_cfg.get('max_archive') or (audio_cfg.get('limits', {}) or {}).get('max_archive', 2))

    return {
        "music": random.choice(music) if music else None,
        "ambience": random.choice(ambience) if ambience else None,
        "transitions": random.sample(transitions, min(len(transitions), max_trans)),
        "hits": random.sample(hits, min(len(hits), max_hits)),
        "archive": random.sample(archive, min(len(archive), max_arch)),
    }

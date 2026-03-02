import os, random

def _pick_files(dirpath):
    if not os.path.isdir(dirpath): return []
    return [os.path.join(dirpath,f) for f in os.listdir(dirpath) if f.lower().endswith(('.wav','.mp3'))]

def select_audio(config):
    music = _pick_files(config['audio']['music_dir'])
    sfx = {
        'ambience': _pick_files(config['audio']['sfx']['ambience']),
        'transitions': _pick_files(config['audio']['sfx']['transitions']),
        'hits': _pick_files(config['audio']['sfx']['hits']),
        'archive': _pick_files(config['audio']['sfx']['archive']),
    }
    chosen = {
        'music': random.choice(music) if music else None,
        'ambience': random.choice(sfx['ambience']) if sfx['ambience'] else None,
        'transitions': random.sample(sfx['transitions'], min(len(sfx['transitions']), 4)),
        'hits': random.sample(sfx['hits'], min(len(sfx['hits']), 3)),
        'archive': random.sample(sfx['archive'], min(len(sfx['archive']), 2)),
    }
    return chosen

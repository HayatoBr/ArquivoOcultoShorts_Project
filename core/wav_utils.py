import wave
import contextlib
import os

def wav_duration_seconds(path: str) -> float:
    if not path or not os.path.isfile(path):
        return 0.0
    with contextlib.closing(wave.open(path, "rb")) as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return float(frames) / float(rate) if rate else 0.0

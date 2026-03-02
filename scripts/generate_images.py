from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when executed as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.config import load_config  # noqa: E402
from core.images.image_generator import generate_images_from_script  # noqa: E402


def _latest_job_dir(output_root: Path) -> Path | None:
    jobs = output_root / "jobs"
    if not jobs.exists():
        return None
    # job_short_YYYYMMDD_HHMMSS
    candidates = [p for p in jobs.iterdir() if p.is_dir() and p.name.startswith("job_short_")]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _resolve_paths() -> tuple[str, str]:
    # Prefer env vars set by pipeline runner
    script_path = (os.environ.get("AO_SCRIPT_PATH") or "").strip()
    out_dir = (os.environ.get("AO_IMAGES_DIR") or "").strip()
    if script_path and out_dir:
        return script_path, out_dir

    # Fallback 1: CLI args: --script <path> --out <dir>
    args = sys.argv[1:]
    if "--script" in args and "--out" in args:
        try:
            s = args[args.index("--script") + 1]
            o = args[args.index("--out") + 1]
            if s and o:
                return s, o
        except Exception:
            pass

    # Fallback 2: infer latest job folder (zero-config robustness)
    out_root = Path("output")
    job = _latest_job_dir(out_root)
    if job:
        s = job / "script.txt"
        o = job / "images"
        o.mkdir(parents=True, exist_ok=True)
        return str(s), str(o)

    raise RuntimeError("AO_SCRIPT_PATH não definido e não foi possível inferir um job em output/jobs.")


def main():
    cfg = load_config()

    script_path, out_dir = _resolve_paths()
    max_images = int((os.environ.get("AO_MAX_IMAGES") or "5").strip() or "5")

    if not Path(script_path).exists():
        raise RuntimeError(f"Script não encontrado: {script_path}")

    images = generate_images_from_script(cfg, script_path=script_path, out_dir=out_dir, max_images=max_images)
    print(f"OK: imagens geradas: {len(images)}")
    for p in images:
        print(p)


if __name__ == "__main__":
    main()

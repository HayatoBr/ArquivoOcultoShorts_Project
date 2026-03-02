from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure project root in sys.path when called as script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.utils.config_loader import load_config  # type: ignore
from core.images.image_generator import generate_images_from_script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="Caminho para script.txt")
    ap.add_argument("--out", required=True, help="Pasta de saída para imagens")
    ap.add_argument("--max", type=int, default=5, help="Máximo de imagens")
    args = ap.parse_args()

    cfg = load_config()  # loads config/config.yml
    imgs = generate_images_from_script(cfg, script_path=args.script, out_dir=args.out, max_images=args.max)
    print("OK:", len(imgs), "imagens")


if __name__ == "__main__":
    main()

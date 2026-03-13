from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch

from ao.utils.config_loader import load_config
from ao.utils.logger import make_logger
from ao.core.pipeline_short import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arquivo Oculto Shorts - pipeline principal"
    )
    parser.add_argument("--test", action="store_true", help="Roda em TestMode")
    parser.add_argument("--topic", type=str, default="", help="Força um tema")
    parser.add_argument("--config", type=str, default="config.yml", help="Caminho do config")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    config_path = (project_root / args.config).resolve()

    cfg = load_config(config_path)
    logger = make_logger(project_root, name="run_short")

    logger.info(">>> Raiz do projeto: %s", project_root)
    logger.info(">>> Config: %s", config_path)
    logger.info(">>> Executando %s", "TEST MODE" if args.test else "MODO PRODUÇÃO")
    logger.info("[BOOT] python=%s", sys.executable)
    logger.info("[BOOT] torch=%s | torch_cuda=%s | cuda_available=%s", torch.__version__, getattr(torch.version, "cuda", None), torch.cuda.is_available())
    logger.info("[BOOT] CUDA_VISIBLE_DEVICES=%s", os.environ.get("CUDA_VISIBLE_DEVICES"))

    try:
        out = run_pipeline(
            cfg=cfg,
            project_root=project_root,
            test_mode=args.test,
            topic_hint=args.topic.strip(),
            logger=logger,
        )
        logger.info("OK: pipeline finalizado em %s", out)
        return 0
    except Exception:
        logger.exception("Pipeline falhou")
        return 1


if __name__ == "__main__":
    sys.exit(main())
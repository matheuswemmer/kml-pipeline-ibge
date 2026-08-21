"""Log por execução, em arquivo e no console."""

import logging
from datetime import datetime

from . import paths


def setup(nome: str) -> logging.Logger:
    paths.ensure()
    arquivo = paths.LOGS / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{nome}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        handlers=[
            logging.FileHandler(arquivo, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logging.info("log desta execução: %s", arquivo)
    return logging.getLogger(nome)

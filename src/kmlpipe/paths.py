"""Resolução de caminhos do projeto, independente de onde o script rodou."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"           # ZIPs e GPKGs exatamente como vieram do IBGE
INTERIM = DATA / "interim"   # CSVs extraídos, ainda com nomes originais
PROCESSED = DATA / "processed"  # tabelas padronizadas, parquet
DICTS = DATA / "dicts"       # dicionários de variáveis
OUTPUT = ROOT / "output"     # KMZ municipais entregues
LOGS = ROOT / "logs"

ALL = [RAW, INTERIM, PROCESSED, DICTS, OUTPUT, LOGS]


def ensure() -> None:
    """Cria os diretórios de trabalho se ainda não existirem."""
    for path in ALL:
        path.mkdir(parents=True, exist_ok=True)

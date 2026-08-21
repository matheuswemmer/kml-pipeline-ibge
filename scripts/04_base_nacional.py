"""04 — Materializa a base nacional de indicadores por setor censitário.

Uso:
    python scripts/04_base_nacional.py

Lê as 6 tabelas do IBGE uma única vez, calcula os 32 indicadores curados para
os 458.772 setores do país e grava data/processed/indicadores_br.parquet.

Esta etapa existe para inverter o gargalo. Gerando município a município
direto dos CSV, cada arquivo custaria uma releitura das tabelas nacionais
(~20 s) — 5.570 municípios levariam mais de 30 horas. Lendo uma vez e fatiando
o Parquet depois, o mesmo trabalho cai para minutos.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import consolidar, headers, logging_setup, paths  # noqa: E402

DESTINO = "indicadores_br.parquet"


def main() -> int:
    log = logging_setup.setup("base_nacional")
    paths.ensure()

    inicio = time.time()
    cabecalhos = headers.obter(sources.TABELAS)

    brutos = consolidar.carregar(
        ind_cfg.INDICADORES, sources.TABELAS, cabecalhos, cod_mun=None,
    )
    calculados = consolidar.calcular(ind_cfg.INDICADORES, brutos)

    # cd_setor é a chave de tudo; vira coluna para sobreviver ao Parquet.
    calculados = calculados.reset_index()

    esperado = {ind.nome for ind in ind_cfg.INDICADORES}
    faltando = esperado - set(calculados.columns)
    if faltando:
        log.error("indicadores não calculados: %s", sorted(faltando))
        return 1

    chave = calculados[consolidar.CHAVE]
    if chave.duplicated().any():
        log.error("cd_setor duplicado na base nacional: %d linha(s)",
                  int(chave.duplicated().sum()))
        return 1
    if not chave.str.fullmatch(r"\d{15}").all():
        log.error("cd_setor fora do padrão de 15 dígitos")
        return 1

    destino = paths.PROCESSED / DESTINO
    calculados.to_parquet(destino, index=False, compression="zstd")

    log.info("%d setores x %d indicadores -> %s (%.1f MB) em %.0f s",
             len(calculados), len(esperado), destino,
             destino.stat().st_size / 1e6, time.time() - inicio)

    # Preenchimento por indicador: onde estiver muito baixo, é cobertura da
    # fonte, não erro — mas convém enxergar antes de gerar 5.570 arquivos.
    print()
    print("preenchimento nacional por indicador (%):")
    print(calculados[sorted(esperado)].notna().mean().mul(100).round(1).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

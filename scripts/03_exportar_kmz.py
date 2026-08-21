"""03 — Gera o arquivo de um município só, para conferência pontual.

Uso:
    python scripts/03_exportar_kmz.py --uf SC --municipio 4209102
    python scripts/03_exportar_kmz.py --uf SC --municipio 4209102 --kmz

Para gerar uma UF inteira use scripts/05_gerar_lote.py, que é muito mais
rápido por preparar a malha uma vez só.

Usa a base nacional (scripts/04_base_nacional.py) quando ela existir; sem ela,
recai na leitura direta dos CSV, que custa ~20 s por execução.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import (consolidar, exportar, headers,  # noqa: E402
                     logging_setup, lote, paths)


def indicadores_do_municipio(prefixo_uf: str, cod_mun: str, log):
    """Do Parquet quando houver; dos CSV quando não."""
    if (paths.PROCESSED / lote.PARQUET).exists():
        base, colunas = lote.carregar_indicadores(prefixo_uf)
        return base[base.index.str.startswith(cod_mun)], colunas

    log.info("base nacional ausente, lendo dos CSV (mais lento)")
    cabecalhos = headers.obter(sources.TABELAS)
    brutos = consolidar.carregar(
        ind_cfg.INDICADORES, sources.TABELAS, cabecalhos, cod_mun=cod_mun,
    )
    calculados = consolidar.calcular(ind_cfg.INDICADORES, brutos)
    return calculados, list(calculados.columns)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uf", required=True, help="sigla da UF (ex.: SC)")
    p.add_argument("--municipio", required=True,
                   help="código IBGE de 7 dígitos (ex.: 4209102)")
    p.add_argument("--kmz", action="store_true",
                   help="gerar .kmz em vez de .kml")
    args = p.parse_args()

    log = logging_setup.setup("exportar")
    paths.ensure()

    sigla = args.uf.upper()
    codigos = {v: k for k, v in sources.UFS.items()}
    if sigla not in codigos:
        log.error("UF desconhecida: %s", sigla)
        return 1

    gpkg = paths.RAW / f"{sigla}_setores_CD2022.gpkg"
    if not gpkg.exists():
        log.error("malha ausente: %s — rode 01_download.py --uf %s", gpkg.name, sigla)
        return 1

    malha = exportar.carregar_malha(gpkg, args.municipio)
    malha = exportar.reparar_geometrias(malha)
    malha = exportar.normalizar_malha(malha)
    malha = exportar.reprojetar(malha)

    indicadores, colunas = indicadores_do_municipio(
        codigos[sigla], args.municipio, log,
    )

    destino = lote.caminho_saida(
        sigla, args.municipio, malha["NM_MUN"].iloc[0],
        ext=".kmz" if args.kmz else ".kml",
    )
    stats = exportar.gerar_municipio(malha, indicadores, destino, colunas)

    log.info("%s: %d setores, %.2f MB", destino.name,
             stats["setores"], stats["bytes"] / 1e6)

    dados = exportar.juntar(malha, indicadores)
    print()
    print(dados[["CD_SETOR", "NM_BAIRRO", "renda_resp_mediana",
                 "pct_via_pavimentada", "pct_arborizacao"]].head(8).to_string(index=False))
    print()
    print("preenchimento por indicador (%):")
    print(dados[colunas].notna().mean().mul(100).round(1).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""03 — Gera o KMZ de setores enriquecido com os indicadores curados.

Uso:
    python scripts/03_exportar_kmz.py --uf SC --municipio 4209102
    python scripts/03_exportar_kmz.py --uf SC            # UF inteira

Saída em output/<uf>/<nome>_<codigo>_setores_CD2022.kmz, seguindo a convenção
de nome do próprio IBGE.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import consolidar, exportar, headers, logging_setup, paths  # noqa: E402


def apelido(texto: str) -> str:
    """Nome de arquivo no padrão do IBGE: minúsculo, sem acento, com _."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uf", required=True, help="sigla da UF (ex.: SC)")
    p.add_argument("--municipio", help="código IBGE de 7 dígitos (ex.: 4209102)")
    p.add_argument("--kml", action="store_true",
                   help="gerar também .kml puro, além do .kmz")
    args = p.parse_args()

    log = logging_setup.setup("exportar")
    paths.ensure()

    sigla = args.uf.upper()
    if sigla not in sources.UFS.values():
        log.error("UF desconhecida: %s", sigla)
        return 1

    gpkg = paths.RAW / f"{sigla}_setores_CD2022.gpkg"
    if not gpkg.exists():
        log.error("malha ausente: %s — rode 01_download.py --uf %s", gpkg.name, sigla)
        return 1

    malha = exportar.carregar_malha(gpkg, args.municipio)

    cabecalhos = headers.obter(sources.TABELAS)
    brutos = consolidar.carregar(
        ind_cfg.INDICADORES, sources.TABELAS, cabecalhos, cod_mun=args.municipio,
    )
    calculados = consolidar.calcular(ind_cfg.INDICADORES, brutos)
    colunas = list(calculados.columns)

    dados = exportar.juntar(malha, calculados)

    if args.municipio:
        nome = f"{apelido(malha['NM_MUN'].iloc[0])}_{args.municipio}"
    else:
        nome = f"{sigla.lower()}_uf"
    destino = paths.OUTPUT / sigla / f"{nome}_setores_CD2022.kmz"

    exportar.escrever_kmz(dados, destino, colunas)
    exportar.validar(destino, len(dados), colunas)

    if args.kml:
        puro = destino.with_suffix(".kml")
        exportar.escrever_kmz(dados, puro, colunas)
        exportar.validar(puro, len(dados), colunas)

    # Amostra do resultado, para conferência visual imediata.
    amostra = dados[["CD_SETOR", "NM_BAIRRO", "renda_resp_mediana",
                     "pct_via_pavimentada", "pct_arborizacao"]].head(8)
    print()
    print(amostra.to_string(index=False))
    print()
    preenchimento = dados[colunas].notna().mean().mul(100).round(1)
    print("preenchimento por indicador (%):")
    print(preenchimento.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

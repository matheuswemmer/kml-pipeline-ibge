"""01 — Baixa as fontes do IBGE declaradas em config/sources.py.

Uso:
    python scripts/01_download.py --dicionarios
    python scripts/01_download.py --tabelas
    python scripts/01_download.py --uf RO
    python scripts/01_download.py --tudo

Os arquivos caem em data/raw/ com o nome original do IBGE e são registrados
em data/raw/manifest.json. Re-executar não rebaixa o que já está íntegro.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import sources  # noqa: E402
from kmlpipe import download, logging_setup, paths  # noqa: E402


def nome_local(url: str) -> str:
    """Nome do arquivo em disco: o basename do IBGE, com acentos decodificados."""
    return unquote(url.rsplit("/", 1)[-1])


def baixar_grupo(itens: dict[str, str], destino: Path, log, forcar: bool) -> None:
    for chave, url in itens.items():
        try:
            download.baixar(url, destino / nome_local(url), forcar=forcar)
        except Exception as erro:
            log.error("falhou %s: %s", chave, erro)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dicionarios", action="store_true", help="dicionários de variáveis")
    p.add_argument("--tabelas", action="store_true", help="agregados por setor (CSV)")
    p.add_argument("--uf", metavar="SIGLA", help="GeoPackage e KMZ de uma UF (ex.: RO)")
    p.add_argument("--malha-br", action="store_true", help="GeoPackage do Brasil (1,5 GB)")
    p.add_argument("--tudo", action="store_true", help="dicionários + tabelas + malha BR")
    p.add_argument("--forcar", action="store_true", help="rebaixar mesmo se já existir")
    args = p.parse_args()

    if not any([args.dicionarios, args.tabelas, args.uf, args.malha_br, args.tudo]):
        p.print_help()
        return 1

    log = logging_setup.setup("download")
    paths.ensure()

    if args.dicionarios or args.tudo:
        log.info("=== dicionários de variáveis ===")
        baixar_grupo(sources.DICIONARIOS, paths.DICTS, log, args.forcar)

    if args.tabelas or args.tudo:
        log.info("=== agregados por setor censitário ===")
        tabelas = {nome: url for nome, (url, _) in sources.TABELAS.items()}
        baixar_grupo(tabelas, paths.RAW, log, args.forcar)

    if args.uf:
        sigla = args.uf.upper()
        codigos = {v: k for k, v in sources.UFS.items()}
        if sigla not in codigos:
            log.error("UF desconhecida: %s", sigla)
            return 1
        log.info("=== malha da UF %s ===", sigla)
        baixar_grupo(
            {
                f"gpkg_{sigla}": sources.malha_gpkg_uf(sigla),
                f"kml_{sigla}": sources.malha_kml_uf(codigos[sigla], sigla),
            },
            paths.RAW,
            log,
            args.forcar,
        )

    if args.malha_br or args.tudo:
        log.info("=== GeoPackage do Brasil (1,5 GB) ===")
        baixar_grupo({"gpkg_BR": sources.MALHA_GPKG_BR}, paths.RAW, log, args.forcar)

    log.info("concluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

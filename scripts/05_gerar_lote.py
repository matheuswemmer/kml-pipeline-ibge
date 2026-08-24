"""05 — Gera os KML de todos os municípios de uma UF.

Uso:
    python scripts/05_gerar_lote.py --uf MA
    python scripts/05_gerar_lote.py --uf MA --processos 6 --refazer

Exige a base nacional em data/processed/indicadores_br.parquet
(scripts/04_base_nacional.py) e o GeoPackage da UF em data/raw, que é baixado
automaticamente se faltar.

O paralelismo tem padrão 1 de propósito: em execução serial, uma falha aponta
direto para o município que a causou.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import download, logging_setup, lote, paths  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uf", required=True, help="sigla da UF (ex.: MA)")
    p.add_argument("--processos", type=int, default=1,
                   help="processos paralelos (padrão 1)")
    p.add_argument("--refazer", action="store_true",
                   help="regerar mesmo os municípios já no manifesto")
    p.add_argument("--conjunto", default="todos", choices=sorted(ind_cfg.CONJUNTOS),
                   help="quais indicadores vão para o KML (padrão: todos)")
    args = p.parse_args()

    log = logging_setup.setup("lote")
    paths.ensure()

    sigla = args.uf.upper()
    codigos = {v: k for k, v in sources.UFS.items()}
    if sigla not in codigos:
        log.error("UF desconhecida: %s", sigla)
        return 1
    prefixo = codigos[sigla]

    gpkg = paths.RAW / f"{sigla}_setores_CD2022.gpkg"
    if not gpkg.exists():
        log.info("malha de %s ausente, baixando", sigla)
        download.baixar(sources.malha_gpkg_uf(sigla), gpkg)

    somente = ind_cfg.CONJUNTOS[args.conjunto]
    log.info("conjunto %r: %d indicadores -> %s",
             args.conjunto, len(somente), ", ".join(somente))

    # Quais dos indicadores escolhidos vêm do bloco de entorno, para o campo
    # COBERTURA_IBGE poder dizer "IBGE não pesquisou a rua" em vez de um
    # genérico "dados parciais".
    de_entorno = {ind.nome for ind in ind_cfg.INDICADORES
                  if ind.tabela == "entorno_domicilios"}

    resumo = lote.gerar_uf(sigla, prefixo, somente=somente, de_entorno=de_entorno,
                           refazer=args.refazer, processos=args.processos)

    print()
    print(f"UF                    {resumo['uf']}")
    print(f"conjunto              {args.conjunto} ({len(somente)} indicadores)")
    print(f"municípios gerados    {resumo['municipios']}")
    print(f"setores na malha      {resumo['setores_na_malha']}")
    print(f"setores nos arquivos  {resumo['setores_nos_arquivos']}")
    print(f"tamanho total         {resumo['bytes'] / 1e6:.1f} MB")
    print(f"tempo                 {resumo['segundos']:.0f} s "
          f"({resumo['segundos'] / max(resumo['municipios'], 1):.2f} s/município)")

    if resumo["setores_na_malha"] != resumo["setores_nos_arquivos"]:
        log.error("RECONCILIAÇÃO FALHOU: %d setores na malha, %d nos arquivos",
                  resumo["setores_na_malha"], resumo["setores_nos_arquivos"])
        return 1
    if resumo["falhas"]:
        return 1

    print("\nreconciliação ok: todo setor da malha está em algum arquivo")
    return 0


if __name__ == "__main__":
    sys.exit(main())

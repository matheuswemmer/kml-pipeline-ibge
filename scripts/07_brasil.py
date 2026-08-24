"""07 — Gera os KML municipais de todas as UFs, ou de uma lista delas.

Uso:
    python scripts/07_brasil.py --conjunto essenciais --processos 6
    python scripts/07_brasil.py --ufs MA,SC,RO
    python scripts/07_brasil.py --refazer

Para cada UF: baixa a malha se faltar, gera os municípios e valida. É
retomável — o manifesto por UF faz a execução seguinte pular o que já saiu,
então uma queda no meio não obriga a recomeçar.

As UFs vão da maior para a menor. Se algo quebrar em São Paulo, quebra nos
primeiros minutos, e não depois de meia hora de trabalho perdido.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import download, logging_setup, lote, paths  # noqa: E402

# Ordem aproximada de tamanho, das maiores para as menores.
ORDEM = ["SP", "MG", "RS", "BA", "PR", "GO", "SC", "PB", "PI", "MA", "PE",
         "CE", "RN", "MT", "PA", "TO", "AL", "MS", "ES", "SE", "AM", "RJ",
         "RO", "AC", "AP", "RR", "DF"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ufs", help="lista separada por vírgula (padrão: todas)")
    p.add_argument("--conjunto", default="essenciais",
                   choices=sorted(ind_cfg.CONJUNTOS))
    p.add_argument("--processos", type=int, default=6)
    p.add_argument("--refazer", action="store_true")
    args = p.parse_args()

    log = logging_setup.setup("brasil")
    paths.ensure()

    if args.ufs:
        siglas = [s.strip().upper() for s in args.ufs.split(",")]
    else:
        siglas = [s for s in ORDEM if s in sources.UFS.values()]

    desconhecidas = [s for s in siglas if s not in sources.UFS.values()]
    if desconhecidas:
        log.error("UF desconhecida: %s", desconhecidas)
        return 1

    codigos = {v: k for k, v in sources.UFS.items()}
    somente = ind_cfg.CONJUNTOS[args.conjunto]
    de_entorno = {ind.nome for ind in ind_cfg.INDICADORES
                  if ind.tabela == "entorno_domicilios"}
    rotulos = {ind.nome: (ind.rotulo, ind.tipo) for ind in ind_cfg.INDICADORES}

    log.info("%d UF(s), conjunto %r com %d indicadores, %d processo(s)",
             len(siglas), args.conjunto, len(somente), args.processos)

    inicio = time.time()
    resumos, quebradas = [], []

    for i, sigla in enumerate(siglas, 1):
        log.info("========== [%d/%d] %s ==========", i, len(siglas), sigla)
        try:
            gpkg = paths.RAW / f"{sigla}_setores_CD2022.gpkg"
            if not gpkg.exists():
                download.baixar(sources.malha_gpkg_uf(sigla), gpkg)

            resumo = lote.gerar_uf(
                sigla, codigos[sigla], somente=somente, de_entorno=de_entorno,
                rotulos=rotulos, refazer=args.refazer, processos=args.processos,
            )
            if resumo["setores_na_malha"] != resumo["setores_nos_arquivos"]:
                raise RuntimeError(
                    f"reconciliação falhou: {resumo['setores_na_malha']} na malha, "
                    f"{resumo['setores_nos_arquivos']} nos arquivos"
                )
            if resumo["falhas"]:
                raise RuntimeError(f"{len(resumo['falhas'])} município(s) falharam")

            # Validação completa, no mesmo processo que gerou: relê os arquivos
            # e confronta com a malha e o Parquet.
            validacao = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "06_validar_uf.py"),
                 "--uf", sigla, "--conjunto", args.conjunto],
                capture_output=True, text=True, encoding="utf-8",
            )
            if validacao.returncode != 0:
                raise RuntimeError(f"validação reprovou:\n{validacao.stdout[-800:]}")

            resumos.append(resumo)
            log.info("%s OK: %d municípios, %d setores, %.0f MB, %.0f s",
                     sigla, resumo["municipios"], resumo["setores_nos_arquivos"],
                     resumo["bytes"] / 1e6, resumo["segundos"])

        except Exception as erro:
            quebradas.append((sigla, str(erro)))
            log.error("%s FALHOU: %s", sigla, erro)

    duracao = time.time() - inicio
    municipios = sum(r["municipios"] for r in resumos)
    setores = sum(r["setores_nos_arquivos"] for r in resumos)
    tamanho = sum(r["bytes"] for r in resumos)

    print()
    print("=" * 62)
    print(f"{'UF':4} {'munic.':>7} {'setores':>9} {'MB':>8} {'seg':>6}")
    print("-" * 62)
    for r in sorted(resumos, key=lambda x: x["uf"]):
        print(f"{r['uf']:4} {r['municipios']:>7} {r['setores_nos_arquivos']:>9} "
              f"{r['bytes'] / 1e6:>8.1f} {r['segundos']:>6.0f}")
    print("-" * 62)
    print(f"{'TOT':4} {municipios:>7} {setores:>9} {tamanho / 1e6:>8.1f} "
          f"{duracao:>6.0f}")
    print("=" * 62)

    if quebradas:
        print(f"\n{len(quebradas)} UF(s) com falha:")
        for sigla, erro in quebradas:
            print(f"  {sigla}: {erro[:200]}")
        return 1

    print(f"\n{len(resumos)} UF(s) geradas e validadas em {duracao / 60:.1f} min")
    if municipios != 5570:
        print(f"ATENÇÃO: {municipios} municípios, esperado 5.570 no Brasil")
    return 0


if __name__ == "__main__":
    sys.exit(main())

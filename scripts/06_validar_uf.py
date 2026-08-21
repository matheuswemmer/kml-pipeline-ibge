"""06 — Valida os KML gerados de uma UF contra a malha e a base nacional.

Uso:
    python scripts/06_validar_uf.py --uf MA

Relê todos os arquivos do disco e confronta com as fontes. É a rede de
proteção do projeto: os 5.494 arquivos herdados passaram meses com o schema
desalinhado porque ninguém releu a saída.

Cinco conferências:
  1. cobertura      — um arquivo por município da malha, nem mais nem menos
  2. reconciliação  — todo setor da malha está em exatamente um arquivo
  3. chave          — CD_SETOR com 15 dígitos, sem duplicata
  4. nulos          — a ausência no KML bate exatamente com a do Parquet
  5. valores        — os números no KML batem com os do Parquet

As conferências 4 e 5 são as que pegam corrupção no caminho de escrita: se
uma coluna se deslocar, ou se um nulo virar zero, elas acusam.
"""

import argparse
import glob
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import sources  # noqa: E402
from kmlpipe import logging_setup, lote, paths  # noqa: E402

TOLERANCIA = 0.01  # os KML guardam texto; comparar float com folga de 1 centavo


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uf", required=True)
    args = p.parse_args()

    log = logging_setup.setup("validar")
    sigla = args.uf.upper()
    codigos = {v: k for k, v in sources.UFS.items()}
    if sigla not in codigos:
        log.error("UF desconhecida: %s", sigla)
        return 1
    prefixo = codigos[sigla]

    arquivos = sorted(glob.glob(str(paths.OUTPUT / sigla / "*.kml")))
    if not arquivos:
        log.error("nenhum KML em output/%s — rode 05_gerar_lote.py --uf %s",
                  sigla, sigla)
        return 1

    malha = lote.preparar_malha(sigla)
    base, colunas = lote.carregar_indicadores(prefixo)
    log.info("lendo %d arquivo(s) de %s", len(arquivos), sigla)

    partes = []
    for caminho in arquivos:
        g = gpd.read_file(caminho, engine="pyogrio")
        g["_arquivo"] = Path(caminho).name
        partes.append(g.drop(columns="geometry"))
    lidos = pd.concat(partes, ignore_index=True)
    lidos["CD_SETOR"] = lidos["CD_SETOR"].astype(str).str.zfill(15)

    erros: list[str] = []

    # 1. cobertura
    municipios_malha = set(malha["CD_MUN"])
    municipios_lidos = set(lidos["CD_MUN"].astype(str))
    if municipios_malha != municipios_lidos:
        erros.append(
            f"cobertura: {len(municipios_malha - municipios_lidos)} município(s) "
            f"sem arquivo, {len(municipios_lidos - municipios_malha)} a mais"
        )
    if len(arquivos) != len(municipios_malha):
        erros.append(f"cobertura: {len(arquivos)} arquivos para "
                     f"{len(municipios_malha)} municípios")

    # 2. reconciliação
    if len(lidos) != len(malha):
        erros.append(f"reconciliação: {len(lidos)} setores nos arquivos, "
                     f"{len(malha)} na malha")

    # 3. chave
    if lidos["CD_SETOR"].duplicated().any():
        dups = lidos.loc[lidos["CD_SETOR"].duplicated(), "CD_SETOR"].head(3).tolist()
        erros.append(f"chave: CD_SETOR duplicado, ex.: {dups}")
    if not lidos["CD_SETOR"].str.fullmatch(r"\d{15}").all():
        erros.append("chave: CD_SETOR fora do padrão de 15 dígitos")
    if set(lidos["CD_SETOR"]) != set(malha["CD_SETOR"]):
        erros.append("chave: conjunto de setores difere da malha")

    # 4 e 5. nulos e valores, coluna a coluna, contra o Parquet
    esperado = base.reindex(lidos["CD_SETOR"])
    lidos = lidos.set_index("CD_SETOR")

    for col in colunas:
        if col not in lidos.columns:
            erros.append(f"valores: coluna {col} ausente nos KML")
            continue

        obtido = pd.to_numeric(lidos[col], errors="coerce")
        alvo = pd.to_numeric(esperado[col], errors="coerce")
        alvo.index = obtido.index

        nulos_obtidos, nulos_alvo = int(obtido.isna().sum()), int(alvo.isna().sum())
        if nulos_obtidos != nulos_alvo:
            erros.append(
                f"nulos: {col} tem {nulos_obtidos} vazios no KML e "
                f"{nulos_alvo} no Parquet — ausência pode ter virado zero"
            )

        ambos = obtido.notna() & alvo.notna()
        divergentes = int(((obtido[ambos] - alvo[ambos]).abs() > TOLERANCIA).sum())
        if divergentes:
            erros.append(f"valores: {col} diverge em {divergentes} setor(es)")

    print()
    print(f"UF                {sigla}")
    print(f"arquivos          {len(arquivos)}")
    print(f"municípios        {len(municipios_malha)}")
    print(f"setores           {len(lidos)}")
    print(f"indicadores       {len(colunas)}")
    zerados = {c: int((pd.to_numeric(lidos[c], errors='coerce') == 0).sum())
               for c in ("pct_via_pavimentada", "pct_arborizacao")
               if c in lidos.columns}
    vazios = {c: int(pd.to_numeric(lidos[c], errors='coerce').isna().sum())
              for c in zerados}
    for c in zerados:
        print(f"  {c:24} vazios {vazios[c]:6} | zero real {zerados[c]:6}")

    if erros:
        print(f"\n{len(erros)} PROBLEMA(S):")
        for e in erros:
            print(f"  - {e}")
        return 1

    print("\nok: cobertura, reconciliação, chave, nulos e valores conferem")
    return 0


if __name__ == "__main__":
    sys.exit(main())

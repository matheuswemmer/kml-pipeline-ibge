"""08 — Prepara a publicação no S3 preservando os nomes já em uso.

Uso:
    python scripts/08_publicar.py
    python scripts/08_publicar.py --copiar     # copia em vez de hardlink

Os arquivos no bucket têm nomes opacos (`AC/Acrelandia/1755867329246.kml`),
gerados por timestamp no upload original e registrados em `klm_documents` no
Supabase. Subir os arquivos novos com os nomes do IBGE criaria 5.570 objetos
ao lado dos 5.494 existentes, e o site continuaria servindo os antigos.

Este script monta `publicacao/` espelhando exatamente as chaves do bucket, de
modo que um único `aws s3 sync` sobrescreva cada arquivo no lugar. Nenhum link
do site muda.

O script NÃO envia nada e NÃO escreve no banco: ele prepara a árvore e gera o
SQL para você revisar e executar.
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kmlpipe import logging_setup, paths  # noqa: E402

EXPORT = "klm_documents.json"
DESTINO = ROOT / "publicacao"
SQL = "atualizar_banco.sql"


def pasta_cidade(cidade: str) -> str:
    """Mesma transformação usada na carga original.

    Conferida contra as 5.494 linhas do banco, sem divergência: remove acento,
    remove apóstrofo, espaço vira underscore.
    """
    s = "".join(c for c in unicodedata.normalize("NFD", cidade)
                if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "_", s.replace("'", "").replace("`", "").strip())


def _sql_txt(valor: str) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--copiar", action="store_true",
                   help="copiar arquivos em vez de criar hardlink")
    args = p.parse_args()

    log = logging_setup.setup("publicar")

    export = paths.INTERIM / EXPORT
    if not export.exists():
        log.error("%s não existe — exporte klm_documents do Supabase antes",
                  export)
        return 1

    banco = json.loads(export.read_text(encoding="utf-8"))
    por_codigo = {}
    for linha in banco:
        m = re.search(r"\((\d{7})\)", linha["name"])
        if m:
            por_codigo[m.group(1)] = linha

    gerados = {}
    for caminho in paths.OUTPUT.glob("*/*.kml"):
        m = re.search(r"_(\d{7})_setores_CD2022\.kml$", caminho.name)
        if m:
            gerados[m.group(1)] = caminho

    casados = sorted(set(por_codigo) & set(gerados))
    novos = sorted(set(gerados) - set(por_codigo))
    orfaos = sorted(set(por_codigo) - set(gerados))

    if orfaos:
        log.error("%d linha(s) do banco sem arquivo gerado: %s",
                  len(orfaos), orfaos[:5])
        return 1

    log.info("%d arquivo(s) para sobrescrever, %d novo(s)", len(casados), len(novos))

    if DESTINO.exists():
        log.error("%s já existe — remova antes de regerar", DESTINO)
        return 1

    def colocar(origem: Path, chave: str) -> None:
        alvo = DESTINO / chave
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if args.copiar:
            alvo.write_bytes(origem.read_bytes())
        else:
            os.link(origem, alvo)  # mesmo volume: não duplica os 3,2 GB

    updates, inserts = [], []

    for codigo in casados:
        linha = por_codigo[codigo]
        origem = gerados[codigo]
        colocar(origem, linha["file_path"])
        updates.append(
            f"update klm_documents set file_size = {origem.stat().st_size}, "
            f"updated_at = now() where id = {_sql_txt(linha['id'])};"
        )

    # Os 76 municípios sem linha no banco ganham chave no mesmo padrão. O
    # timestamp é gerado agora, em milissegundos, como na carga original.
    base_ms = int(time.time() * 1000)
    for i, codigo in enumerate(novos):
        origem = gerados[codigo]
        uf = origem.parent.name
        amostra = gpd.read_file(origem, engine="pyogrio", max_features=1)
        cidade = str(amostra["NM_MUN"].iloc[0])
        chave = f"{uf}/{pasta_cidade(cidade)}/{base_ms + i}.kml"
        colocar(origem, chave)
        inserts.append(
            "insert into klm_documents "
            "(id, name, city, state, file_path, file_size, type, "
            "download_count, view_count, created_at, updated_at) values ("
            f"{_sql_txt(uuid.uuid4())}, {_sql_txt(f'{cidade} ({codigo})')}, "
            f"{_sql_txt(cidade)}, {_sql_txt(uf)}, {_sql_txt(chave)}, "
            f"{origem.stat().st_size}, 'municipal', 0, 0, now(), now());"
        )

    destino_sql = paths.INTERIM / SQL
    destino_sql.write_text(
        "-- Gerado por scripts/08_publicar.py. Revise antes de executar.\n"
        "-- Rode DEPOIS de concluir o upload: o banco passa a refletir\n"
        "-- arquivos que precisam já estar no bucket.\n\n"
        f"-- {len(updates)} arquivos substituídos\n" + "\n".join(updates) +
        f"\n\n-- {len(inserts)} municípios novos\n" + "\n".join(inserts) + "\n",
        encoding="utf-8",
    )

    total = sum(f.stat().st_size for f in DESTINO.rglob("*.kml"))
    print()
    print(f"árvore pronta       {DESTINO}")
    print(f"  substituídos      {len(casados)}")
    print(f"  novos             {len(novos)}")
    print(f"  total             {len(casados) + len(novos)} arquivos, "
          f"{total / 1e9:.2f} GB")
    print(f"SQL para o banco    {destino_sql}")
    print()
    print("Para enviar (confira com --dryrun antes):")
    print("  aws s3 sync publicacao/ s3://SEU-BUCKET/ \\")
    print('      --content-type "application/vnd.google-earth.kml+xml"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

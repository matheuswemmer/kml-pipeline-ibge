"""Lê o cabeçalho do CSV dentro de cada ZIP do IBGE sem baixar o arquivo.

Um ZIP começa com o *local file header* seguido do fluxo deflate. Pedindo só
os primeiros KB via HTTP Range e descomprimindo o que chegou, dá para ler a
primeira linha do CSV — o suficiente para saber quais colunas o arquivo tem.
Isso permite validar o catálogo inteiro (500 MB) em segundos.
"""

from __future__ import annotations

import json
import logging
import struct
import zlib

import requests

from . import paths

log = logging.getLogger(__name__)

CACHE = paths.INTERIM / "_headers_csv.json"
PREFIXO = 400_000  # bytes; sobra folga para cabeçalhos de 400+ colunas


def _ler_prefixo(url: str) -> tuple[str, str, int]:
    r = requests.get(url, headers={"Range": f"bytes=0-{PREFIXO - 1}"}, timeout=120)
    r.raise_for_status()
    raw = r.content

    if raw[:4] != b"PK\x03\x04":
        raise ValueError(f"não parece um ZIP: {url}")

    metodo = struct.unpack("<H", raw[8:10])[0]
    fnlen = struct.unpack("<H", raw[26:28])[0]
    exlen = struct.unpack("<H", raw[28:30])[0]
    nome = raw[30:30 + fnlen].decode("cp437")
    dados = raw[30 + fnlen + exlen:]

    if metodo == 8:
        # decompressobj tolera o fluxo cortado no meio; só precisamos da 1ª linha
        dados = zlib.decompressobj(-15).decompress(dados)
    elif metodo != 0:
        raise ValueError(f"método de compressão {metodo} não suportado: {url}")

    if b"\n" not in dados:
        raise ValueError(f"cabeçalho não coube em {PREFIXO} bytes: {url}")

    linha = dados.split(b"\n", 1)[0].decode("latin-1").strip()

    total = 0
    faixa = r.headers.get("content-range", "")
    if "/" in faixa:
        total = int(faixa.rsplit("/", 1)[-1])

    return nome, linha, total


def obter(tabelas: dict, *, forcar: bool = False) -> dict:
    """Devolve {tabela: {arquivo_csv, url, bytes, colunas}}, usando cache."""
    cache = {}
    if CACHE.exists() and not forcar:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    faltando = [k for k in tabelas if k not in cache or "bytes" not in cache[k]]
    for chave in faltando:
        url = tabelas[chave][0]
        nome, linha, total = _ler_prefixo(url)
        cache[chave] = {
            "arquivo_csv": nome,
            "url": url,
            "bytes": total,
            "colunas": [c.strip().strip('"').lstrip("\ufeff") for c in linha.split(";")],
        }
        log.info("cabeçalho lido: %-20s %4d colunas  (%.1f MB)",
                 chave, len(cache[chave]["colunas"]), total / 1e6)

    if faltando:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

    return cache

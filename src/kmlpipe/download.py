"""Download idempotente de arquivos do IBGE.

Princípios (herdados do README do projeto anterior):
  - nunca modificar o arquivo original;
  - toda execução é reproduzível e registrada;
  - re-executar não rebaixa o que já está íntegro.

O manifesto (`data/raw/manifest.json`) guarda tamanho e sha256 de cada
arquivo baixado. Uma segunda execução compara o `content-length` do servidor
com o que está em disco e pula o download quando bate.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import requests
from tqdm import tqdm

from . import paths

log = logging.getLogger(__name__)

MANIFESTO = paths.RAW / "manifest.json"
CHUNK = 1024 * 512
TIMEOUT = 120


def _carregar_manifesto() -> dict:
    if MANIFESTO.exists():
        return json.loads(MANIFESTO.read_text(encoding="utf-8"))
    return {}


def _salvar_manifesto(dados: dict) -> None:
    MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
    MANIFESTO.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(CHUNK), b""):
            h.update(bloco)
    return h.hexdigest()


def tamanho_remoto(url: str) -> int | None:
    """Content-length do servidor, ou None se ele não informar."""
    try:
        r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        tamanho = r.headers.get("content-length")
        return int(tamanho) if tamanho else None
    except requests.RequestException as erro:
        log.warning("HEAD falhou em %s: %s", url, erro)
        return None


def baixar(url: str, destino: Path, *, forcar: bool = False) -> Path:
    """Baixa `url` para `destino`, pulando se o arquivo já estiver íntegro.

    A escrita é atômica: grava num `.part` e só renomeia no fim, para que uma
    interrupção nunca deixe um arquivo truncado passando por completo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    esperado = tamanho_remoto(url)

    if destino.exists() and not forcar:
        atual = destino.stat().st_size
        if esperado is None or atual == esperado:
            log.info("já em disco, pulando: %s (%.1f MB)", destino.name, atual / 1e6)
            return destino
        log.warning(
            "tamanho divergente em %s (disco %s, servidor %s) — rebaixando",
            destino.name, atual, esperado,
        )

    parcial = destino.with_suffix(destino.suffix + ".part")
    log.info("baixando %s", url)

    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or None
        with parcial.open("wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024,
            desc=destino.name[:40], leave=False,
        ) as barra:
            for bloco in r.iter_content(chunk_size=CHUNK):
                f.write(bloco)
                barra.update(len(bloco))

    parcial.replace(destino)

    manifesto = _carregar_manifesto()
    manifesto[destino.name] = {
        "url": url,
        "bytes": destino.stat().st_size,
        "sha256": sha256(destino),
    }
    _salvar_manifesto(manifesto)

    log.info("ok: %s (%.1f MB)", destino.name, destino.stat().st_size / 1e6)
    return destino

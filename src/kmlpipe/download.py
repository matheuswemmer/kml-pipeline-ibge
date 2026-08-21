"""Download idempotente de arquivos do IBGE, com procedência auditável.

Princípios (herdados do README do projeto anterior):
  - nunca modificar o arquivo original;
  - toda execução é reproduzível e registrada;
  - re-executar não rebaixa o que já está íntegro.

O manifesto (`data/raw/manifest.json`) responde "de onde veio este arquivo e
como sei que ele é o do IBGE?". Ele NÃO tenta lembrar quem colocou o arquivo
ali — essa informação não é recuperável e um rótulo errado é pior que nenhum.
O que ele registra é o grau de conferência efetivamente feito:

  nao_conferido    o arquivo está em disco e nada foi comparado
  tamanho          o byte count bate com o content-length do servidor
  sha256           baixamos de novo e o hash é idêntico ao do servidor

Só `sha256` é prova. `tamanho` é indício forte e barato; é o que a rotina de
download usa para decidir se pula.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import requests
from tqdm import tqdm

from . import paths

log = logging.getLogger(__name__)

MANIFESTO = paths.RAW / "manifest.json"
CHUNK = 1024 * 512
TIMEOUT = 120

NAO_CONFERIDO = "nao_conferido"
POR_TAMANHO = "tamanho"
POR_SHA256 = "sha256"

# Ordem de força: nunca rebaixar uma conferência já registrada.
FORCA = {NAO_CONFERIDO: 0, POR_TAMANHO: 1, POR_SHA256: 2}


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


def _registrar(destino: Path, url: str, conferencia: str) -> None:
    """Grava a procedência, sem nunca rebaixar uma conferência já registrada."""
    manifesto = _carregar_manifesto()
    anterior = manifesto.get(destino.name, {})

    if FORCA.get(anterior.get("conferencia"), -1) > FORCA[conferencia]:
        conferencia = anterior["conferencia"]

    manifesto[destino.name] = {
        "url": url,
        "bytes": destino.stat().st_size,
        "sha256": anterior.get("sha256") or sha256(destino),
        "conferencia": conferencia,
        "registrado_em": datetime.now().isoformat(timespec="seconds"),
    }
    _salvar_manifesto(manifesto)


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
            # Registra mesmo pulando: um arquivo pode ter chegado aqui por fora
            # (cópia manual, download anterior) e ficaria sem procedência.
            _registrar(
                destino, url,
                POR_TAMANHO if esperado is not None else NAO_CONFERIDO,
            )
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
    _registrar(destino, url, POR_TAMANHO)

    log.info("ok: %s (%.1f MB)", destino.name, destino.stat().st_size / 1e6)
    return destino


def verificar(destino: Path, url: str) -> bool:
    """Rebaixa o arquivo em memória e compara o sha256 com o de disco.

    É a única prova de que o arquivo local é o que o IBGE serve. Custa uma
    transferência inteira, então roda sob demanda, não a cada execução.
    """
    if not destino.exists():
        log.error("não existe em disco: %s", destino)
        return False

    local = sha256(destino)
    h = hashlib.sha256()
    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        for bloco in r.iter_content(chunk_size=CHUNK):
            h.update(bloco)
    remoto = h.hexdigest()

    if local == remoto:
        _registrar(destino, url, POR_SHA256)
        log.info("sha256 confere: %s (%s…)", destino.name, local[:16])
        return True

    log.error("sha256 DIVERGE em %s | disco=%s… servidor=%s…",
              destino.name, local[:16], remoto[:16])
    manifesto = _carregar_manifesto()
    manifesto.setdefault(destino.name, {})["conferencia"] = "DIVERGENTE"
    _salvar_manifesto(manifesto)
    return False

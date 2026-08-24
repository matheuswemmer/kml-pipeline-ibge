"""Geração em lote dos KML municipais de uma UF.

O ganho de tempo vem de fazer uma vez o que antes era feito por município:
ler a malha, unir setores partidos e reprojetar. Sobra, por arquivo, apenas
recortar, escrever, enxugar e validar.

O manifesto por UF (`output/<UF>/_manifesto.json`) permite retomar de onde
parou. Sem ele, uma queda no meio de São Paulo obrigaria a refazer tudo.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from . import exportar, paths

log = logging.getLogger(__name__)

PARQUET = "indicadores_br.parquet"
MANIFESTO = "_manifesto.json"
CHAVE = "cd_setor"


def apelido(texto: str) -> str:
    """Nome de arquivo no padrão do IBGE: minúsculo, sem acento, com _."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


def caminho_saida(sigla: str, cod_mun: str, nome_mun: str, ext: str = ".kml") -> Path:
    return paths.OUTPUT / sigla / f"{apelido(nome_mun)}_{cod_mun}_setores_CD2022{ext}"


def carregar_indicadores(uf_prefixo: str, somente: list[str] | None = None,
                         ) -> tuple[pd.DataFrame, list[str]]:
    """Fatia a base nacional pela UF e devolve (tabela indexada, colunas).

    `somente` restringe as colunas que vão para o KML, na ordem em que foi
    passada — é ela que define a ordem dos campos no `<Schema>`. A base
    nacional continua guardando os 32; escolher um subconjunto não exige
    recalcular nada.
    """
    caminho = paths.PROCESSED / PARQUET
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho.name} não existe — rode scripts/04_base_nacional.py"
        )

    base = pd.read_parquet(caminho)
    base = base[base[CHAVE].str.startswith(uf_prefixo)]

    if somente is None:
        colunas = [c for c in base.columns if c != CHAVE]
    else:
        faltando = [c for c in somente if c not in base.columns]
        if faltando:
            raise KeyError(f"indicadores inexistentes na base: {faltando}")
        colunas = list(somente)
        base = base[[CHAVE] + colunas]

    return base.set_index(CHAVE), colunas


def preparar_malha(sigla: str):
    """Lê, une setores partidos e reprojeta — uma vez para a UF inteira."""
    gpkg = paths.RAW / f"{sigla}_setores_CD2022.gpkg"
    if not gpkg.exists():
        raise FileNotFoundError(
            f"{gpkg.name} não está em data/raw — rode 01_download.py --uf {sigla}"
        )

    malha = exportar.carregar_malha(gpkg)
    malha = exportar.reparar_geometrias(malha)
    malha = exportar.normalizar_malha(malha)
    malha = exportar.reprojetar(malha)

    sem_mun = malha["CD_MUN"].isna() | (malha["CD_MUN"].astype(str).str.strip() == "")
    if sem_mun.any():
        # Decisão do projeto: descartar. O produto busca por município, então
        # um setor sem município não teria como ser encontrado. Registrado
        # aqui para não sumir em silêncio.
        log.warning("descartando %d setor(es) sem CD_MUN: %s",
                    int(sem_mun.sum()),
                    malha.loc[sem_mun, "CD_SETOR"].head(5).tolist())
        malha = malha[~sem_mun]

    return malha


def _ler_manifesto(sigla: str) -> dict:
    caminho = paths.OUTPUT / sigla / MANIFESTO
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {}


def _salvar_manifesto(sigla: str, dados: dict) -> None:
    caminho = paths.OUTPUT / sigla / MANIFESTO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False),
                       encoding="utf-8")


def _tarefa(args):
    """Executado no worker: gera um município. Devolve (cod, stats|erro)."""
    grupo, indicadores, destino, colunas, de_entorno = args
    try:
        return destino.name, exportar.gerar_municipio(
            grupo, indicadores, destino, colunas, de_entorno
        ), None
    except Exception as erro:  # pragma: no cover - caminho de falha
        return destino.name, None, f"{type(erro).__name__}: {erro}"


def gerar_uf(sigla: str, prefixo: str, *, somente: list[str] | None = None,
             de_entorno: set[str] | None = None,
             refazer: bool = False, processos: int = 1) -> dict:
    """Gera os KML de todos os municípios de uma UF.

    `prefixo` é o código de dois dígitos da UF (ex.: "21" para MA), usado para
    fatiar a base nacional. Vem de config/sources.py, pelo chamador.
    `somente` escolhe quais indicadores vão para o arquivo.
    """
    inicio = time.time()

    malha = preparar_malha(sigla)
    indicadores, colunas = carregar_indicadores(prefixo, somente)
    log.info("%s: %d setores na malha, %d na base de indicadores",
             sigla, len(malha), len(indicadores))

    manifesto = _ler_manifesto(sigla)
    grupos = list(malha.groupby("CD_MUN", sort=True))

    pendentes = []
    pulados = 0
    for cod_mun, grupo in grupos:
        destino = caminho_saida(sigla, cod_mun, grupo["NM_MUN"].iloc[0])
        if destino.exists() and destino.name in manifesto and not refazer:
            pulados += 1
            continue
        pendentes.append((grupo, indicadores, destino, colunas,
                          de_entorno or set()))

    if pulados:
        log.info("%d município(s) já gerados, pulando", pulados)
    log.info("gerando %d município(s) com %d processo(s)", len(pendentes), processos)

    falhas: list[str] = []
    feitos = 0

    def registrar(nome, stats, erro):
        nonlocal feitos
        if erro:
            falhas.append(f"{nome}: {erro}")
            log.error("falhou %s: %s", nome, erro)
            return
        manifesto[nome] = stats
        feitos += 1
        if feitos % 25 == 0:
            log.info("  %d/%d", feitos, len(pendentes))

    if processos > 1:
        with ProcessPoolExecutor(max_workers=processos) as pool:
            futuros = [pool.submit(_tarefa, a) for a in pendentes]
            for fut in as_completed(futuros):
                registrar(*fut.result())
    else:
        for args in pendentes:
            registrar(*_tarefa(args))

    _salvar_manifesto(sigla, manifesto)

    setores_gerados = sum(m["setores"] for m in manifesto.values())
    bytes_totais = sum(m["bytes"] for m in manifesto.values())
    duracao = time.time() - inicio

    resumo = {
        "uf": sigla,
        "municipios": len(manifesto),
        "setores_na_malha": len(malha),
        "setores_nos_arquivos": setores_gerados,
        "bytes": bytes_totais,
        "falhas": falhas,
        "segundos": round(duracao, 1),
    }

    log.info("%s: %d municípios, %d setores, %.1f MB em %.0f s",
             sigla, resumo["municipios"], setores_gerados,
             bytes_totais / 1e6, duracao)
    if falhas:
        log.error("%d falha(s)", len(falhas))
    return resumo

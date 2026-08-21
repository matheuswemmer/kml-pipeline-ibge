"""Junta geometria e indicadores e escreve o KMZ.

A geometria vem do GeoPackage oficial por UF, não dos KMZ: os KMZ do IBGE
guardam os atributos numa tabela HTML dentro de `<description>`, e foi o
parsing posicional desse HTML que corrompeu o arquivo herdado de Joinville.

Reprojeção é obrigatória. O GeoPackage do IBGE está em EPSG:4674 (SIRGAS
2000) e KML exige EPSG:4326 (WGS 84). Sem a conversão explícita os polígonos
saem deslocados no Google Earth.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

log = logging.getLogger(__name__)

CRS_KML = "EPSG:4326"

# Colunas de contexto da malha que vão junto, para o setor ser identificável
# sem consultar outra base.
CONTEXTO = [
    "CD_SETOR", "NM_MUN", "CD_MUN", "NM_BAIRRO", "NM_DIST",
    "SITUACAO", "AREA_KM2",
]


def carregar_malha(gpkg, cod_mun: str | None = None) -> gpd.GeoDataFrame:
    malha = gpd.read_file(gpkg, engine="pyogrio")
    log.info("malha: %d setores, CRS %s", len(malha), malha.crs)

    if cod_mun:
        malha = malha[malha["CD_MUN"] == cod_mun].copy()
        log.info("filtrado para o município %s: %d setores", cod_mun, len(malha))
        if malha.empty:
            raise ValueError(f"nenhum setor com CD_MUN={cod_mun}")

    malha["CD_SETOR"] = malha["CD_SETOR"].astype(str).str.strip().str.zfill(15)
    return malha


def juntar(malha: gpd.GeoDataFrame, indicadores: pd.DataFrame,
           ) -> gpd.GeoDataFrame:
    """Junta pela esquerda: a malha manda, atributo ausente vira nulo.

    Left join é deliberado. O bloco de entorno só foi aplicado em parte dos
    setores; um inner join sumiria com os setores não pesquisados, e um
    fillna(0) inventaria bairro sem árvore e sem pavimento.
    """
    antes = len(malha)
    saida = malha.merge(
        indicadores, how="left", left_on="CD_SETOR", right_index=True,
    )
    if len(saida) != antes:
        raise RuntimeError(
            f"o join duplicou linhas: {antes} -> {len(saida)}. "
            "Provável cd_setor repetido em alguma tabela."
        )

    sem_dado = int(saida[indicadores.columns].isna().all(axis=1).sum())
    if sem_dado:
        log.warning("%d de %d setores sem nenhum indicador", sem_dado, antes)
    return saida


def escrever_kmz(dados: gpd.GeoDataFrame, destino, colunas: list[str]) -> None:
    """Escreve KMZ ou KML em EPSG:4326, conforme a extensão do destino.

    KMZ é o KML zipado — mesmo conteúdo, ~10x menor. O Google Earth abre os
    dois; o .kml serve para inspecionar o XML a olho nu.
    """
    presentes = [c for c in CONTEXTO if c in dados.columns]
    saida = dados[presentes + colunas + ["geometry"]].copy()

    if saida.crs is None:
        raise ValueError("a malha veio sem CRS definido")
    if saida.crs.to_string() != CRS_KML:
        log.info("reprojetando %s -> %s", saida.crs.to_string(), CRS_KML)
        saida = saida.to_crs(CRS_KML)

    # O LIBKML usa a coluna `Name` como <name> do Placemark, que é o rótulo
    # exibido no Google Earth.
    saida.insert(0, "Name", saida["CD_SETOR"])

    destino.parent.mkdir(parents=True, exist_ok=True)
    saida.to_file(destino, driver="LIBKML")
    log.info("%s escrito: %s (%d feições, %.1f MB)",
             destino.suffix.lstrip(".").upper(), destino,
             len(saida), destino.stat().st_size / 1e6)


def validar(destino, esperado: int, colunas: list[str]) -> None:
    """Relê o arquivo escrito e confere contagem, chave e colunas.

    Nenhum export sai sem esta conferência: o arquivo herdado passou meses
    com o schema desalinhado justamente porque ninguém releu a saída.
    """
    lido = gpd.read_file(destino, engine="pyogrio")

    if len(lido) != esperado:
        raise AssertionError(f"{destino.name}: {len(lido)} feições, esperado {esperado}")

    cd = lido["CD_SETOR"].astype(str)
    if not cd.str.fullmatch(r"\d{15}").all():
        ruins = cd[~cd.str.fullmatch(r"\d{15}")].head(3).tolist()
        raise AssertionError(f"{destino.name}: CD_SETOR inválido, ex.: {ruins}")
    if cd.duplicated().any():
        raise AssertionError(f"{destino.name}: CD_SETOR duplicado")

    ausentes = [c for c in colunas if c not in lido.columns]
    if ausentes:
        raise AssertionError(f"{destino.name}: colunas perdidas na escrita: {ausentes}")

    log.info("validado: %d feições, CD_SETOR íntegro, %d indicadores presentes",
             len(lido), len(colunas))

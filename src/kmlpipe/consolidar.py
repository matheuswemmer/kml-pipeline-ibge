"""Lê os CSV do IBGE e calcula os indicadores curados por setor censitário.

Dois cuidados que o formato do IBGE exige:

1. **A coluna-chave tem quatro grafias** (`CD_SETOR`, `CD_setor`, `setor`,
   `COD_SETOR_M22FINAL`). O nome real vem do cache de cabeçalhos, nunca de
   suposição. Tudo é renomeado para `cd_setor` logo na leitura.

2. **Valores suprimidos.** O IBGE marca com `X` as células omitidas por sigilo
   estatístico. Convertidas para `NaN`, nunca para zero: um setor com renda
   suprimida não é um setor de renda zero.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import pandas as pd

from . import paths

log = logging.getLogger(__name__)

CHAVE = "cd_setor"


def _caminho_zip(url: str) -> Path:
    from urllib.parse import unquote
    return paths.RAW / unquote(url.rsplit("/", 1)[-1])


def ler_tabela(chave_tabela: str, url: str, cabecalho: dict,
               variaveis: list[str], *, cod_mun: str | None = None) -> pd.DataFrame:
    """Lê só as colunas pedidas de uma tabela, opcionalmente de um município.

    `variaveis` usa os códigos canônicos em maiúsculas; a grafia real no CSV
    (que em `basico` é minúscula) é resolvida aqui.
    """
    caminho = _caminho_zip(url)
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho.name} não está em data/raw — rode 01_download.py --tabelas"
        )

    reais = {c.upper(): c for c in cabecalho["colunas"]}
    coluna_chave = cabecalho["colunas"][0]
    faltando = [v for v in variaveis if v.upper() not in reais]
    if faltando:
        raise KeyError(f"{chave_tabela}: variáveis ausentes no CSV: {faltando}")

    usar = [coluna_chave] + [reais[v.upper()] for v in variaveis]

    with zipfile.ZipFile(caminho) as zf:
        nome = zf.namelist()[0]
        with zf.open(nome) as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin-1", usecols=usar, dtype=str,
                low_memory=False,
            )

    df = df.rename(columns={coluna_chave: CHAVE})
    df[CHAVE] = df[CHAVE].str.strip().str.zfill(15)

    if cod_mun:
        df = df[df[CHAVE].str.startswith(cod_mun)]

    # Renomeia para o código canônico em maiúsculas e converte para número.
    renomear = {reais[v.upper()]: v.upper() for v in variaveis}
    df = df.rename(columns=renomear)

    suprimidos = 0
    for v in variaveis:
        col = v.upper()
        bruto = df[col].str.strip().str.replace(",", ".", regex=False)
        convertido = pd.to_numeric(bruto, errors="coerce")
        suprimidos += int((bruto.notna() & convertido.isna()).sum())
        df[col] = convertido

    if suprimidos:
        log.info("%s: %d célula(s) suprimida(s) pelo IBGE -> NaN",
                 chave_tabela, suprimidos)

    log.info("%-20s %6d setores, %d variáveis", chave_tabela, len(df), len(variaveis))
    return df.set_index(CHAVE)


def carregar(indicadores, tabelas: dict, cabecalhos: dict,
             *, cod_mun: str | None = None) -> pd.DataFrame:
    """Lê todas as tabelas necessárias e devolve um DataFrame por setor."""
    por_tabela: dict[str, set[str]] = {}
    for ind in indicadores:
        por_tabela.setdefault(ind.tabela, set()).update(
            v.upper() for v in ind.numerador
        )
        # O denominador pode vir de outra tabela: os percentuais de domicílio
        # usam V00001 (total), publicado em `domicilio1`, enquanto as
        # categorias estão em `domicilio2`.
        tabela_den = getattr(ind, "tabela_denominador", None) or ind.tabela
        por_tabela.setdefault(tabela_den, set()).update(
            v.upper() for v in ind.denominador
        )

    partes = []
    for nome, variaveis in por_tabela.items():
        url = tabelas[nome][0]
        partes.append(
            ler_tabela(nome, url, cabecalhos[nome], sorted(variaveis), cod_mun=cod_mun)
        )

    dados = pd.concat(partes, axis=1, join="outer")
    log.info("consolidado: %d setores, %d variáveis brutas",
             len(dados), dados.shape[1])
    return dados


def _soma(dados: pd.DataFrame, colunas: list[str]) -> pd.Series:
    """Soma tratando ausência como ausência: se tudo é NaN, o total é NaN."""
    presentes = [c for c in colunas if c in dados.columns]
    if not presentes:
        return pd.Series(pd.NA, index=dados.index, dtype="Float64")
    return dados[presentes].sum(axis=1, min_count=1)


def calcular(indicadores, dados: pd.DataFrame) -> pd.DataFrame:
    """Aplica as fórmulas declaradas em config/indicadores.py."""
    saida = pd.DataFrame(index=dados.index)

    for ind in indicadores:
        if ind.tipo in {"valor", "contagem"}:
            col = ind.numerador[0].upper()
            saida[ind.nome] = dados[col] if col in dados.columns else pd.NA

        elif ind.tipo == "percentual":
            num = _soma(dados, [v.upper() for v in ind.numerador])
            den = _soma(dados, [v.upper() for v in ind.denominador])
            # Denominador zero não é 0%: é ausência de base para o cálculo.
            saida[ind.nome] = (num / den.where(den > 0) * 100).round(2)

        elif ind.tipo == "derivado":
            if ind.nome == "renda_resp_per_capita_proxy":
                renda, resp = (v.upper() for v in ind.numerador)
                moradores = ind.denominador[0].upper()
                den = dados[moradores].where(dados[moradores] > 0)
                saida[ind.nome] = (dados[renda] * dados[resp] / den).round(2)
            else:
                raise NotImplementedError(f"derivado sem fórmula: {ind.nome}")

        else:
            raise ValueError(f"tipo desconhecido em {ind.nome}: {ind.tipo}")

    return saida

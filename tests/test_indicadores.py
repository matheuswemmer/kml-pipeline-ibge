"""Valida a curadoria contra o dicionário oficial do IBGE.

Roda com: python tests/test_indicadores.py
Sai com código 1 se qualquer indicador citar variável inexistente, apontar
para o arquivo errado ou tiver denominador incoerente.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config"))

import indicadores as I  # noqa: E402

DIRECOES = {"valoriza", "deprecia", "contexto"}
TIPOS = {"percentual", "valor", "contagem", "derivado"}
BASES = {"categorias", "total"}


def main() -> int:
    dic = pd.read_csv(ROOT / "docs" / "variaveis_origem.csv")
    onde = dict(zip(dic.variavel, dic.tabela))
    erros = []

    nomes = [ind.nome for ind in I.INDICADORES]
    duplicados = {n for n in nomes if nomes.count(n) > 1}
    if duplicados:
        erros.append(f"nomes de coluna duplicados: {duplicados}")

    for ind in I.INDICADORES:
        if ind.direcao not in DIRECOES:
            erros.append(f"{ind.nome}: direcao inválida {ind.direcao!r}")
        if ind.tipo not in TIPOS:
            erros.append(f"{ind.nome}: tipo inválido {ind.tipo!r}")
        if ind.base not in BASES:
            erros.append(f"{ind.nome}: base inválida {ind.base!r}")

        tabela_den = ind.tabela_denominador or ind.tabela
        alvos = ([(v, ind.tabela) for v in ind.numerador]
                 + [(v, tabela_den) for v in ind.denominador])
        for v, esperada in alvos:
            if v not in onde:
                erros.append(f"{ind.nome}: variável {v} não existe no IBGE")
            elif onde[v] != esperada:
                erros.append(
                    f"{ind.nome}: {v} está em {onde[v]!r}, "
                    f"mas o indicador declara {esperada!r}"
                )

        if ind.tipo == "percentual":
            if not ind.denominador:
                erros.append(f"{ind.nome}: percentual sem denominador")
            # Só o padrão "parte do todo" exige o numerador dentro do
            # denominador; com total independente isso não vale.
            if ind.base == "categorias" and not set(ind.numerador) <= set(ind.denominador):
                fora = set(ind.numerador) - set(ind.denominador)
                erros.append(
                    f"{ind.nome}: base='categorias' mas {sorted(fora)} "
                    f"está fora do denominador"
                )
        elif ind.tipo in {"valor", "contagem"}:
            if len(ind.numerador) != 1 or ind.denominador:
                erros.append(f"{ind.nome}: {ind.tipo} deve ter 1 variável e nenhum denominador")

    usadas = {v for ind in I.INDICADORES
              for v in list(ind.numerador) + list(ind.denominador)}
    tabelas = sorted({ind.tabela for ind in I.INDICADORES}
                     | {ind.tabela_denominador for ind in I.INDICADORES
                        if ind.tabela_denominador})

    print(f"indicadores      : {len(I.INDICADORES)}")
    print(f"variáveis usadas : {len(usadas)} de {len(dic)}")
    print(f"arquivos exigidos: {len(tabelas)} de 13 -> {tabelas}")

    if erros:
        print(f"\n{len(erros)} PROBLEMA(S):")
        for e in erros:
            print(f"  - {e}")
        return 1

    print("\nok: toda variável existe, está no arquivo declarado e o "
          "denominador é coerente")
    return 0


if __name__ == "__main__":
    sys.exit(main())

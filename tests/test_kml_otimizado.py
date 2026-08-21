"""Garante que o enxugamento do KML é puramente cosmético.

Roda com: python tests/test_kml_otimizado.py

`enxugar_kml()` reescreve o texto do arquivo removendo a indentação que o
driver LIBKML coloca dentro de `<coordinates>` e o sufixo `,0` de altitude.
É uma manipulação de texto sobre um arquivo já escrito — exatamente o tipo de
atalho que corrompe dados em silêncio. Estes testes existem para provar que
geometria e atributos atravessam intactos.
"""

import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kmlpipe import exportar  # noqa: E402

TOLERANCIA = 1e-9


def _amostra() -> gpd.GeoDataFrame:
    """Um polígono simples, um com buraco e um multipolígono."""
    com_buraco = Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        [[(1, 1), (1, 2), (2, 2), (2, 1)]],
    )
    multi = MultiPolygon([
        Polygon([(10, 10), (11, 10), (11, 11), (10, 11)]),
        Polygon([(20, 20), (21, 20), (21, 21), (20, 21)]),
    ])
    simples = Polygon([(5.1234567, 5.7654321), (6, 5), (6, 6), (5, 6)])

    return gpd.GeoDataFrame(
        {
            "Name": ["420910205000001", "420910205000004", "420910205000005"],
            "CD_SETOR": ["420910205000001", "420910205000004", "420910205000005"],
            "NM_MUN": ["Joinville", "Joinville", "Joinville"],
            "renda_resp_mediana": [8000.0, 6000.0, None],
            "pct_via_pavimentada": [100.0, 0.0, None],
            "geometry": [simples, com_buraco, multi],
        },
        crs=exportar.CRS_KML,
    )


def main() -> int:
    colunas = ["renda_resp_mediana", "pct_via_pavimentada"]
    falhas = []

    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "amostra.kml"
        exportar.escrever(_amostra(), destino, colunas)

        antes = gpd.read_file(destino, engine="pyogrio").sort_values("CD_SETOR")
        bruto, enxuto = exportar.enxugar_kml(destino)
        depois = gpd.read_file(destino, engine="pyogrio").sort_values("CD_SETOR")

        if enxuto >= bruto:
            falhas.append(f"o arquivo não encolheu: {bruto} -> {enxuto} bytes")

        texto = destino.read_text(encoding="utf-8")
        bloco = texto.split("<coordinates>")[1].split("</coordinates>")[0]
        if "\n" in bloco:
            falhas.append("sobrou quebra de linha dentro de <coordinates>")
        if any(v.count(",") > 1 for v in bloco.split()):
            falhas.append("sobrou altitude nas coordenadas")

        if len(antes) != len(depois):
            falhas.append(f"contagem mudou: {len(antes)} -> {len(depois)}")

        for coluna in ["CD_SETOR", "NM_MUN"]:
            if not (antes[coluna].values == depois[coluna].values).all():
                falhas.append(f"coluna {coluna} mudou no enxugamento")

        for coluna in colunas:
            a = pd.to_numeric(antes[coluna], errors="coerce")
            b = pd.to_numeric(depois[coluna], errors="coerce")
            if (a.isna().values != b.isna().values).any():
                falhas.append(f"nulos de {coluna} mudaram — ausência virou valor")
            elif not ((a.dropna().values - b.dropna().values) == 0).all():
                falhas.append(f"valores de {coluna} mudaram")

        for i, (ga, gb) in enumerate(zip(antes.geometry, depois.geometry)):
            if ga.geom_type != gb.geom_type:
                falhas.append(f"feição {i}: tipo {ga.geom_type} -> {gb.geom_type}")
            elif not ga.equals_exact(gb, TOLERANCIA):
                falhas.append(f"feição {i}: geometria alterada além de {TOLERANCIA}")

        print(f"amostra: {len(antes)} feições "
              f"({', '.join(antes.geometry.geom_type)})")
        print(f"tamanho: {bruto} -> {enxuto} bytes "
              f"({(1 - enxuto / bruto) * 100:.1f}% menor)")

    if falhas:
        print(f"\n{len(falhas)} PROBLEMA(S):")
        for f in falhas:
            print(f"  - {f}")
        return 1

    print("\nok: geometria, atributos e nulos intactos após o enxugamento")
    return 0


if __name__ == "__main__":
    sys.exit(main())

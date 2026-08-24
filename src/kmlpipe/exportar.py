"""Junta geometria e indicadores e escreve o KML por município.

A geometria vem do GeoPackage oficial por UF, não dos KMZ: os KMZ do IBGE
guardam os atributos numa tabela HTML dentro de `<description>`, e foi o
parsing posicional desse HTML que corrompeu o arquivo herdado de Joinville.

Reprojeção é obrigatória e fica separada da escrita: o GeoPackage está em
EPSG:4674 (SIRGAS 2000) e KML exige EPSG:4326 (WGS 84). Reprojetar a UF inteira
uma vez custa muito menos que reprojetar município a município.
"""

from __future__ import annotations

import logging
import re

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon

log = logging.getLogger(__name__)

CRS_KML = "EPSG:4326"

# Colunas de contexto da malha que vão junto, para o setor ser identificável
# sem consultar outra base.
CONTEXTO = [
    "CD_SETOR", "NM_MUN", "CD_MUN", "NM_BAIRRO", "NM_DIST",
    "SITUACAO", "AREA_KM2", "COBERTURA_IBGE", "description",
]

# Texto do campo COBERTURA_IBGE, em português leigo: quem abre o arquivo não
# precisa saber o que é "bloco de entorno" para entender por que faltam dados.
COBERTURA_COMPLETA = "Dados completos"
COBERTURA_SEM_ENTORNO = "IBGE não pesquisou a rua deste setor"
COBERTURA_VAZIA = "IBGE não divulgou dados deste setor"
COBERTURA_PARCIAL = "Dados parciais do IBGE"

_COORDS = re.compile(r"(<coordinates>)(.*?)(</coordinates>)", re.S)


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


def _apenas_poligonos(geom):
    """Descarta linhas e pontos que o reparo pode produzir."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        partes = []
        for parte in geom.geoms:
            if parte.geom_type == "Polygon":
                partes.append(parte)
            elif parte.geom_type == "MultiPolygon":
                partes.extend(parte.geoms)
        if partes:
            return MultiPolygon(partes) if len(partes) > 1 else partes[0]
    raise ValueError(f"reparo não produziu polígono: {geom.geom_type}")


def reparar_geometrias(malha: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Conserta geometrias inválidas da malha do IBGE.

    São raras — uma única em Santa Catarina, nenhuma no Maranhão ou em
    Rondônia — mas fatais: o driver LIBKML recusa a feição inteira e o
    município inteiro deixa de ser gerado. O caso de SC é um anel interno
    auto-intersectante em São José.

    Só a geometria inválida é tocada; as demais passam intactas.
    """
    invalidas = ~malha.geometry.is_valid
    if not invalidas.any():
        return malha

    afetados = malha.loc[invalidas, "NM_MUN"].unique().tolist()
    log.warning("reparando %d geometria(s) inválida(s) em %s",
                int(invalidas.sum()), afetados)

    area_antes = malha.loc[invalidas].geometry.area.sum()
    consertadas = malha.loc[invalidas, "geometry"].make_valid().apply(_apenas_poligonos)

    malha = malha.copy()
    malha.loc[invalidas, "geometry"] = consertadas

    area_depois = malha.loc[invalidas].geometry.area.sum()
    desvio = abs(area_depois - area_antes) / area_antes if area_antes else 0
    if desvio > 0.01:
        raise RuntimeError(
            f"o reparo alterou a área em {desvio:.1%} — geometria não confiável"
        )

    if not malha.geometry.is_valid.all():
        raise RuntimeError("ainda há geometria inválida depois do reparo")
    return malha


def normalizar_malha(malha: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Une num MultiPolygon os setores que a malha traz partidos em vários.

    O IBGE publica alguns setores como várias linhas Polygon, uma por parte —
    em Santa Catarina são 45 setores em 18 municípios (Balneário Camboriú é o
    caso mais visível). Sem unir, o KML sai com placemarks repetidos para o
    mesmo `CD_SETOR` e a validação de chave única falha.

    `AREA_KM2` já vem com a área total do setor em todas as partes, então
    manter o primeiro valor é correto — não somar.
    """
    repetidos = malha["CD_SETOR"].duplicated(keep=False)
    if not repetidos.any():
        return malha

    partidos = malha[repetidos]
    log.info("unindo %d setor(es) partido(s) em %d linha(s), %d município(s)",
             partidos["CD_SETOR"].nunique(), len(partidos),
             partidos["CD_MUN"].nunique())

    unidos = partidos.dissolve(by="CD_SETOR", aggfunc="first", as_index=False)
    saida = pd.concat([malha[~repetidos], unidos], ignore_index=True)

    if saida["CD_SETOR"].duplicated().any():
        raise RuntimeError("ainda há CD_SETOR duplicado depois de unir as partes")
    return gpd.GeoDataFrame(saida, geometry="geometry", crs=malha.crs)


def reprojetar(malha: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Leva a malha para EPSG:4326. Aplicar uma vez por UF, não por município."""
    if malha.crs is None:
        raise ValueError("a malha veio sem CRS definido")
    if malha.crs.to_string() == CRS_KML:
        return malha
    log.info("reprojetando %s -> %s", malha.crs.to_string(), CRS_KML)
    return malha.to_crs(CRS_KML)


def juntar(malha: gpd.GeoDataFrame, indicadores: pd.DataFrame) -> gpd.GeoDataFrame:
    """Junta pela esquerda: a malha manda, atributo ausente vira nulo.

    Left join é deliberado. O bloco de entorno só foi aplicado em parte dos
    setores — no Maranhão, em 48% deles. Um inner join sumiria com os setores
    não pesquisados, e um fillna(0) marcaria meio estado como sem árvore e sem
    pavimento, com aparência de dado válido.
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
    return saida


def marcar_cobertura(dados: gpd.GeoDataFrame, colunas: list[str],
                     de_entorno: set[str]) -> gpd.GeoDataFrame:
    """Cria COBERTURA_IBGE, dizendo em português por que faltam valores.

    Existe porque o LIBKML **omite o campo inteiro** quando o valor é nulo: no
    Google Earth o setor não pesquisado simplesmente aparece com menos linhas
    no balão, sem nenhuma pista do motivo. Um contador não resolveria — ele é
    nulo justamente nesses setores e sumiria junto. Só um campo de texto
    sempre preenchido sobrevive para explicar a ausência.
    """
    if not colunas:
        return dados

    nulos = dados[colunas].isna()
    entorno = [c for c in colunas if c in de_entorno]
    outros = [c for c in colunas if c not in de_entorno]

    tudo_nulo = nulos.all(axis=1)
    nada_nulo = ~nulos.any(axis=1)
    so_entorno_nulo = (
        nulos[entorno].all(axis=1) & ~nulos[outros].any(axis=1)
        if entorno and outros else pd.Series(False, index=dados.index)
    )

    dados = dados.copy()
    dados["COBERTURA_IBGE"] = COBERTURA_PARCIAL
    dados.loc[nada_nulo, "COBERTURA_IBGE"] = COBERTURA_COMPLETA
    dados.loc[so_entorno_nulo, "COBERTURA_IBGE"] = COBERTURA_SEM_ENTORNO
    dados.loc[tudo_nulo, "COBERTURA_IBGE"] = COBERTURA_VAZIA
    return dados


def _compactar_coordenadas(bloco: str) -> str:
    """Um vértice por espaço, sem altitude redundante.

    O driver LIBKML escreve cada vértice numa linha própria com 16 espaços de
    indentação — em Joinville isso foi 1,18 MB de espaço em branco num arquivo
    de 6,42 MB. O sufixo `,0` de altitude some junto: a malha do IBGE é 2D, e
    o próprio IBGE não emite altitude nos KML dele.
    """
    vertices = []
    for vertice in bloco.split():
        partes = vertice.split(",")
        if len(partes) == 3 and partes[2] == "0":
            partes = partes[:2]  # só descarta altitude nula, nunca um z real
        vertices.append(",".join(partes))
    return " ".join(vertices)


def _formatar(valor, tipo: str) -> str:
    """Número no formato brasileiro, ou um traço quando não há dado."""
    if valor is None or pd.isna(valor):
        return "&mdash;"
    if tipo == "percentual":
        return f"{valor:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    if tipo in {"valor", "derivado"}:
        return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,.0f}".replace(",", ".")


def _rotulo_limpo(rotulo: str) -> str:
    """Tira a unidade do rótulo: ela já aparece junto do valor."""
    return re.sub(r"\s*\((%|R\$)\)\s*$", "", rotulo).strip()


def montar_descricao(dados: gpd.GeoDataFrame, colunas: list[str],
                     rotulos: dict[str, tuple[str, str]]) -> pd.Series:
    """Tabela HTML para o balão do Google Earth.

    O Google Earth não exibe `ExtendedData`/`SchemaData` de forma confiável —
    os valores existem no arquivo mas o usuário só os enxerga abrindo o XML.
    Por isso o próprio IBGE embute uma tabela HTML em `<description>` nos KMZ
    dele. Aqui é a mesma solução, com rótulos legíveis em vez de códigos.

    Os dados continuam em `ExtendedData` para quem lê por software; a
    descrição é só a camada de leitura humana.
    """
    linhas = []
    for _, r in dados.iterrows():
        partes = [
            "<table>",
            f"<tr><th colspan='2'>Setor {r['CD_SETOR']}</th></tr>",
            f"<tr><td>Município</td><td>{r.get('NM_MUN', '')}</td></tr>",
        ]
        if r.get("NM_BAIRRO"):
            partes.append(f"<tr><td>Bairro</td><td>{r['NM_BAIRRO']}</td></tr>")
        partes.append(
            f"<tr><td>Situação</td><td>{r.get('SITUACAO', '')}</td></tr>"
        )
        for col in colunas:
            rotulo, tipo = rotulos.get(col, (col, "percentual"))
            partes.append(
                f"<tr><td>{_rotulo_limpo(rotulo)}</td>"
                f"<td>{_formatar(r[col], tipo)}</td></tr>"
            )
        cobertura = r.get("COBERTURA_IBGE")
        if cobertura and cobertura != COBERTURA_COMPLETA:
            partes.append(f"<tr><td colspan='2'><i>{cobertura}</i></td></tr>")
        partes.append("</table>")
        linhas.append("".join(partes))

    return pd.Series(linhas, index=dados.index)


ESTILO_ID = "setor"

# Cor no formato KML: AABBGGRR, não RRGGBB. `ff0000ff` é vermelho opaco — o
# mesmo contorno usado nos arquivos que já estão em produção. `fill 0` deixa o
# polígono vazado: sem isso o Google Earth aplica o padrão dele, um branco
# semitransparente que cobre a imagem de satélite e torna o mapa inútil.
ESTILO = (
    f'<Style id="{ESTILO_ID}">'
    "<LineStyle><color>ff0000ff</color><width>1.2</width></LineStyle>"
    "<PolyStyle><fill>0</fill><outline>1</outline></PolyStyle>"
    "</Style>"
)

_PRIMEIRO_PLACEMARK = re.compile(r"(\s*)(<Placemark\b)")
_NOME_PLACEMARK = re.compile(r"(<Placemark\b[^>]*>\s*<name>[^<]*</name>)")


def aplicar_estilo(caminho) -> None:
    """Insere um <Style> compartilhado e aponta cada Placemark para ele.

    O arquivo herdado repetia o mesmo bloco de estilo em cada um dos 1.064
    placemarks. Declarar uma vez e referenciar por `styleUrl` dá o mesmo
    resultado visual com uma fração do tamanho.
    """
    texto = caminho.read_text(encoding="utf-8")
    if f'<Style id="{ESTILO_ID}">' in texto:
        return

    texto = _PRIMEIRO_PLACEMARK.sub(
        lambda m: f"{m.group(1)}{ESTILO}{m.group(1)}{m.group(2)}", texto, count=1,
    )
    texto = _NOME_PLACEMARK.sub(
        lambda m: f"{m.group(1)}<styleUrl>#{ESTILO_ID}</styleUrl>", texto,
    )
    caminho.write_text(texto, encoding="utf-8")


def enxugar_kml(caminho) -> tuple[int, int]:
    """Reescreve o KML sem a indentação do driver. Devolve (antes, depois)."""
    texto = caminho.read_text(encoding="utf-8")
    antes = len(texto)

    enxuto = _COORDS.sub(
        lambda m: m.group(1) + _compactar_coordenadas(m.group(2)) + m.group(3),
        texto,
    )
    caminho.write_text(enxuto, encoding="utf-8")

    depois = len(enxuto)
    log.debug("enxugado %s: %.2f -> %.2f MB", caminho.name, antes / 1e6, depois / 1e6)
    return antes, depois


def escrever(dados: gpd.GeoDataFrame, destino, colunas: list[str]) -> None:
    """Escreve KML ou KMZ conforme a extensão. Espera a malha já em 4326."""
    if dados.crs is None or dados.crs.to_string() != CRS_KML:
        raise ValueError(
            f"escrever() exige EPSG:4326; recebeu {dados.crs}. "
            "Chame reprojetar() antes."
        )

    presentes = [c for c in CONTEXTO if c in dados.columns]
    saida = dados[presentes + colunas + ["geometry"]].copy()

    # O LIBKML mapeia int64 para o tipo `string` do KML, então uma contagem sem
    # nulos (população, domicílios) sairia declarada como texto enquanto os
    # demais indicadores saem como `double`. Quem lê o schema veria tipos
    # diferentes para colunas igualmente numéricas. float64 uniformiza tudo em
    # `double`, sem mudar o valor exibido.
    saida[colunas] = saida[colunas].astype("float64")
    if "description" in saida.columns:
        saida["description"] = saida["description"].fillna("")

    # O LIBKML usa a coluna `Name` como <name> do Placemark, que é o rótulo
    # exibido no Google Earth.
    saida.insert(0, "Name", saida["CD_SETOR"])

    destino.parent.mkdir(parents=True, exist_ok=True)
    # O LIBKML abre um arquivo existente em modo de atualização e acrescenta um
    # segundo <Schema> em vez de sobrescrever — a cada regeração o arquivo
    # ganha mais um bloco duplicado. A contagem de feições continua correta,
    # então a validação de schema não acusa. Apagar antes é o único jeito de
    # garantir escrita limpa.
    destino.unlink(missing_ok=True)
    saida.to_file(destino, driver="LIBKML")


def validar(destino, esperado: int, colunas: list[str]) -> None:
    """Relê o arquivo escrito e confere contagem, chave e colunas.

    Nenhum export sai sem esta conferência, e ela roda depois do enxugamento,
    para validar exatamente o arquivo que será publicado. O arquivo herdado
    passou meses com o schema desalinhado porque ninguém releu a saída.
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

    # COBERTURA_IBGE só cumpre seu papel se estiver em TODA feição: é o único
    # campo que sobrevive quando os indicadores são nulos, porque o LIBKML
    # omite campo numérico vazio. Se ele próprio faltar, o setor volta a ficar
    # sem explicação nenhuma.
    if "COBERTURA_IBGE" in lido.columns:
        faltando = int(lido["COBERTURA_IBGE"].isna().sum())
        if faltando:
            raise AssertionError(
                f"{destino.name}: COBERTURA_IBGE vazia em {faltando} setor(es)"
            )

    # Schema duplicado não altera a contagem de feições nem as colunas, então
    # só é detectável olhando o texto. Acontecia quando o LIBKML reabria um
    # arquivo existente em vez de sobrescrever.
    if destino.suffix == ".kml":
        texto = destino.read_text(encoding="utf-8")
        schemas = texto.count("<Schema ")
        if schemas != 1:
            raise AssertionError(
                f"{destino.name}: {schemas} blocos <Schema>, esperado 1"
            )

        # Sem estilo, o Google Earth preenche o polígono com branco
        # semitransparente e o mapa fica ilegível. Todo placemark precisa
        # apontar para o estilo vazado.
        marcas = texto.count("<Placemark ")
        refs = texto.count(f"<styleUrl>#{ESTILO_ID}</styleUrl>")
        if texto.count(f'<Style id="{ESTILO_ID}">') != 1 or refs != marcas:
            raise AssertionError(
                f"{destino.name}: estilo ausente ou incompleto "
                f"({refs} styleUrl para {marcas} placemarks)"
            )


def gerar_municipio(malha_mun: gpd.GeoDataFrame, indicadores: pd.DataFrame,
                    destino, colunas: list[str],
                    de_entorno: set[str] | None = None,
                    rotulos: dict[str, tuple[str, str]] | None = None) -> dict:
    """Escreve, enxuga e valida o arquivo de um município.

    Caminho único: tanto a ferramenta de município avulso quanto o lote por UF
    passam por aqui, para que não existam dois jeitos de produzir um arquivo.
    """
    dados = juntar(malha_mun, indicadores)
    dados = marcar_cobertura(dados, colunas, de_entorno or set())
    if rotulos:
        dados["description"] = montar_descricao(dados, colunas, rotulos)
    escrever(dados, destino, colunas)
    if destino.suffix == ".kml":
        aplicar_estilo(destino)
        bruto, enxuto = enxugar_kml(destino)
    else:
        bruto, enxuto = 0, 0
    validar(destino, len(dados), colunas)

    return {
        "arquivo": destino.name,
        "setores": len(dados),
        "bytes": destino.stat().st_size,
        "bytes_antes_de_enxugar": bruto,
        "sem_indicador": int(dados[colunas].isna().all(axis=1).sum()),
    }

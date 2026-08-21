"""
Catálogo de fontes do IBGE — Censo Demográfico 2022.

Todas as URLs abaixo foram verificadas diretamente no FTP do IBGE.
A chave de junção entre TODAS as fontes é o código de setor censitário
de 15 dígitos (`CD_SETOR`), tratado sempre como string com zero à esquerda.

Atenção: o IBGE versiona alguns arquivos no próprio nome (ex.: `_20260508_`).
Ao atualizar, confira o diretório antes de alterar a constante.
"""

FTP = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022"
GEOFTP = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais"
    "/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022"
)

UFS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
# GeoPackage é a fonte da verdade da geometria: colunas tipadas, sem HTML.
# Os KMZ oficiais guardam os atributos numa tabela HTML dentro de <description>,
# o que exige parsing frágil — usamos KMZ apenas como formato de SAÍDA.

MALHA_GPKG_BR = f"{GEOFTP}/setores/gpkg/BR/BR_setores_CD2022.gpkg"


def malha_gpkg_uf(sigla: str) -> str:
    """GeoPackage de setores de uma UF (ex.: 'RO')."""
    return f"{GEOFTP}/setores/gpkg/UF/{sigla}/{sigla}_setores_CD2022.gpkg"


def malha_kml_uf(codigo: str, sigla: str) -> str:
    """ZIP com um KMZ por município da UF (ex.: '11', 'RO').

    É a origem dos ~5.494 KMZ municipais. Baixado apenas como referência
    de layout de saída — a geometria de trabalho vem do GeoPackage.
    """
    return f"{GEOFTP}/setores/kml/{codigo}_{sigla}.zip"


# ---------------------------------------------------------------------------
# Atributos por setor censitário
# ---------------------------------------------------------------------------
_AGREGADOS = f"{FTP}/Agregados_por_Setores_Censitarios"
_ENTORNO = (
    f"{FTP}/Agregados_por_Setores_Censitarios"
    "_Caracteristicas_urbanisticas_do_entorno_dos_domicilios"
)
_RENDA = f"{FTP}/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel"

# name -> (url, prefixo das variáveis)
TABELAS = {
    # Bloco geral do Censo
    "basico":        (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_basico_BR_20260520.zip", None),
    "demografia":    (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_demografia_BR.zip", None),
    "alfabetizacao": (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_alfabetizacao_BR.zip", None),
    "cor_ou_raca":   (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_cor_ou_raca_BR.zip", None),
    "domicilio1":    (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_caracteristicas_domicilio1_BR.zip", None),
    "domicilio2":    (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.zip", None),
    "domicilio3":    (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_caracteristicas_domicilio3_BR_20250417.zip", None),
    "parentesco":    (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_parentesco_BR.zip", None),
    "obitos":        (f"{_AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_obitos_BR.zip", None),

    # Entorno urbanístico: arborização, pavimentação, calçada, meio-fio,
    # bueiro, iluminação pública, rampa, esgoto a céu aberto, lixo acumulado.
    "entorno_domicilios": (f"{_ENTORNO}/Agregados_por_Setor_csv/Agregados_por_setores_entorno_domic%c3%adlios_BR.zip", "V05"),
    "entorno_faces":      (f"{_ENTORNO}/Agregados_por_Setor_csv/Agregados_por_setores_entorno_faces_BR.zip", None),
    "entorno_moradores":  (f"{_ENTORNO}/Agregados_por_Setor_csv/Agregados_por_setores_entorno_moradores_BR.zip", None),

    # Rendimento do responsável pelo domicílio.
    "renda_responsavel": (f"{_RENDA}/Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip", "V06"),
}

# ---------------------------------------------------------------------------
# Dicionários de variáveis — sem eles V05017 não vira "arborização".
# ---------------------------------------------------------------------------
DICIONARIOS = {
    "agregados": f"{_AGREGADOS}/dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx",
    "entorno":   f"{_ENTORNO}/dicionarios_de_dados_entorno.zip",
    "renda":     f"{_RENDA}/dicionario_de_dados_renda_responsavel_20260508.xlsx",
    "malha":     f"{GEOFTP}/Dicionario_de_dados_malha_agregados.xlsx",
}

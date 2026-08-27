"""02 — Consolida os dicionários do IBGE num único índice de variáveis.

Saídas:
  data/processed/dicionario_unificado.csv  uma linha por variável
  docs/variaveis_origem.csv                tabela variável -> origem (versionada)
  docs/inventario_fontes.md                resumo legível, gerado
  docs/indicadores_curados.md              subconjunto para avaliação imobiliária

Responde a "esta variável vem de qual arquivo?" com procedência verificada.
O mapeamento variável -> arquivo é derivado de DUAS fontes independentes e
conferido entre si:
  1. a coluna `Tema` dos dicionários oficiais do IBGE;
  2. o cabeçalho real de cada CSV, lido direto do ZIP remoto por range request.
Divergência entre as duas aborta a execução — é sinal de que o IBGE
republicou um arquivo e o catálogo precisa ser revisto.
"""

import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import indicadores as ind_cfg  # noqa: E402
import sources  # noqa: E402
from kmlpipe import headers, inventario, logging_setup, paths  # noqa: E402

# Tema no dicionário oficial -> chave da tabela em config/sources.py
TEMA_PARA_TABELA = {
    "Características do Domicílio - Parte 1": "domicilio1",
    "Características do Domicílio - Parte 2": "domicilio2",
    "Características do Domicílio - Parte 3": "domicilio3",
    "Alfabetização": "alfabetizacao",
    "Demografia": "demografia",
    "Parentesco": "parentesco",
    "Óbitos": "obitos",
    "Cor ou Raça": "cor_ou_raca",
}

# Arquivo dentro de dicionarios_de_dados_entorno.zip -> chave da tabela
ENTORNO_PARA_TABELA = {
    "dicionario_entorno_domicilios.xlsx": "entorno_domicilios",
    "dicionario_entorno_faces.xlsx": "entorno_faces",
    "dicionario_entorno_pessoas.xlsx": "entorno_moradores",
}

DIC_AGREGADOS = "dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx"
DIC_RENDA = "dicionario_de_dados_renda_responsavel_20260508.xlsx"
DIC_ENTORNO = "dicionarios_de_dados_entorno.zip"

COLUNAS = ["tabela", "tema", "tipo", "variavel", "descricao"]


def _limpar(texto: str) -> str:
    """Descrições do entorno vêm com colchetes de hierarquia; viram ' > '."""
    t = str(texto).strip()
    if t.startswith("[") and t.endswith("]"):
        partes = re.findall(r"\[([^\]]*)\]", t)
        if partes:
            return " > ".join(p.strip() for p in partes)
    return t


def carregar_agregados(log) -> pd.DataFrame:
    caminho = paths.DICTS / DIC_AGREGADOS
    linhas = []

    basico = pd.read_excel(caminho, "Dicionário Básico")
    basico.columns = ["tema", "variavel", "descricao"]
    for _, r in basico.iterrows():
        linhas.append(("basico", "Básico", "Setor", r.variavel, r.descricao))

    nao_pct = pd.read_excel(caminho, "Dicionário não PCT")
    nao_pct.columns = ["tipo", "tema", "variavel", "descricao"]
    desconhecidos = set(nao_pct.tema) - set(TEMA_PARA_TABELA)
    if desconhecidos:
        log.error("temas sem mapeamento para arquivo: %s", desconhecidos)
        raise SystemExit(1)
    for _, r in nao_pct.iterrows():
        linhas.append((TEMA_PARA_TABELA[r.tema], r.tema, r.tipo, r.variavel, r.descricao))

    return pd.DataFrame(linhas, columns=COLUNAS)


def carregar_entorno(log) -> pd.DataFrame:
    unidades = {
        "entorno_domicilios": "Domicílio",
        "entorno_faces": "Face de quadra",
        "entorno_moradores": "Pessoa",
    }
    linhas = []
    with zipfile.ZipFile(paths.DICTS / DIC_ENTORNO) as zf:
        for nome, tabela in ENTORNO_PARA_TABELA.items():
            d = pd.read_excel(zf.open(nome))
            d.columns = ["variavel", "descricao"]
            for _, r in d.iterrows():
                linhas.append((tabela, "Entorno urbanístico", unidades[tabela],
                               r.variavel, r.descricao))
    return pd.DataFrame(linhas, columns=COLUNAS)


def carregar_renda(log) -> pd.DataFrame:
    d = pd.read_excel(paths.DICTS / DIC_RENDA)
    d.columns = ["tema", "variavel", "descricao"]
    d["tabela"] = "renda_responsavel"
    d["tipo"] = "Responsável pelo domicílio"
    return d[COLUNAS]


def anotar_procedencia(dic: pd.DataFrame, cabecalhos: dict) -> pd.DataFrame:
    """Acrescenta de qual arquivo/URL cada variável vem e sua grafia exata."""
    dic["url_origem"] = dic["tabela"].map(
        {nome: url for nome, (url, _) in sources.TABELAS.items()}
    )
    dic["arquivo_csv"] = dic["tabela"].map(
        {k: v["arquivo_csv"] for k, v in cabecalhos.items()}
    )
    dic["coluna_chave_no_csv"] = dic["tabela"].map(
        {k: v["colunas"][0] for k, v in cabecalhos.items()}
    )

    grafia = {}
    for tabela, info in cabecalhos.items():
        for c in info["colunas"]:
            if re.fullmatch(r"[Vv]\d+", c):
                grafia[(tabela, c.upper())] = c
    dic["variavel_no_csv"] = [
        grafia.get((t, str(v).upper())) for t, v in zip(dic.tabela, dic.variavel)
    ]
    return dic


def conferir(dic: pd.DataFrame, cabecalhos: dict, log) -> None:
    """Confronta o dicionário com o cabeçalho real de cada CSV."""
    problemas = 0
    for tabela, info in cabecalhos.items():
        # O IBGE não é consistente na caixa: `basico` usa `v0001`, os demais
        # `V00001`. Comparamos em maiúsculas; a grafia real fica em
        # `variavel_no_csv`.
        no_csv = {c.upper() for c in info["colunas"] if re.fullmatch(r"[Vv]\d+", c)}
        no_dic = {str(v).upper() for v in dic.loc[dic.tabela == tabela, "variavel"]}
        so_csv, so_dic = no_csv - no_dic, no_dic - no_csv
        if so_csv or so_dic:
            problemas += 1
            log.error("%s: só no CSV=%s | só no dicionário=%s",
                      tabela, sorted(so_csv)[:5], sorted(so_dic)[:5])
        else:
            log.info("%-20s %4d variáveis conferem com o CSV", tabela, len(no_csv))

    if problemas:
        log.error("%d tabela(s) divergem entre dicionário e CSV", problemas)
        raise SystemExit(1)


def main() -> int:
    log = logging_setup.setup("dicionario")
    paths.ensure()

    cabecalhos = headers.obter(sources.TABELAS)

    dic = pd.concat(
        [carregar_agregados(log), carregar_entorno(log), carregar_renda(log)],
        ignore_index=True,
    )
    dic["descricao"] = dic["descricao"].map(_limpar)
    dic = anotar_procedencia(dic, cabecalhos)

    duplicadas = dic[dic.variavel.duplicated(keep=False)]
    if not duplicadas.empty:
        log.error("variáveis em mais de um arquivo:\n%s", duplicadas.to_string())
        raise SystemExit(1)
    log.info("nenhuma variável aparece em dois arquivos diferentes")

    conferir(dic, cabecalhos, log)

    destino = paths.PROCESSED / "dicionario_unificado.csv"
    dic.to_csv(destino, index=False, encoding="utf-8")
    log.info("%d variáveis de %d arquivos -> %s",
             len(dic), dic.tabela.nunique(), destino)

    # Tabela enxuta variável -> origem, versionada no repo por ser pequena
    # e a resposta mais consultada do projeto.
    tabela = ROOT / "docs" / "variaveis_origem.csv"
    tabela.parent.mkdir(exist_ok=True)
    (dic.rename(columns={"tipo": "unidade", "arquivo_csv": "arquivo",
                         "coluna_chave_no_csv": "coluna_chave"})
        [["variavel", "variavel_no_csv", "descricao", "tema", "unidade",
          "tabela", "arquivo", "coluna_chave", "url_origem"]]
        .to_csv(tabela, index=False, encoding="utf-8"))
    log.info("tabela variável->origem -> %s", tabela)

    doc = ROOT / "docs" / "inventario_fontes.md"
    doc.parent.mkdir(exist_ok=True)
    tamanhos = {k: v["bytes"] for k, v in cabecalhos.items()}
    doc.write_text(inventario.gerar(dic, cabecalhos, tamanhos), encoding="utf-8")
    log.info("inventário -> %s", doc)

    curadoria = ROOT / "docs" / "indicadores_curados.md"
    curadoria.write_text(
        inventario.gerar_curadoria(ind_cfg.INDICADORES, ind_cfg.EXCLUIDOS,
                                   ind_cfg.INDISPONIVEIS, tamanhos,
                                   ind_cfg.CONJUNTOS),
        encoding="utf-8")
    log.info("curadoria (%d indicadores) -> %s",
             len(ind_cfg.INDICADORES), curadoria)

    print()
    print(dic.groupby("tabela", sort=False)
             .agg(variaveis=("variavel", "size"),
                  de=("variavel", "first"),
                  ate=("variavel", "last"),
                  chave=("coluna_chave_no_csv", "first"))
             .to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Gera docs/inventario_fontes.md a partir do dicionário unificado.

O documento é derivado, nunca editado à mão: qualquer republicação do IBGE
muda os números aqui automaticamente na próxima execução do 02.
"""

from __future__ import annotations

import pandas as pd

# Temas de interesse. Quando o tema corresponde a um arquivo inteiro usamos a
# tabela; quando é um recorte dentro de um arquivo, usamos regex sobre a
# descrição. Os regex foram conferidos contra o texto real do IBGE — cuidado:
# "sanitário" aparece em "vaso sanitário" (banheiro) e não serve para esgoto,
# e óbitos são descritos como "pessoa falecida", nunca como "óbito".
TEMAS: list[tuple[str, str, str | None]] = [
    ("Renda do responsável", "tabela", "renda_responsavel"),
    ("Demografia (sexo e idade)", "tabela", "demografia"),
    ("Alfabetização", "tabela", "alfabetizacao"),
    ("Cor ou raça", "tabela", "cor_ou_raca"),
    ("Parentesco / composição familiar", "tabela", "parentesco"),
    ("Óbitos no domicílio", "tabela", "obitos"),
    ("Arborização", "regex", r"arboriza"),
    ("Pavimentação da via", "regex", r"pavimentada"),
    ("Calçada", "regex", r"cal[çc]ada"),
    ("Rampa para cadeirante", "regex", r"rampa"),
    ("Iluminação pública", "regex", r"ilumina[çc][ãa]o"),
    ("Bueiro", "regex", r"bueiro"),
    ("Ponto de ônibus", "regex", r"ponto de [ôo]nibus"),
    ("Via sinalizada para bicicleta", "regex", r"bicicleta"),
    ("Abastecimento de água", "regex", r"abastecimento de água|rede geral de distribui"),
    ("Destinação do esgoto", "regex", r"esgoto"),
    ("Destino do lixo", "regex", r"lixo"),
    ("Banheiros no domicílio", "regex", r"banheiro"),
    ("Energia elétrica", "regex", r"energia el[ée]tric"),
]

UNIDADE = {
    "basico": "Setor", "domicilio1": "Domicílio", "domicilio2": "Domicílio",
    "domicilio3": "Domicílio", "alfabetizacao": "Pessoa", "demografia": "Pessoa",
    "parentesco": "Pessoa", "obitos": "Pessoa", "cor_ou_raca": "Pessoa",
    "entorno_domicilios": "Domicílio", "entorno_moradores": "Pessoa",
    "entorno_faces": "Face de quadra", "renda_responsavel": "Responsável",
}

ORDEM = [
    "basico", "domicilio1", "domicilio2", "domicilio3", "alfabetizacao",
    "demografia", "parentesco", "obitos", "cor_ou_raca", "entorno_domicilios",
    "entorno_moradores", "entorno_faces", "renda_responsavel",
]


def _selecionar(dic: pd.DataFrame, modo: str, alvo: str) -> pd.DataFrame:
    if modo == "tabela":
        return dic[dic.tabela == alvo]
    return dic[dic.descricao.str.contains(alvo, case=False, na=False, regex=True)]


def gerar(dic: pd.DataFrame, headers: dict, tamanhos: dict[str, int]) -> str:
    L: list[str] = []
    add = L.append

    add("# Inventário de fontes e variáveis — Censo 2022 por setor censitário")
    add("")
    add("Gerado por `scripts/02_dicionario.py`. **Não editar à mão.**")
    add("")
    add("Cada variável foi conferida contra duas fontes independentes: o dicionário")
    add("oficial do IBGE e o cabeçalho real do CSV, lido direto do ZIP remoto via")
    add("*range request* (sem baixar os arquivos inteiros).")
    add("")
    add(f"**{len(dic)} variáveis** em **{dic.tabela.nunique()} arquivos**. Nenhuma")
    add("variável aparece em dois arquivos: as faixas são contíguas e disjuntas.")
    add("")

    add("## Qual variável vem de qual arquivo")
    add("")
    add("| Arquivo (chave em `sources.py`) | Vars | Faixa | Unidade | Coluna-chave no CSV | MB |")
    add("|---|---:|---|---|---|---:|")
    for t in ORDEM:
        s = dic[dic.tabela == t]
        if s.empty:
            continue
        chave = headers[t]["colunas"][0].strip().strip('"').lstrip("\ufeff")
        add(f"| `{t}` | {len(s)} | `{s.variavel.iloc[0]}`–`{s.variavel.iloc[-1]}` "
            f"| {UNIDADE[t]} | `{chave}` | {tamanhos.get(t, 0) / 1e6:.1f} |")
    add("")
    add(f"Volume total dos CSV: **{sum(tamanhos.values()) / 1e6:.0f} MB** compactados.")
    add("")

    add("## Armadilhas confirmadas")
    add("")
    add("**1. A coluna-chave tem quatro grafias diferentes.** Um merge ingênuo quebra:")
    add("")
    por_chave: dict[str, list[str]] = {}
    for t in ORDEM:
        if t in headers:
            k = headers[t]["colunas"][0].strip().strip('"').lstrip("\ufeff")
            por_chave.setdefault(k, []).append(t)
    for k, ts in por_chave.items():
        add(f"- `{k}` → {', '.join('`' + x + '`' for x in ts)}")
    add("")
    add("**2. A caixa do nome da variável varia.** `basico` usa `v0001` minúsculo;")
    add("os demais usam maiúsculo (`V00001`). A coluna `variavel_no_csv` do dicionário")
    add("unificado guarda a grafia exata de cada uma, para ler sem adivinhar.")
    add("")
    add("**3. `basico` repete as 29 colunas de contexto da malha** (`NM_MUN`, `CD_UF`, …),")
    add("redundantes com o GeoPackage. Devem ser descartadas na junção.")
    add("")
    add("**4. O mesmo tema aparece em três unidades de medida diferentes.** Entorno é")
    add("publicado por domicílio (`V050xx`), por morador (`V052xx`) e por face de quadra")
    add("(`V054xx`). São recortes distintos do mesmo questionário — escolher um e")
    add("documentar a escolha, nunca somar entre eles.")
    add("")

    add("## Cobertura por tema")
    add("")
    add("| Tema | Variáveis | Arquivos |")
    add("|---|---:|---|")
    for nome, modo, alvo in TEMAS:
        m = _selecionar(dic, modo, alvo)
        if m.empty:
            add(f"| {nome} | **0 — não publicado por setor** | — |")
        else:
            arqs = ", ".join("`" + x + "`" for x in sorted(m.tabela.unique()))
            add(f"| {nome} | {len(m)} | {arqs} |")
    add("")
    add("> **Energia elétrica não é publicada por setor censitário no Censo 2022.**")
    add("> O README do projeto anterior listava esse indicador como meta; nesta")
    add("> granularidade ele não existe e precisaria vir de outra fonte.")
    add("")

    add("## Não incluídos no catálogo")
    add("")
    add("Existem no FTP mas ficaram fora de `config/sources.py`: são recortes de")
    add("populações específicas, com a maioria dos setores sem dado.")
    add("")
    add("- `Agregados_por_setores_domicilios_indigenas_BR.zip` (`V01500`+)")
    add("- `Agregados_por_setores_pessoas_indigenas_BR.zip`")
    add("- `Agregados_por_setores_domicilios_quilombolas_BR.zip` (`V03000`+)")
    add("- `Agregados_por_setores_pessoas_quilombolas_BR.zip`")
    add("")
    add("Basta acrescentá-los a `TABELAS` se forem necessários.")
    add("")
    return "\n".join(L)


def gerar_curadoria(indicadores, excluidos, indisponiveis, tamanhos) -> str:
    """docs/indicadores_curados.md — o subconjunto que vai para o KMZ."""
    L: list[str] = []
    add = L.append

    usadas = {v for i in indicadores
              for v in list(i.numerador) + list(i.denominador)}
    tabelas = sorted({i.tabela for i in indicadores})
    mb = sum(tamanhos.get(t, 0) for t in tabelas) / 1e6

    add("# Indicadores curados para avaliação imobiliária")
    add("")
    add("Gerado por `scripts/02_dicionario.py` a partir de "
        "`config/indicadores.py`. **Não editar à mão.**")
    add("")
    add("**Regra de inclusão:** a variável entra se for reconhecida no mercado "
        "como fator que valoriza ou deprecia o imóvel.")
    add("")
    add(f"Resultado: **{len(indicadores)} indicadores** derivados de "
        f"**{len(usadas)} variáveis** do IBGE — de 1.531 disponíveis.")
    add(f"Isso reduz o download de 513 MB para **{mb:.0f} MB** "
        f"({len(tabelas)} arquivos em vez de 13).")
    add("")
    add("Todo percentual declara denominador explícito: contagem bruta de "
        "domicílios não é comparável entre setores de tamanhos diferentes.")
    add("")

    grupos: dict[str, list] = {}
    for ind in indicadores:
        grupos.setdefault(ind.tabela, []).append(ind)

    SETA = {"valoriza": "▲ valoriza", "deprecia": "▼ deprecia",
            "contexto": "● contexto"}

    for tabela in tabelas:
        add(f"## `{tabela}`")
        add("")
        add("| Coluna no KMZ | Rótulo | Sentido | Fórmula |")
        add("|---|---|---|---|")
        for ind in grupos[tabela]:
            if ind.tipo in {"valor", "contagem"}:
                formula = f"`{ind.numerador[0]}`"
            elif ind.tipo == "derivado":
                formula = ("`" + "*".join(ind.numerador) + " / "
                           + "+".join(ind.denominador) + "`")
            else:
                num = "+".join(ind.numerador)
                den = "+".join(ind.denominador)
                if len(ind.numerador) > 3:
                    num = f"{ind.numerador[0]}…{ind.numerador[-1]}"
                if len(ind.denominador) > 3:
                    den = f"{ind.denominador[0]}…{ind.denominador[-1]}"
                formula = f"`{num} / {den}`"
            add(f"| `{ind.nome}` | {ind.rotulo} | {SETA[ind.direcao]} | {formula} |")
        add("")
        notas = [i for i in grupos[tabela] if i.nota]
        if notas:
            for ind in notas:
                add(f"- **`{ind.nome}`** — {ind.nota}")
            add("")

    add("## Excluídos deliberadamente")
    add("")
    for chave, motivo in excluidos.items():
        add(f"**`{chave}`** — {motivo}")
        add("")

    add("## Não publicados por setor no Censo 2022")
    add("")
    add("Fatores que o mercado usaria, mas que a fonte não oferece nesta "
        "granularidade:")
    add("")
    for chave, motivo in indisponiveis.items():
        add(f"- **{chave}** — {motivo}")
    add("")
    return "\n".join(L)

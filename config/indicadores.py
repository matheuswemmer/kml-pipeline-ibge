"""Curadoria dos indicadores que vão para o KMZ.

Regra de inclusão: a variável entra se fizer sentido para avaliação
imobiliária — se for reconhecida no mercado como fator que valoriza ou
deprecia o imóvel. Das 1.531 variáveis publicadas por setor, a esmagadora
maioria é desagregação demográfica sem leitura de valor; o que sobra está
aqui.

Cada indicador declara denominador explícito. Contagem bruta de domicílios
não é comparável entre setores de tamanhos diferentes — o que se compara é
proporção. As únicas exceções são valores monetários e totais de contexto,
marcados como `valor` e `contagem`.

`direcao` registra o sentido esperado no mercado, para orientar simbologia e
sinalizar quando o dado contradiz a expectativa. Não é peso de modelo: a
magnitude do efeito varia por praça e precisa ser estimada, nunca assumida.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Indicador:
    nome: str                      # nome da coluna no KMZ, snake_case
    rotulo: str                    # rótulo legível, exibido no Google Earth
    tabela: str                    # chave em config/sources.py
    tipo: str                      # percentual | valor | contagem | derivado
    direcao: str                   # valoriza | deprecia | contexto
    numerador: list[str] = field(default_factory=list)
    denominador: list[str] = field(default_factory=list)
    nota: str = ""
    # Como o denominador se relaciona com o numerador. Distinção que importa:
    #   "categorias" -> o denominador é a soma das categorias do próprio bloco,
    #                   e o numerador é um subconjunto dele (parte do todo);
    #   "total"      -> o denominador é uma variável de total independente,
    #                   publicada à parte (ex.: V0003, V01006).
    # A validação só exige numerador ⊆ denominador no primeiro caso.
    base: str = "categorias"
    # Tabela de onde vem o denominador, quando não é a mesma do numerador.
    # Usado para V00001 (total de domicílios), que está em `domicilio1`
    # enquanto as categorias estão em `domicilio2`.
    tabela_denominador: str | None = None


def _faixa(inicio: str, fim: str) -> list[str]:
    """Todas as variáveis Vxxxxx entre dois códigos, inclusive."""
    largura = len(inicio) - 1
    return [f"V{n:0{largura}d}" for n in range(int(inicio[1:]), int(fim[1:]) + 1)]


# ---------------------------------------------------------------------------
# Renda — o preditor isolado mais forte de valor em praticamente toda praça
# ---------------------------------------------------------------------------
RENDA = [
    Indicador(
        "renda_resp_mediana", "Renda mediana do responsável (R$)",
        "renda_responsavel", "valor", "valoriza", ["V06006"],
        nota="Mediana é mais robusta que a média: um único setor com outlier "
             "de renda não distorce a leitura.",
    ),
    Indicador(
        "renda_resp_media", "Renda média do responsável (R$)",
        "renda_responsavel", "valor", "valoriza", ["V06004"],
        nota="Sensível a outliers. Comparar com a mediana: divergência grande "
             "indica setor heterogêneo.",
    ),
    Indicador(
        "renda_resp_per_capita_proxy", "Renda per capita — proxy (R$)",
        "renda_responsavel", "derivado", "valoriza",
        ["V06004", "V06001"], ["V06002"],
        nota="PROXY, não renda per capita real. V06004*V06001/V06002 ignora a "
             "renda dos demais moradores e subestima o valor. O Censo 2022 não "
             "publica renda domiciliar per capita por setor.",
    ),
]

# ---------------------------------------------------------------------------
# Entorno urbanístico — infraestrutura da rua, o que o avaliador vê in loco
# Denominador exclui "não declarado": proporção sobre quem respondeu.
# ---------------------------------------------------------------------------
ENTORNO = [
    Indicador("pct_via_pavimentada", "Via pavimentada (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05006"], ["V05006", "V05007"]),
    Indicador("pct_calcada", "Calçada (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05021"], ["V05021", "V05022"]),
    Indicador("pct_iluminacao_publica", "Iluminação pública (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05012"], ["V05012", "V05013"]),
    Indicador("pct_bueiro", "Bueiro / drenagem (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05009"], ["V05009", "V05010"],
              nota="Ausência de drenagem sinaliza risco de alagamento, que "
                   "deprecia de forma acentuada e persistente."),
    Indicador("pct_arborizacao", "Arborização — ao menos 1 árvore (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05031", "V05032", "V05033"],
              ["V05030", "V05031", "V05032", "V05033"],
              nota="V05034 (saltado) fica fora do denominador: não foi "
                   "observado, não é ausência de árvore."),
    Indicador("pct_arborizacao_densa", "Arborização densa — 5+ árvores (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05033"], ["V05030", "V05031", "V05032", "V05033"]),
    Indicador("pct_ponto_onibus", "Ponto de ônibus na face (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05015"], ["V05015", "V05016"],
              nota="Acessibilidade a transporte. Em praças de padrão alto o "
                   "sinal pode inverter — verificar antes de usar."),
    Indicador("pct_ciclovia", "Via sinalizada para bicicleta (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05018"], ["V05018", "V05019"]),
    Indicador("pct_rampa_acessibilidade", "Rampa para cadeirante (%)",
              "entorno_domicilios", "percentual", "valoriza",
              ["V05027"], ["V05027", "V05028"]),
    Indicador("pct_obstaculo_calcada", "Obstáculo na calçada (%)",
              "entorno_domicilios", "percentual", "deprecia",
              ["V05024"], ["V05024", "V05025"]),
    Indicador("entorno_domicilios_pesquisados", "Domicílios pesquisados no entorno",
              "entorno_domicilios", "contagem", "contexto", ["V05000"],
              nota="Controle de qualidade. O bloco de entorno só foi aplicado "
                   "em setores selecionados; valor ausente ou baixo significa "
                   "que os percentuais acima são pouco confiáveis ou nulos."),
]

# ---------------------------------------------------------------------------
# Saneamento — presença ou ausência de rede move preço de forma direta
# ---------------------------------------------------------------------------
# Estes quatro blocos são exaustivos: conferido que somam exatamente V00001
# (total de domicílios) nos setores sem supressão — 204.414 no caso do esgoto,
# resíduo zero em todos. Por isso o denominador é V00001 e não a soma do
# bloco: o IBGE suprime células por sigilo (54,6% dos setores no esgoto), e
# somar o bloco trataria cada `X` como zero, encolhendo o denominador e
# superestimando o percentual.
#
# As faixas seguem declaradas porque descrevem o bloco, mesmo não sendo mais
# usadas como denominador.
_AGUA = _faixa("V00111", "V00118")
_ESGOTO = _faixa("V00309", "V00316")
_LIXO = _faixa("V00397", "V00402")
_BANHEIRO = _faixa("V00232", "V00238")

SANEAMENTO = [
    Indicador("pct_agua_rede_geral", "Água de rede geral (%)",
              "domicilio2", "percentual", "valoriza", ["V00111"], ["V00001"], base="total", tabela_denominador="domicilio1"),
    Indicador("pct_agua_encanada_interna", "Água encanada dentro do domicílio (%)",
              "domicilio2", "percentual", "valoriza",
              ["V00199"], ["V00001"], base="total", tabela_denominador="domicilio1"),
    Indicador("pct_esgoto_rede_geral", "Esgoto em rede geral (%)",
              "domicilio2", "percentual", "valoriza",
              ["V00309", "V00310"], ["V00001"], base="total", tabela_denominador="domicilio1",
              nota="Inclui fossa séptica ligada à rede (V00310), que a "
                   "engenharia sanitária trata como solução adequada."),
    Indicador("pct_esgoto_inadequado", "Esgoto inadequado (%)",
              "domicilio2", "percentual", "deprecia",
              ["V00312", "V00313", "V00314", "V00316"], ["V00001"], base="total", tabela_denominador="domicilio1",
              nota="Fossa rudimentar, vala, lançamento em corpo hídrico e "
                   "ausência de banheiro. Esgoto a céu aberto é um dos "
                   "depreciadores mais fortes em avaliação urbana."),
    Indicador("pct_lixo_coletado", "Coleta de lixo (%)",
              "domicilio2", "percentual", "valoriza",
              ["V00397", "V00398"], ["V00001"], base="total", tabela_denominador="domicilio1"),
    Indicador("pct_lixo_destino_inadequado", "Lixo com destino inadequado (%)",
              "domicilio2", "percentual", "deprecia",
              ["V00399", "V00400", "V00401"], ["V00001"], base="total", tabela_denominador="domicilio1",
              nota="Queimado, enterrado ou jogado em terreno baldio."),
    Indicador("pct_sem_banheiro", "Sem banheiro exclusivo (%)",
              "domicilio2", "percentual", "deprecia",
              ["V00236", "V00237", "V00238"], ["V00001"], base="total", tabela_denominador="domicilio1"),
    Indicador("pct_dois_ou_mais_banheiros", "Dois ou mais banheiros (%)",
              "domicilio2", "percentual", "valoriza",
              ["V00233", "V00234", "V00235"], ["V00001"], base="total", tabela_denominador="domicilio1",
              nota="Proxy de padrão construtivo do setor."),
]

# ---------------------------------------------------------------------------
# Tipologia — verticalização e padrão de ocupação
# A espécie do domicílio só é publicada cruzada com cor/raça do responsável;
# somamos as cinco categorias para recuperar a marginal. O recorte racial é
# descartado na soma, não usado.
# ---------------------------------------------------------------------------
_CASA = _faixa("V00090", "V00094")
_VILA = _faixa("V00095", "V00099")
_APTO = _faixa("V00100", "V00104")
_ESPECIE = _CASA + _VILA + _APTO

TIPOLOGIA = [
    Indicador("pct_apartamento", "Apartamentos (%)",
              "domicilio2", "percentual", "contexto", _APTO, _ESPECIE,
              nota="Grau de verticalização. Não valoriza nem deprecia por si: "
                   "define o segmento com que o imóvel avaliando compete."),
    Indicador("pct_casa_condominio", "Casas de vila ou condomínio (%)",
              "domicilio2", "percentual", "valoriza", _VILA, _ESPECIE),
]

# ---------------------------------------------------------------------------
# Ocupação e densidade — vacância e sazonalidade
# ---------------------------------------------------------------------------
OCUPACAO = [
    Indicador("pct_domicilios_vagos", "Domicílios vagos (%)",
              "basico", "percentual", "deprecia", ["V0009"], ["V0003"],
              nota="Vacância alta indica excesso de oferta ou esvaziamento.",
              base="total"),
    Indicador("pct_uso_ocasional", "Domicílios de uso ocasional (%)",
              "basico", "percentual", "contexto", ["V0008"], ["V0003"],
              nota="Segunda residência. Valor alto caracteriza praça de "
                   "veraneio, onde a sazonalidade domina a formação de preço.",
              base="total"),
    Indicador("media_moradores_domicilio", "Média de moradores por domicílio",
              "basico", "valor", "contexto", ["V0005"]),
    Indicador("domicilios_particulares", "Domicílios particulares",
              "basico", "contagem", "contexto", ["V0003"]),
    Indicador("populacao_total", "População total",
              "basico", "contagem", "contexto", ["V0001"]),
]

# ---------------------------------------------------------------------------
# Perfil da população — capital humano e ciclo de vida do bairro
# ---------------------------------------------------------------------------
PERFIL = [
    Indicador("pct_alfabetizados_15mais", "Alfabetização, 15 anos ou mais (%)",
              "alfabetizacao", "percentual", "valoriza",
              _faixa("V00748", "V00760"), _faixa("V00644", "V00656"),
              nota="Treze faixas etárias no numerador e no denominador, "
                   "pareadas uma a uma.",
              base="total"),
    Indicador("pct_idosos", "População de 60 anos ou mais (%)",
              "demografia", "percentual", "contexto",
              ["V01040", "V01041"], ["V01006"],
              nota="Bairro consolidado e estável, com menor rotatividade.",
              base="total"),
    Indicador("pct_criancas", "População de 0 a 9 anos (%)",
              "demografia", "percentual", "contexto",
              ["V01031", "V01032"], ["V01006"],
              nota="Bairro em formação, demanda por escola e creche.",
              base="total"),
]

INDICADORES = RENDA + ENTORNO + SANEAMENTO + TIPOLOGIA + OCUPACAO + PERFIL

# ---------------------------------------------------------------------------
# Exclusões deliberadas
# ---------------------------------------------------------------------------
EXCLUIDOS = {
    "cor_ou_raca": (
        "As 95 variáveis de cor ou raça, e todas as desagregações raciais em "
        "domicilio2 e alfabetizacao, ficam fora por decisão de projeto. Usar "
        "composição racial como preditor de valor imobiliário reproduz "
        "segregação histórica na forma de preço — é o mecanismo do redlining, "
        "e num laudo vira discriminação com aparência técnica. O efeito que "
        "essas variáveis capturariam já entra pela renda e pela infraestrutura, "
        "que são as causas defensáveis. Habilitar apenas com justificativa "
        "explícita e finalidade que não seja precificação."
    ),
    "obitos": (
        "As 93 variáveis de óbito no domicílio (jan/2019 a jul/2022) refletem "
        "sobretudo a mortalidade da pandemia. Não é atributo do imóvel nem do "
        "entorno e não tem leitura de valor estável."
    ),
    "parentesco": (
        "As 182 de composição familiar descrevem quem mora, não o imóvel nem a "
        "localização. Densidade e ciclo de vida já entram por indicadores mais "
        "diretos."
    ),
    "entorno_faces_e_moradores": (
        "As 70 variáveis de entorno medidas por face de quadra (V054xx) e por "
        "morador (V052xx) cobrem os mesmos temas já capturados por domicílio "
        "(V050xx). Usar as três seria triplicar a mesma informação em unidades "
        "incomparáveis."
    ),
    "domicilio3": (
        "As 148 variáveis do domicilio3 repetem as categorias do domicilio2 "
        "contadas por morador, criança e sexo. Para proporção de domicílios, "
        "que é o que interessa aqui, o domicilio2 é a base correta."
    ),
}

# Variáveis que o mercado usaria mas que o Censo 2022 NÃO publica por setor.
INDISPONIVEIS = {
    "condicao_de_ocupacao": "Próprio, alugado, cedido ou financiado — existia "
                            "em 2010, não publicado por setor em 2022.",
    "comodos_e_dormitorios": "Número de cômodos e de dormitórios — idem.",
    "energia_eletrica": "Não publicado por setor no Censo 2022. Precisaria vir "
                        "da ANEEL ou da distribuidora local.",
    "valor_do_aluguel": "Nunca foi publicado na granularidade de setor.",
}


# ---------------------------------------------------------------------------
# Conjuntos nomeados de saída
# ---------------------------------------------------------------------------
# Os 32 indicadores continuam definidos e validados acima; um conjunto apenas
# escolhe quais vão para o KML. Trocar de conjunto não exige recalcular a base
# nacional, que guarda todos.
#
# ATENÇÃO em `essenciais`: sem `entorno_domicilios_pesquisados` não há como
# distinguir "rua sem asfalto" de "setor não pesquisado". Dois dos seis
# indicadores vêm do bloco de entorno, que no Maranhão cobre só 48% dos
# setores — neles, mais da metade do estado sai vazio sem explicação no
# próprio arquivo.
CONJUNTOS = {
    "todos": [ind.nome for ind in INDICADORES],
    "essenciais": [
        "renda_resp_per_capita_proxy",
        "renda_resp_mediana",
        # É o V06004 do IBGE, sem cálculo intermediário — e é o mesmo número
        # que os arquivos herdados guardavam sozinho no <description>.
        # Mantê-lo permite conferir a base nova contra a antiga setor a setor.
        "renda_resp_media",
        "pct_esgoto_rede_geral",
        "pct_via_pavimentada",
        "pct_arborizacao_densa",
        "pct_lixo_coletado",
    ],
}

# Indicadores curados para avaliação imobiliária

Gerado por `scripts/02_dicionario.py` a partir de `config/indicadores.py`. **Não editar à mão.**

**Regra de inclusão:** a variável entra se for reconhecida no mercado como fator que valoriza ou deprecia o imóvel.

Resultado: **32 indicadores** derivados de **108 variáveis** do IBGE — de 1.531 disponíveis.
Isso reduz o download de 513 MB para **285 MB** (6 arquivos em vez de 13).

Todo percentual declara denominador explícito: contagem bruta de domicílios não é comparável entre setores de tamanhos diferentes.

## `alfabetizacao`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `pct_alfabetizados_15mais` | Alfabetização, 15 anos ou mais (%) | ▲ valoriza | `V00748…V00760 / V00644…V00656` |

- **`pct_alfabetizados_15mais`** — Treze faixas etárias no numerador e no denominador, pareadas uma a uma.

## `basico`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `pct_domicilios_vagos` | Domicílios vagos (%) | ▼ deprecia | `V0009 / V0003` |
| `pct_uso_ocasional` | Domicílios de uso ocasional (%) | ● contexto | `V0008 / V0003` |
| `media_moradores_domicilio` | Média de moradores por domicílio | ● contexto | `V0005` |
| `domicilios_particulares` | Domicílios particulares | ● contexto | `V0003` |
| `populacao_total` | População total | ● contexto | `V0001` |

- **`pct_domicilios_vagos`** — Vacância alta indica excesso de oferta ou esvaziamento.
- **`pct_uso_ocasional`** — Segunda residência. Valor alto caracteriza praça de veraneio, onde a sazonalidade domina a formação de preço.

## `demografia`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `pct_idosos` | População de 60 anos ou mais (%) | ● contexto | `V01040+V01041 / V01006` |
| `pct_criancas` | População de 0 a 9 anos (%) | ● contexto | `V01031+V01032 / V01006` |

- **`pct_idosos`** — Bairro consolidado e estável, com menor rotatividade.
- **`pct_criancas`** — Bairro em formação, demanda por escola e creche.

## `domicilio2`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `pct_agua_rede_geral` | Água de rede geral (%) | ▲ valoriza | `V00111 / V00111…V00118` |
| `pct_agua_encanada_interna` | Água encanada dentro do domicílio (%) | ▲ valoriza | `V00199 / V00199+V00200+V00201` |
| `pct_esgoto_rede_geral` | Esgoto em rede geral (%) | ▲ valoriza | `V00309+V00310 / V00309…V00316` |
| `pct_esgoto_inadequado` | Esgoto inadequado (%) | ▼ deprecia | `V00312…V00316 / V00309…V00316` |
| `pct_lixo_coletado` | Coleta de lixo (%) | ▲ valoriza | `V00397+V00398 / V00397…V00402` |
| `pct_lixo_destino_inadequado` | Lixo com destino inadequado (%) | ▼ deprecia | `V00399+V00400+V00401 / V00397…V00402` |
| `pct_sem_banheiro` | Sem banheiro exclusivo (%) | ▼ deprecia | `V00236+V00237+V00238 / V00232…V00238` |
| `pct_dois_ou_mais_banheiros` | Dois ou mais banheiros (%) | ▲ valoriza | `V00233+V00234+V00235 / V00232…V00238` |
| `pct_apartamento` | Apartamentos (%) | ● contexto | `V00100…V00104 / V00090…V00104` |
| `pct_casa_condominio` | Casas de vila ou condomínio (%) | ▲ valoriza | `V00095…V00099 / V00090…V00104` |

- **`pct_esgoto_rede_geral`** — Inclui fossa séptica ligada à rede (V00310), que a engenharia sanitária trata como solução adequada.
- **`pct_esgoto_inadequado`** — Fossa rudimentar, vala, lançamento em corpo hídrico e ausência de banheiro. Esgoto a céu aberto é um dos depreciadores mais fortes em avaliação urbana.
- **`pct_lixo_destino_inadequado`** — Queimado, enterrado ou jogado em terreno baldio.
- **`pct_dois_ou_mais_banheiros`** — Proxy de padrão construtivo do setor.
- **`pct_apartamento`** — Grau de verticalização. Não valoriza nem deprecia por si: define o segmento com que o imóvel avaliando compete.

## `entorno_domicilios`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `pct_via_pavimentada` | Via pavimentada (%) | ▲ valoriza | `V05006 / V05006+V05007` |
| `pct_calcada` | Calçada (%) | ▲ valoriza | `V05021 / V05021+V05022` |
| `pct_iluminacao_publica` | Iluminação pública (%) | ▲ valoriza | `V05012 / V05012+V05013` |
| `pct_bueiro` | Bueiro / drenagem (%) | ▲ valoriza | `V05009 / V05009+V05010` |
| `pct_arborizacao` | Arborização — ao menos 1 árvore (%) | ▲ valoriza | `V05031+V05032+V05033 / V05030…V05033` |
| `pct_arborizacao_densa` | Arborização densa — 5+ árvores (%) | ▲ valoriza | `V05033 / V05030…V05033` |
| `pct_ponto_onibus` | Ponto de ônibus na face (%) | ▲ valoriza | `V05015 / V05015+V05016` |
| `pct_ciclovia` | Via sinalizada para bicicleta (%) | ▲ valoriza | `V05018 / V05018+V05019` |
| `pct_rampa_acessibilidade` | Rampa para cadeirante (%) | ▲ valoriza | `V05027 / V05027+V05028` |
| `pct_obstaculo_calcada` | Obstáculo na calçada (%) | ▼ deprecia | `V05024 / V05024+V05025` |
| `entorno_domicilios_pesquisados` | Domicílios pesquisados no entorno | ● contexto | `V05000` |

- **`pct_bueiro`** — Ausência de drenagem sinaliza risco de alagamento, que deprecia de forma acentuada e persistente.
- **`pct_arborizacao`** — V05034 (saltado) fica fora do denominador: não foi observado, não é ausência de árvore.
- **`pct_ponto_onibus`** — Acessibilidade a transporte. Em praças de padrão alto o sinal pode inverter — verificar antes de usar.
- **`entorno_domicilios_pesquisados`** — Controle de qualidade. O bloco de entorno só foi aplicado em setores selecionados; valor ausente ou baixo significa que os percentuais acima são pouco confiáveis ou nulos.

## `renda_responsavel`

| Coluna no KMZ | Rótulo | Sentido | Fórmula |
|---|---|---|---|
| `renda_resp_mediana` | Renda mediana do responsável (R$) | ▲ valoriza | `V06006` |
| `renda_resp_media` | Renda média do responsável (R$) | ▲ valoriza | `V06004` |
| `renda_resp_per_capita_proxy` | Renda per capita — proxy (R$) | ▲ valoriza | `V06004*V06001 / V06002` |

- **`renda_resp_mediana`** — Mediana é mais robusta que a média: um único setor com outlier de renda não distorce a leitura.
- **`renda_resp_media`** — Sensível a outliers. Comparar com a mediana: divergência grande indica setor heterogêneo.
- **`renda_resp_per_capita_proxy`** — PROXY, não renda per capita real. V06004*V06001/V06002 ignora a renda dos demais moradores e subestima o valor. O Censo 2022 não publica renda domiciliar per capita por setor.

## Excluídos deliberadamente

**`cor_ou_raca`** — As 95 variáveis de cor ou raça, e todas as desagregações raciais em domicilio2 e alfabetizacao, ficam fora por decisão de projeto. Usar composição racial como preditor de valor imobiliário reproduz segregação histórica na forma de preço — é o mecanismo do redlining, e num laudo vira discriminação com aparência técnica. O efeito que essas variáveis capturariam já entra pela renda e pela infraestrutura, que são as causas defensáveis. Habilitar apenas com justificativa explícita e finalidade que não seja precificação.

**`obitos`** — As 93 variáveis de óbito no domicílio (jan/2019 a jul/2022) refletem sobretudo a mortalidade da pandemia. Não é atributo do imóvel nem do entorno e não tem leitura de valor estável.

**`parentesco`** — As 182 de composição familiar descrevem quem mora, não o imóvel nem a localização. Densidade e ciclo de vida já entram por indicadores mais diretos.

**`entorno_faces_e_moradores`** — As 70 variáveis de entorno medidas por face de quadra (V054xx) e por morador (V052xx) cobrem os mesmos temas já capturados por domicílio (V050xx). Usar as três seria triplicar a mesma informação em unidades incomparáveis.

**`domicilio3`** — As 148 variáveis do domicilio3 repetem as categorias do domicilio2 contadas por morador, criança e sexo. Para proporção de domicílios, que é o que interessa aqui, o domicilio2 é a base correta.

## Não publicados por setor no Censo 2022

Fatores que o mercado usaria, mas que a fonte não oferece nesta granularidade:

- **condicao_de_ocupacao** — Próprio, alugado, cedido ou financiado — existia em 2010, não publicado por setor em 2022.
- **comodos_e_dormitorios** — Número de cômodos e de dormitórios — idem.
- **energia_eletrica** — Não publicado por setor no Censo 2022. Precisaria vir da ANEEL ou da distribuidora local.
- **valor_do_aluguel** — Nunca foi publicado na granularidade de setor.

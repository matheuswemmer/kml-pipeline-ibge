# kml-pipeline-ibge

Pipeline reprodutível que enriquece a malha de **setores censitários do IBGE
(Censo 2022)** com indicadores socioeconômicos e urbanísticos e exporta um
**KML por município** — 5.570 arquivos, 468.097 setores, 3,26 GB.

Chave de tudo: `CD_SETOR`, string de 15 dígitos.

---

## Estado

Brasil inteiro gerado e validado.

| Etapa | Script | Situação |
|---|---|---|
| Catálogo de fontes | `config/sources.py` | 20 URLs, conferidas por sha256 |
| Download idempotente | `01_download.py` | ✅ |
| Dicionário unificado | `02_dicionario.py` | ✅ 1.531 variáveis com procedência |
| Município avulso | `03_exportar_kmz.py` | ✅ ferramenta de conferência |
| Base nacional | `04_base_nacional.py` | ✅ 468.099 setores × 32 indicadores |
| Lote por UF | `05_gerar_lote.py` | ✅ |
| Validação por UF | `06_validar_uf.py` | ✅ |
| Brasil inteiro | `07_brasil.py` | ✅ 27 UFs em ~14 min |
| Publicação no S3 | `08_publicar.py` | ✅ preserva os nomes em uso |

Documentação gerada, nunca editada à mão:
[inventário de fontes](docs/inventario_fontes.md) ·
[indicadores curados](docs/indicadores_curados.md) ·
[variável → origem](docs/variaveis_origem.csv)

Para o front: [prompt de adaptação](docs/prompt_lovable.md) ·
[prompt de diagnóstico](docs/prompt_lovable_diagnostico.md).

---

## Como rodar

```bash
pip install -r requirements.txt

python scripts/01_download.py --dicionarios --tabelas   # ~500 MB
python scripts/02_dicionario.py                          # dicionário + docs
python scripts/04_base_nacional.py                       # ~50 s, uma vez
python scripts/07_brasil.py --conjunto essenciais --processos 6
python scripts/08_publicar.py                            # prepara o envio
```

Um município só, para conferir algo pontual:

```bash
python scripts/03_exportar_kmz.py --uf SC --municipio 4209102
```

---

## Por que a pipeline é assim

Cada decisão abaixo veio de um defeito real encontrado durante o
desenvolvimento, quase sempre invisível para quem só olha o arquivo pronto.

### A geometria vem do GeoPackage, não do KMZ

Os KMZ do IBGE guardam os atributos numa tabela HTML dentro de
`<description>`. Extrair dali exige parsing posicional — e foi exatamente isso
que corrompeu a base herdada, onde `CD_SETOR` continha `"Urbana"` e `CD_UF`
continha o código do município. O GeoPackage por UF traz as mesmas colunas
tipadas, sem parsing.

### Reprojetar é obrigatório, e a prova não é visual

O GeoPackage está em **EPSG:4674 (SIRGAS 2000)**; KML exige **EPSG:4326**.
A conversão é explícita, aplicada uma vez por UF.

Comparamos a geometria gerada contra o KMZ oficial do IBGE nos 217 municípios
do Maranhão: **pior IoU 0,99999912, deslocamento máximo 0,0000 m** em 16.301
setores. É prova mais forte que conferência a olho.

### Setores partidos viram MultiPolygon

O IBGE publica alguns setores como várias linhas `Polygon`, uma por parte —
45 setores em 18 municípios de SC. Sem uni-los, o KML sai com placemarks
repetidos e a chave duplica.

### Geometria inválida derruba o município inteiro

Um anel auto-intersectante em São José (SC) fez o driver recusar a feição e
**perder os 423 setores do município**. É rara — uma em SC, nenhuma em MA ou
RO — mas fatal. `reparar_geometrias()` conserta e aborta se a área mudar mais
de 1%.

### O LIBKML não sobrescreve

Ele reabre o arquivo existente e **acrescenta outro `<Schema>`**. Cada
regeração empilhava um bloco duplicado sem alterar a contagem de feições,
então nenhuma validação acusava — Joinville chegou a ter três. Corrigido
apagando o destino antes de escrever, e a validação passou a contar os blocos.

### O balão precisa de HTML

O Google Earth não renderiza `ExtendedData`/`SchemaData` de forma confiável:
os valores existiam no arquivo mas só apareciam abrindo o XML. Não é acaso que
o próprio IBGE embute uma tabela HTML em `<description>`. Fazemos o mesmo, com
rótulos legíveis. Os dados continuam em `ExtendedData` para leitura por
software.

### Sem estilo, o mapa fica ilegível

Sem `<Style>`, o Google Earth preenche o polígono com branco semitransparente
e 16 mil setores viram um lençol opaco sobre a imagem de satélite. Aplicamos
contorno vermelho vazado — o mesmo da base em produção — declarado uma vez por
documento em vez de repetido em cada placemark.

---

## Ausência de dado nunca vira zero

O princípio que mais afeta a leitura dos arquivos.

O bloco de entorno do Censo 2022 **é urbano**: cobre 96% dos setores urbanos do
Maranhão e 0,6% dos rurais. Os 48% de ausência no estado não são falha de
amostragem — o Maranhão é 52% rural.

Como o LIBKML **omite o campo inteiro** quando o valor é nulo, um setor sem
dado apareceria com menos linhas no balão e nenhuma explicação. Por isso todo
arquivo carrega `COBERTURA_IBGE`, um campo de texto sempre preenchido:

| Valor | Significado |
|---|---|
| Dados completos | todos os indicadores presentes |
| Setor rural — o IBGE só pesquisa infraestrutura de rua em área urbana | comportamento normal da pesquisa |
| IBGE não divulgou a pesquisa de rua deste setor | lacuna real, 1,1% no MA |
| IBGE não divulgou dados deste setor | setor sem dado algum |
| Dados parciais do IBGE | combinações restantes |

Um contador de domicílios pesquisados não resolveria: ele é nulo justamente
nos setores que precisam da explicação, e sumiria junto.

### O `X` do sigilo estatístico

O IBGE marca com `X` as células que poderiam identificar pessoas. São
convertidas para nulo, nunca para zero — mas isso não basta quando o valor
entra numa soma.

Os percentuais de domicílio somavam o bloco de categorias como denominador, e
a soma **pulava os nulos** — tratando cada `X` como zero. Como a supressão
atinge 54,6% dos setores no bloco de esgoto, o denominador encolhia e o
percentual saía superestimado. No pior caso, um setor com 9 domicílios e
quatro células suprimidas exibia **100% de esgoto em rede geral** quando o
correto era 33%: o denominador havia colapsado até igualar o numerador. Isso
acontecia em 250 setores.

A correção usa `V00001` (total de domicílios) como denominador. Conferido que
os blocos de água, esgoto, lixo e banheiro somam **exatamente** `V00001` nos
setores sem supressão — resíduo zero em 204.414 casos no esgoto. O bloco de
espécie do domicílio não é exaustivo (13.221 setores divergem, porque há
espécies além de casa, vila e apartamento) e por isso mantém a soma do bloco.

Resta a supressão no **numerador**, que é irredutível: o dado está oculto na
fonte. Nesses casos o percentual é um piso, não um valor exato.

---

## Os indicadores

Regra de inclusão: **a variável entra se for reconhecida no mercado como fator
que valoriza ou deprecia o imóvel.** Das 1.531 publicadas por setor, 32 passam
— e um *conjunto* escolhe quais vão para o arquivo.

O conjunto `essenciais`, usado na geração atual, tem 7: renda per capita
estimada, renda mediana, renda média, esgoto em rede, via pavimentada,
arborização densa e coleta de lixo.

Detalhes, fórmulas e exclusões em
[docs/indicadores_curados.md](docs/indicadores_curados.md).

### Ressalvas que mudam a leitura

**“Renda per capita” não existe por setor.** O Censo publica *rendimento do
responsável* — `V06004` (média) e `V06006` (mediana). O proxy
`V06004 × V06001 / V06002` ignora a renda dos demais moradores e subestima;
por isso o nome carrega o aviso.

**Percentual de entorno é sobre domicílios, não sobre a rua.**
`pct_via_pavimentada` a 60% significa que 60% dos domicílios do setor ficam em
rua asfaltada.

**Arredondamento.** Percentuais são gravados com 2 casas. Com denominador
mediano de 195 domicílios, a menor variação real do dado é 0,51 ponto
percentual — as duas casas já são 51× mais finas do que a pesquisa comporta.

**Cor ou raça fica de fora por decisão de projeto.** Usar composição racial
como preditor de valor imobiliário reproduz segregação histórica na forma de
preço. O efeito já entra pela renda e pela infraestrutura, que são causas
defensáveis.

**Não existem por setor em 2022:** condição de ocupação (próprio/alugado),
cômodos, dormitórios e energia elétrica.

---

## Armadilhas da fonte

Descobertas cruzando o dicionário oficial com o cabeçalho real de cada CSV:

- **A coluna-chave tem quatro grafias** — `CD_SETOR`, `CD_setor`, `setor` e
  `COD_SETOR_M22FINAL`, conforme o arquivo.
- **A caixa da variável varia** — `v0001` em `basico`, `V00001` nos demais.
- **Entorno vem em três unidades incomparáveis** — domicílio (`V050xx`),
  morador (`V052xx`) e face de quadra (`V054xx`).
- **A malha e as tabelas não têm o mesmo universo** — 468.099 no `basico`,
  458.772 em renda e demografia, 340.965 no entorno.

---

## Validação

Nenhum arquivo é aceito sem ser **relido do disco** e conferido. A base
herdada passou meses com o schema trocado porque ninguém releu a saída.

Por arquivo, em `exportar.validar()`: contagem de feições, `CD_SETOR` com 15
dígitos e sem duplicata, colunas presentes, `COBERTURA_IBGE` preenchida em toda
feição, um único `<Schema>`, um `styleUrl` por placemark.

Por UF, em `06_validar_uf.py`: cobertura de municípios, reconciliação de
setores, integridade da chave, e — as duas que pegam corrupção no caminho de
escrita — **nulos e valores conferidos coluna a coluna contra o Parquet**.

```bash
python scripts/06_validar_uf.py --uf MA --conjunto essenciais
python tests/test_indicadores.py      # fórmulas contra o dicionário do IBGE
python tests/test_kml_otimizado.py    # enxugamento não altera geometria
```

A saída é **determinística**: execuções serial e paralela produzem arquivos
byte a byte idênticos.

---

## Publicação

Os arquivos no bucket têm nomes opacos por timestamp
(`AC/Acrelandia/1755867329246.kml`), registrados na tabela `klm_documents` do
Supabase. Subir com os nomes do IBGE criaria 5.570 objetos ao lado dos 5.494
existentes, e o site continuaria servindo os antigos.

`08_publicar.py` monta `publicacao/` espelhando exatamente as chaves do
bucket — um `aws s3 sync` sobrescreve cada arquivo no lugar e **nenhum link
muda**. Usa hardlink, então não duplica os 3,26 GB.

Ele também gera o SQL de atualização do banco, em lotes de 500 para caber no
editor do Supabase. O script não envia nada e não escreve no banco.

Passo a passo operacional:
[guia de publicação](https://claude.ai/code/artifact/4bac8ab1-ddd8-4d7e-935c-8b6fde8c21dd).

---

## Estrutura

```
config/sources.py        catálogo de URLs do IBGE, verificadas
config/indicadores.py    curadoria, conjuntos e exclusões
src/kmlpipe/             módulos reutilizáveis
scripts/NN_*.py          etapas numeradas
docs/                    gerado por 02_dicionario.py
data/raw/                como veio do IBGE, nunca modificado
data/processed/          base nacional em Parquet
output/<UF>/             KML municipais + manifesto
publicacao/              árvore espelhando as chaves do S3
```

`data/`, `output/`, `publicacao/` e `logs/` não são versionados: são
reproduzíveis e pesam GB.

---

## Princípios

- Nunca modificar arquivo original — toda transformação gera um novo.
- Ausência é `NULL`, nunca `0`, e o arquivo diz por que está ausente.
- Nenhum export sem releitura e validação automática.
- Documentação gerada por script, não escrita à mão.
- Nome de coluna declara o que ela é, inclusive quando é proxy.
- Toda execução é registrada e retomável.

# kml-pipeline-ibge

Pipeline reprodutível para enriquecer a malha de **setores censitários do IBGE
(Censo 2022)** com variáveis socioeconômicas e urbanísticas, e exportar um
**KMZ por município** (5.570 arquivos) com os atributos corretos e tipados.

Chave de junção de tudo: `CD_SETOR`, string de 15 dígitos.

---

## Estado atual

| Etapa | Script | Status |
|---|---|---|
| Catálogo de fontes verificado | `config/sources.py` | ✅ 20 URLs, todas 200 |
| Download idempotente | `scripts/01_download.py` | ✅ funcionando |
| Dicionário unificado (1.531 vars) | `scripts/02_dicionario.py` | ✅ conferido contra os CSV |
| Curadoria (32 indicadores) | `config/indicadores.py` | ✅ validada contra o dicionário |
| Leitura, junção e export | `scripts/03_exportar_kmz.py` | ✅ Joinville conferido |
| Rodar os 5.494 municípios | — | ⬜ a fazer |

Inventário completo de variáveis e sua procedência:
**[docs/inventario_fontes.md](docs/inventario_fontes.md)**.

---

## Decisões de arquitetura

### A geometria vem do GeoPackage, não do KMZ

Os KMZ oficiais do IBGE **não guardam os atributos em `ExtendedData`** — eles
embutem uma tabela HTML dentro de `<description>`:

```html
<center><table>...<th>CD_SETOR</th><td>110004905000001</td>...</table></center>
```

Extrair atributo de KMZ exige parsear esse HTML, o que é frágil e foi
justamente onde a tentativa anterior quebrou (ver *Lição aprendida*). O
GeoPackage por UF traz as mesmas 29 colunas já **tipadas e nomeadas**, sem
nenhum parsing. Ele é a fonte da verdade da geometria; **KMZ é só formato de
saída**.

### Reprojeção obrigatória na exportação

O GeoPackage do IBGE está em **EPSG:4674 (SIRGAS 2000)**. KML exige
**EPSG:4326 (WGS 84)**. A conversão precisa ser explícita no passo de export —
sem ela os polígonos saem deslocados.

### O canônico é tabular, o KMZ é derivado

A base consolidada vive em Parquet (`data/processed/`), com um registro por
setor. Os 5.570 KMZ são gerados a partir dela. Regerar a saída inteira nunca
depende de rebaixar nada.

---

## Lição aprendida: o KML corrompido

O arquivo herdado `1755893274252.kml` (Joinville, 1.064 setores) tem o
`<Schema>` **desalinhado em uma posição** em relação aos `<SimpleData>`:

| Campo declarado | Valor real armazenado |
|---|---|
| `CD_SETOR` | `Urbana` / `Rural` (é `SITUACAO`) |
| `Valor_rendimento_nominal_mensal` | `1`, `2`, `3` (é `CD_SIT`) |
| `CD_UF` | `4209102` (é `CD_MUN`) |
| `NM_UF` | `Joinville` (é `NM_MUN`) |

O dado bom sobreviveu fora do `ExtendedData`: `<name>` tem o `CD_SETOR` correto
e `<description>` tem a renda. **Por isso a pipeline reconstrói do zero a partir
da fonte oficial em vez de corrigir o arquivo derivado.**

Todo export passa por validação automática antes de ser publicado: o arquivo é
relido do disco e conferido em contagem de feições, integridade do `CD_SETOR`
(15 dígitos, sem duplicata) e presença de todas as colunas.

**Joinville serviu de prova.** O KMZ gerado tem os mesmos 1.064 setores do
arquivo herdado, e os 1.044 valores de renda não suprimidos batem na segunda
casa decimal com o que estava no `<description>` antigo — confirmando que
aquele número era o `V06004` (rendimento médio do responsável). Os 10 setores
que o IBGE suprime por sigilo (`X`) saem nulos, não zero.

---

## Ressalvas sobre as variáveis

### "Renda per capita" não existe por setor no Censo 2022

O que o IBGE publica por setor é **rendimento do responsável pelo domicílio**:

| Variável | Significado |
|---|---|
| `V06001` | Pessoas responsáveis em domicílios particulares permanentes ocupados |
| `V06002` | Moradores em domicílios particulares permanentes ocupados |
| `V06004` | Rendimento nominal **médio** mensal do responsável |
| `V06006` | Rendimento nominal **mediano** mensal do responsável |

Um proxy de renda per capita pode ser derivado como
`V06004 * V06001 / V06002`, mas ele **ignora a renda dos demais moradores** e
subestima o valor real. A coluna derivada deve ser nomeada de forma honesta
(ex.: `renda_resp_per_capita_proxy`) e nunca rotulada como "renda per capita".

Para análise de mercado, `V06006` (mediana) costuma ser mais robusto que a
média, que é puxada por outliers.

### A coluna-chave tem quatro grafias diferentes

`CD_SETOR`, `CD_setor`, `setor` e `COD_SETOR_M22FINAL`, conforme o arquivo. E a
caixa do nome da variável também varia (`v0001` em `basico`, `V00001` nos
demais). Um merge ingênuo por nome de coluna quebra. O dicionário unificado
guarda a grafia real de cada uma em `coluna_chave_no_csv` e `variavel_no_csv`.

### O mesmo tema aparece em três unidades de medida

Entorno é publicado por domicílio (`V050xx`), por morador (`V052xx`) e por face
de quadra (`V054xx`) — recortes distintos do mesmo questionário. Escolher um,
documentar a escolha, e nunca somar entre eles.

### Entorno: são contagens de domicílios, não percentuais

`V05006` = domicílios em face com via pavimentada — **não** é "% pavimentado".
O denominador é `V05000` (domicílios no setor pesquisado para entorno). A
padronização precisa gerar os percentuais explicitamente.

| Tema | Sim | Não | Não declarado |
|---|---|---|---|
| Via pavimentada | `V05006` | `V05007` | `V05008` |
| Bueiro | `V05009` | `V05010` | `V05011` |
| Iluminação pública | `V05012` | `V05013` | `V05014` |
| Ponto de ônibus | `V05015` | `V05016` | `V05017` |
| Via sinalizada p/ bicicleta | `V05018` | `V05019` | `V05020` |
| Calçada | `V05021` | `V05022` | `V05023` |
| Obstáculo na calçada | `V05024` | `V05025` | `V05026` |
| Rampa para cadeirante | `V05027` | `V05028` | `V05029` |

Arborização é ordinal, não binária: `V05030` sem árvores, `V05031` 1–2,
`V05032` 3–4, `V05033` 5 ou mais, `V05034` saltado.

**Cobertura parcial:** o bloco de entorno só foi aplicado em setores
selecionados. Setores fora da amostra ficam sem esses dados — a junção deve ser
`LEFT` a partir da malha, e a ausência precisa ser `NULL`, nunca `0`.

---

## Uso

```bash
pip install -r requirements.txt
python scripts/01_download.py --dicionarios --tabelas --uf SC
python scripts/02_dicionario.py
python scripts/03_exportar_kmz.py --uf SC --municipio 4209102 --kml
```

Os arquivos caem em `data/raw/` com o nome original do IBGE e são registrados
em `data/raw/manifest.json`. Re-executar não rebaixa o que já está íntegro.

### Procedência

O manifesto registra o grau de conferência de cada arquivo, não quem o colocou
ali — essa informação não é recuperável, e um rótulo errado é pior que nenhum:

| `conferencia` | Significa |
|---|---|
| `nao_conferido` | está em disco, nada foi comparado |
| `tamanho` | o byte count bate com o `content-length` do servidor |
| `sha256` | rebaixamos e o hash é idêntico ao do IBGE |

Só `sha256` é prova. Para elevar tudo que está em disco a esse nível:

```bash
python scripts/01_download.py --verificar
```

Uma conferência já registrada nunca é rebaixada por uma execução mais fraca.

Volume total das fontes: **~2,0 GB** (dos quais 1,5 GB é o GeoPackage do Brasil,
opcional — dá para trabalhar UF a UF).

---

## Estrutura

```
config/sources.py       catálogo de URLs do IBGE (verificadas)
src/kmlpipe/            módulos reutilizáveis (paths, logging, download)
scripts/NN_*.py         etapas numeradas da pipeline
data/raw/               como veio do IBGE — nunca modificado
data/interim/           extraído, nomes originais
data/processed/         padronizado, parquet, um registro por setor
data/dicts/             dicionários de variáveis
output/                 KMZ municipais entregues
logs/                   um log por execução
```

`data/`, `output/` e `logs/` não são versionados: são reproduzíveis pela
pipeline e pesam GB.

---

## Princípios

- Nunca modificar arquivo original — toda transformação gera um novo arquivo.
- Colunas em `snake_case`; scripts numerados; um log por execução.
- Ausência de dado é `NULL`, nunca `0`.
- Nenhum export sem validação automática de esquema.
- Nome de coluna derivada declara o que ela é, inclusive quando é proxy.

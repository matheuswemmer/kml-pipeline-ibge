# Inventário de fontes e variáveis — Censo 2022 por setor censitário

Gerado por `scripts/02_dicionario.py`. **Não editar à mão.**

Cada variável foi conferida contra duas fontes independentes: o dicionário
oficial do IBGE e o cabeçalho real do CSV, lido direto do ZIP remoto via
*range request* (sem baixar os arquivos inteiros).

**1531 variáveis** em **13 arquivos**. Nenhuma
variável aparece em dois arquivos: as faixas são contíguas e disjuntas.

## Qual variável vem de qual arquivo

| Arquivo (chave em `sources.py`) | Vars | Faixa | Unidade | Coluna-chave no CSV | MB |
|---|---:|---|---|---|---:|
| `basico` | 9 | `V0001`–`V0009` | Setor | `CD_SETOR` | 15.4 |
| `domicilio1` | 89 | `V00001`–`V00089` | Domicílio | `CD_setor` | 24.2 |
| `domicilio2` | 406 | `V00090`–`V00495` | Domicílio | `setor` | 84.0 |
| `domicilio3` | 148 | `V00496`–`V00643` | Domicílio | `setor` | 52.7 |
| `alfabetizacao` | 362 | `V00644`–`V01005` | Pessoa | `CD_setor` | 142.1 |
| `demografia` | 36 | `V01006`–`V01041` | Pessoa | `CD_setor` | 22.6 |
| `parentesco` | 182 | `V01042`–`V01223` | Pessoa | `CD_SETOR` | 62.9 |
| `obitos` | 93 | `V01224`–`V01316` | Pessoa | `CD_SETOR` | 20.6 |
| `cor_ou_raca` | 95 | `V01317`–`V01411` | Pessoa | `CD_SETOR` | 43.8 |
| `entorno_domicilios` | 35 | `V05000`–`V05034` | Domicílio | `CD_setor` | 11.9 |
| `entorno_moradores` | 35 | `V05200`–`V05234` | Pessoa | `CD_setor` | 13.0 |
| `entorno_faces` | 35 | `V05400`–`V05434` | Face de quadra | `COD_SETOR_M22FINAL` | 10.3 |
| `renda_responsavel` | 6 | `V06001`–`V06006` | Responsável | `CD_SETOR` | 9.4 |

Volume total dos CSV: **513 MB** compactados.

## Armadilhas confirmadas

**1. A coluna-chave tem quatro grafias diferentes.** Um merge ingênuo quebra:

- `CD_SETOR` → `basico`, `parentesco`, `obitos`, `cor_ou_raca`, `renda_responsavel`
- `CD_setor` → `domicilio1`, `alfabetizacao`, `demografia`, `entorno_domicilios`, `entorno_moradores`
- `setor` → `domicilio2`, `domicilio3`
- `COD_SETOR_M22FINAL` → `entorno_faces`

**2. A caixa do nome da variável varia.** `basico` usa `v0001` minúsculo;
os demais usam maiúsculo (`V00001`). A coluna `variavel_no_csv` do dicionário
unificado guarda a grafia exata de cada uma, para ler sem adivinhar.

**3. `basico` repete as 29 colunas de contexto da malha** (`NM_MUN`, `CD_UF`, …),
redundantes com o GeoPackage. Devem ser descartadas na junção.

**4. O mesmo tema aparece em três unidades de medida diferentes.** Entorno é
publicado por domicílio (`V050xx`), por morador (`V052xx`) e por face de quadra
(`V054xx`). São recortes distintos do mesmo questionário — escolher um e
documentar a escolha, nunca somar entre eles.

## Cobertura por tema

| Tema | Variáveis | Arquivos |
|---|---:|---|
| Renda do responsável | 6 | `renda_responsavel` |
| Demografia (sexo e idade) | 36 | `demografia` |
| Alfabetização | 362 | `alfabetizacao` |
| Cor ou raça | 95 | `cor_ou_raca` |
| Parentesco / composição familiar | 182 | `parentesco` |
| Óbitos no domicílio | 93 | `obitos` |
| Arborização | 15 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Pavimentação da via | 9 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Calçada | 18 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Rampa para cadeirante | 9 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Iluminação pública | 9 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Bueiro | 9 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Ponto de ônibus | 9 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Via sinalizada para bicicleta | 12 | `entorno_domicilios`, `entorno_faces`, `entorno_moradores` |
| Abastecimento de água | 60 | `domicilio2`, `domicilio3` |
| Destinação do esgoto | 120 | `domicilio2`, `domicilio3` |
| Destino do lixo | 90 | `domicilio2`, `domicilio3` |
| Banheiros no domicílio | 221 | `domicilio2`, `domicilio3` |
| Energia elétrica | **0 — não publicado por setor** | — |

> **Energia elétrica não é publicada por setor censitário no Censo 2022.**
> O README do projeto anterior listava esse indicador como meta; nesta
> granularidade ele não existe e precisaria vir de outra fonte.

## Não incluídos no catálogo

Existem no FTP mas ficaram fora de `config/sources.py`: são recortes de
populações específicas, com a maioria dos setores sem dado.

- `Agregados_por_setores_domicilios_indigenas_BR.zip` (`V01500`+)
- `Agregados_por_setores_pessoas_indigenas_BR.zip`
- `Agregados_por_setores_domicilios_quilombolas_BR.zip` (`V03000`+)
- `Agregados_por_setores_pessoas_quilombolas_BR.zip`

Basta acrescentá-los a `TABELAS` se forem necessários.

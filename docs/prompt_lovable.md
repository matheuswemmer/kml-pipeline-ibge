# Prompt para o Lovable — adaptar o front ao novo KML

Copie o bloco abaixo inteiro e cole no Lovable. Ele é autocontido: não depende
de nenhum contexto anterior da conversa.

---

Os arquivos KML que a aplicação lê foram regerados com um formato novo. Preciso
que você adapte o código de leitura. Abaixo está exatamente o que mudou.

## O que quebra hoje

A tag `<description>` **deixou de conter um número** e passou a conter uma
tabela HTML dentro de CDATA. Qualquer código que faça `parseFloat(description)`
ou trate esse campo como valor numérico vai falhar.

**Antes:**

```xml
<Placemark id="4209102_Joinville.1">
  <name>420910205000001</name>
  <description>11061,18</description>
  <Style><LineStyle><color>ff0000ff</color></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>
  <ExtendedData><SchemaData schemaUrl="#4209102_Joinville">
    <SimpleData name="CD_SETOR">Urbana</SimpleData>
    <SimpleData name="Valor_rendimento_nominal_mensal">1</SimpleData>
    ...
```

**Agora:**

```xml
<Placemark id="itaparica_2916104_setores_CD2022.1">
  <name>291610405000001</name><styleUrl>#setor</styleUrl>
  <description><![CDATA[<table>...</table>]]></description>
  <ExtendedData>
    <SchemaData schemaUrl="#itaparica_2916104_setores_CD2022.schema">
      <SimpleData name="CD_SETOR">291610405000001</SimpleData>
      <SimpleData name="NM_MUN">Itaparica</SimpleData>
      <SimpleData name="CD_MUN">2916104</SimpleData>
      <SimpleData name="NM_DIST">Itaparica</SimpleData>
      <SimpleData name="SITUACAO">Urbana</SimpleData>
      <SimpleData name="AREA_KM2">0.127874763658598</SimpleData>
      <SimpleData name="COBERTURA_IBGE">Dados completos</SimpleData>
      <SimpleData name="renda_resp_per_capita_proxy">1425.36</SimpleData>
      <SimpleData name="renda_resp_mediana">2000</SimpleData>
      <SimpleData name="renda_resp_media">3547.21</SimpleData>
      <SimpleData name="pct_esgoto_rede_geral">100</SimpleData>
      <SimpleData name="pct_via_pavimentada">100</SimpleData>
      <SimpleData name="pct_arborizacao_densa">30.7</SimpleData>
      <SimpleData name="pct_lixo_coletado">100</SimpleData>
    </SchemaData>
  </ExtendedData>
  <Polygon>...</Polygon>
</Placemark>
```

## Mudança principal

Onde hoje você lê o valor da renda de `<description>`, passe a ler o campo
`renda_resp_media` de dentro de `<ExtendedData>`. É exatamente o mesmo número
que estava em `description` antes — mesma variável do IBGE, conferida setor a
setor.

**Atenção ao separador decimal.** O `description` antigo usava vírgula
(`11061,18`). O `ExtendedData` usa **ponto** (`3547.21`), no padrão XML. Se
houver alguma troca de vírgula por ponto no parser atual, ela precisa sair —
senão `3547.21` vira `354721`.

## Campos disponíveis agora

Identificação:

| Campo | Tipo | Exemplo |
|---|---|---|
| `CD_SETOR` | texto, 15 dígitos | `291610405000001` |
| `NM_MUN` | texto | `Itaparica` |
| `CD_MUN` | texto, 7 dígitos | `2916104` |
| `NM_DIST` | texto | `Itaparica` |
| `NM_BAIRRO` | texto | `Centro` |
| `SITUACAO` | texto | `Urbana` ou `Rural` |
| `AREA_KM2` | número | `0.127874763658598` |
| `COBERTURA_IBGE` | texto | `Dados completos` |

Indicadores, todos numéricos com ponto decimal:

| Campo | Significado | Unidade |
|---|---|---|
| `renda_resp_media` | Renda média do responsável | R$ |
| `renda_resp_mediana` | Renda mediana do responsável | R$ |
| `renda_resp_per_capita_proxy` | Renda per capita estimada | R$ |
| `pct_esgoto_rede_geral` | Esgoto em rede geral | % dos domicílios |
| `pct_via_pavimentada` | Via pavimentada | % dos domicílios |
| `pct_arborizacao_densa` | Arborização densa, 5 ou mais árvores | % dos domicílios |
| `pct_lixo_coletado` | Coleta de lixo | % dos domicílios |

Os `pct_*` são **percentuais de domicílios**, não de área nem de extensão de
rua. `pct_via_pavimentada` em 60 significa que 60% dos domicílios daquele setor
ficam em rua asfaltada.

## Campo ausente não é campo vazio

Quando o IBGE não tem o dado, a linha `<SimpleData>` **não é gerada**. Ela
simplesmente não existe no XML — não vem vazia nem com zero.

O parser não pode assumir que todo placemark tem todos os campos. Trate ausência
como "sem dado" e mostre um traço ou deixe em branco, **nunca zero**. Um setor
sem `pct_via_pavimentada` não é um setor com 0% de pavimentação.

`CD_SETOR`, `NM_MUN`, `CD_MUN`, `SITUACAO`, `AREA_KM2` e `COBERTURA_IBGE`
estão sempre presentes.

## Use o COBERTURA_IBGE na interface

Esse campo existe para explicar ao usuário por que faltam valores. Mostre o
texto dele sempre que algum indicador estiver ausente. Os valores possíveis:

- `Dados completos`
- `Setor rural — o IBGE só pesquisa infraestrutura de rua em área urbana`
- `IBGE não divulgou a pesquisa de rua deste setor`
- `IBGE não divulgou dados deste setor`
- `Dados parciais do IBGE`

O primeiro é o caso normal e não precisa de destaque. Os outros explicam a
ausência — sem eles o usuário acha que o mapa está quebrado.

Metade dos setores do Maranhão cai no caso rural, então isso não é exceção
rara: é comportamento esperado em boa parte do país.

## Estilo agora é compartilhado

Antes cada placemark trazia seu próprio bloco `<Style>`. Agora existe **um
único** `<Style id="setor">` no início do documento, e cada placemark aponta
para ele com `<styleUrl>#setor</styleUrl>`.

A aparência é a mesma — contorno vermelho, polígono vazado. Mas se o código
procura `<Style>` dentro de cada `<Placemark>`, não vai mais achar. Se a
aplicação aplica o próprio estilo ao renderizar, ignore esta seção.

## Campos que deixaram de existir

O formato antigo tinha o schema desalinhado: `CD_SETOR` continha `"Urbana"`,
`CD_UF` continha o código do município, e havia um campo
`Valor_rendimento_nominal_mensal` que trazia `1`, `2` ou `3` em vez de renda.
Todos esses sumiram, junto com `CD_REGIAO`, `NM_REGIAO`, `CD_UF`, `NM_UF`,
`CD_SIT`, `CD_TIPO`, `CD_SUBDIST`, `NM_SUBDIST`, `CD_NU`, `NM_NU`, `CD_FCU`,
`NM_FCU`, `CD_AGLOM`, `NM_AGLOM`, `CD_RGINT`, `NM_RGINT`, `CD_RGI`, `NM_RGI`,
`CD_CONCURB` e `NM_CONCURB`.

Se alguma tela usa algum desses, ela precisa passar a usar os campos novos da
tabela de identificação acima.

## O que não mudou

- `<name>` continua sendo o `CD_SETOR` de 15 dígitos.
- Os nomes dos arquivos no bucket são exatamente os mesmos.
- Os caminhos registrados no banco continuam válidos.
- A geometria é idêntica: mesmas coordenadas, mesmo sistema (WGS 84 / EPSG:4326).
- A quantidade de setores por município é a mesma.

Não altere nada relacionado a URLs, rotas, nomes de arquivo ou consulta ao
banco. A mudança é só na leitura do conteúdo do KML.

## Como testar

Baixe o arquivo de Itaparica (BA) e verifique que a tela mostra, para o setor
`291610405000001`:

- Renda média R$ 3.547,21
- Renda mediana R$ 2.000,00
- Renda per capita estimada R$ 1.425,36
- Esgoto em rede geral 100%
- Via pavimentada 100%
- Arborização densa 30,68% — o valor no `ExtendedData` é `30.68`
- Coleta de lixo 100%

Se você exibir com uma casa decimal, `30,7%` também está correto; o dado
guardado tem duas.

Depois teste um município rural, onde vários indicadores estarão ausentes e o
`COBERTURA_IBGE` deve aparecer explicando o motivo.

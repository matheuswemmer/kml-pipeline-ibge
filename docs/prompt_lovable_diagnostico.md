# Prompt de diagnóstico para o Lovable

O front está exibindo dados do formato antigo do KML, mesmo com o arquivo novo
já no bucket. Este prompt pede investigação antes de correção — a causa mais
provável é cache, e mexer no parser sem confirmar isso mascara o problema.

Copie o bloco abaixo inteiro.

---

A aplicação está exibindo o conteúdo antigo de um arquivo KML que já foi
substituído no S3. Preciso que você **investigue a causa antes de alterar
qualquer código**. Não altere o parser ainda.

## O sintoma

Ao abrir o setor `520880605000118` (Goianira, GO), a tela mostra:

```
Município        Goianira
Situação         0
Área (km²)       0,00 km²
Renda IBGE 2022 - Proxy         —
Renda média do responsável      —
Renda mediana do responsável    —
Esgoto em rede geral            —
Via pavimentada                 —
Arborização densa               —
Coleta de lixo                  —
CD AGLOM         5201
CD DIST          52088060500
CD REGIAO        52
CD RGI           5208707
CD RGINT         520001
CD SIT           55.93597392509558
CD TIPO          5
CD UF            5208806
NM AGLOM         Goiânia
NM REGIAO        Goiás
NM RGI           Goiânia/GO
NM RGINT         Goiânia
NM UF            Goianira
Valor Rendimento Nominal Mensal    8
```

## O que o arquivo no bucket contém hoje

O objeto `GO/Goianira/1755882187190.kml`, no bucket de produção, foi
substituído. Ele tem **567.146 bytes** (o antigo tinha 499.765) e, para esse
mesmo setor, contém:

```
CD_SETOR                       520880605000118
NM_MUN                         Goianira
CD_MUN                         5208806
NM_DIST                        Goianira
SITUACAO                       Rural
AREA_KM2                       55.9359739250956
COBERTURA_IBGE                 Setor rural — o IBGE só pesquisa infraestrutura de rua em área urbana
renda_resp_per_capita_proxy    869.58
renda_resp_mediana             1800
renda_resp_media               2415.49
pct_esgoto_rede_geral          0
pct_lixo_coletado              58.73
```

Os campos `pct_via_pavimentada` e `pct_arborizacao_densa` **não existem** nesse
placemark — o IBGE não pesquisa entorno em setor rural, e por isso a linha não
é gerada. Ausência é esperada, não é erro.

Os campos `CD_AGLOM`, `CD_REGIAO`, `CD_SIT`, `CD_TIPO`, `CD_UF`, `NM_UF`,
`NM_AGLOM`, `NM_REGIAO`, `NM_RGI`, `NM_RGINT`, `CD_DIST`, `CD_RGI` e
`Valor_rendimento_nominal_mensal` **não existem em nenhum lugar do arquivo
novo**. Foram removidos.

## O upload já foi verificado — não é o arquivo

Comparei os 5.570 objetos do bucket com os arquivos gerados, um a um, por
tamanho: **zero ausentes, zero divergentes**. Todo objeto no S3 é a versão
nova. Também não é falha global de cache, porque **alguns municípios já exibem
o conteúdo novo e outros não** — o problema é por arquivo.

## O que isso significa

A tela está renderizando fielmente o arquivo **antigo**. Repare que
`55.93597392509558` aparece no campo `CD SIT`, quando no arquivo novo esse
número é o `AREA_KM2`. O formato antigo tinha o schema deslocado uma posição,
e a tela reproduz esse deslocamento — sinal de que está lendo o arquivo velho,
não o novo.

Como o objeto no S3 já é o novo, a aplicação está usando uma cópia guardada em
algum lugar.

## O que investigar, nesta ordem

**1. De onde vem o arquivo que a tela usa.** Rastreie o caminho completo:
qual componente busca o KML, por qual URL, e se passa por alguma função
intermediária. Me diga a URL exata que é chamada.

**2. Se existe cache em qualquer camada.** Como o comportamento varia de
município para município, procure cache indexado por URL ou por identificador
do documento — não um cache global da aplicação. Verifique todas:
- cache do navegador na requisição do KML (`Cache-Control`, `ETag`)
- `localStorage`, `sessionStorage` ou IndexedDB guardando o KML ou o resultado
  do parse
- service worker interceptando a requisição
- cache de biblioteca de dados (`staleTime` / `cacheTime` do React Query,
  SWR, ou equivalente)
- CDN ou proxy entre a aplicação e o S3
- alguma tabela ou storage do Supabase guardando o conteúdo já processado

**3. Se há cópia local do arquivo.** Procure no repositório qualquer `.kml`
versionado, seed, fixture ou mock que possa estar sendo usado no lugar do
arquivo remoto.

**4. Se o parse é feito e guardado.** Se a aplicação processa o KML uma vez e
salva o resultado, o conteúdo antigo pode ter ficado persistido mesmo com o
arquivo novo disponível.

## Como confirmar

Depois de identificar a origem, faça a aplicação buscar o arquivo ignorando
qualquer cache e me diga se `SITUACAO` passa a mostrar `Rural` em vez de `0`.
Esse é o teste decisivo: `Rural` só existe no arquivo novo.

Compare também um município que **já funciona** com um que não funciona. A
diferença entre os dois é a pista mais direta: se os que falham são justamente
os que foram abertos no site antes da troca dos arquivos, o cache é por URL
visitada.

## Um ajuste que vale fazer de qualquer forma

Independentemente da causa, a tela não deveria listar campos desconhecidos.
Hoje ela despeja tudo que encontra no `ExtendedData`, e por isso os treze
campos antigos aparecem no fim da lista. Exiba apenas os campos que a
aplicação conhece e mapeia; ignore o restante silenciosamente.

Assim, se algum arquivo antigo sobrar em qualquer canto, a interface não fica
poluída — e o problema fica visível como valor ausente, que é honesto, em vez
de virar uma lista de códigos sem sentido para o usuário.

## Não faça ainda

Não altere a lógica de leitura do `ExtendedData` nem os nomes de campo antes
de responder o que encontrou. O parser provavelmente está correto — ele está
lendo bem, só está lendo o arquivo errado.

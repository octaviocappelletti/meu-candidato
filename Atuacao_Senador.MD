# Atuação Parlamentar — Senadores

Documentação da feature de dados legislativos para senadores candidatos à reeleição em 2022.
Complementa `Atuacao_Parlamentar.MD`, que cobre os deputados federais.

---

## O que foi construído

### Script de ingestão (`data/scripts/ingestao_senadores.py`)

Pipeline Python que coleta e agrega dados de atuação legislativa dos 5 senadores
candidatos à reeleição em 2022 com match confirmado na API do Senado Federal.

O script executa cinco etapas por senador:

1. **Mandatos** — `GET /dadosabertos/senador/{codigo}/mandatos` (XML)
   Extrai a data de início do mandato de senador mais antiga para usar como filtro
   temporal nas etapas seguintes, excluindo automaticamente o período em que o
   parlamentar era deputado federal.

2. **Autorias (PEC + PL)** — `GET /dadosabertos/senador/{codigo}/autorias` (XML)
   Retorna todas as proposições de autoria (ou coautoria) do senador com o campo
   `IndicadorAutorPrincipal` (Sim/Não) já embutido — sem chamadas extras por proposição.
   Filtra client-side pelas siglas `PEC`, `PLS` e `PL`.

3. **Proposições aprovadas (PEC)** — `GET /dadosabertos/processo?codigoParlamentarAutor={codigo}&sigla=PEC&dataInicio={data_inicio}` (JSON)
   Retorna todas as PECs do senador desde o início do mandato. Filtra client-side
   pelo campo `normaGerada` (preenchido = transformada em norma jurídica).
   `siglaSituacao` não é usado combinado com `codigoParlamentarAutor` — retorna
   vazio (bug da API). `situacaoAtual` também não é confiável — usar só `normaGerada`.
   Cruza com os dados da Etapa 2 via `(numero, ano)` para determinar `autor_principal`.
   Deduplica client-side — a API retorna duplicatas para algumas proposições.

4. **Proposições aprovadas (PL)** — `GET /dadosabertos/processo?codigoParlamentarAutor={codigo}&sigla=PL&dataInicio={data_inicio}` (JSON)
   Idêntico à Etapa 3, mas para PLs (inclui PLS pré-2019 via mesma sigla normalizada).

5. **Emendas a MPV** — `GET /dadosabertos/processo/emenda?codigoParlamentarAutor={codigo}&dataInicio={data_inicio}` (JSON)
   Filtra client-side via regex `\bMPV\b` no campo `identificacao`.
   Determina autor único verificando ausência de `;` no campo `autoria`.
   **Coletado mas não exibido no front-end** (ver dificuldade #7).

### Métricas coletadas (10/10)

| # | Métrica | Campo no JSON |
|---|---|---|
| 1 | Total de PECs (autor/coautor) | `pec_total` |
| 2 | PECs como autor principal | `pec_autor_principal` |
| 3 | Total de PLs (autor/coautor) | `pl_total` |
| 4 | PLs como autor principal | `pl_autor_principal` |
| 5 | PECs aprovadas (normaGerada preenchido) | `pec_aprovadas` |
| 6 | PECs aprovadas como autor principal | `pec_aprovadas_autor_principal` |
| 7 | PLs aprovadas (normaGerada preenchido) | `pl_aprovadas` |
| 8 | PLs aprovadas como autor principal | `pl_aprovadas_autor_principal` |
| 9 | Total de emendas a MPV | `emendas_mpv_total` |
| 10 | Emendas a MPV como único autor | `emendas_mpv_autor_unico` |

> **Nota técnica sobre MPVs:** Medidas Provisórias são de iniciativa exclusiva da
> Presidência da República. Senadores nunca figuram como autores de MPVs — apenas
> como autores de emendas a elas.

### JSON por senador (`public/legislativo/legislativo.json`)

Campos adicionados aos registros de senadores:

| Campo | Tipo | Descrição |
|---|---|---|
| `pec_total` | int | Total de PECs de autoria (inclui coautorias) |
| `pec_autor_principal` | int | PECs onde `IndicadorAutorPrincipal=Sim` |
| `pl_total` | int | Total de PLs (PLS pré-2019 + PL pós-2019) |
| `pl_autor_principal` | int | PLs onde `IndicadorAutorPrincipal=Sim` |
| `pec_aprovadas` | int | PECs com `normaGerada` preenchido |
| `pec_aprovadas_autor_principal` | int | PECs aprovadas onde o senador é autor principal |
| `pl_aprovadas` | int | PLs com `normaGerada` preenchido |
| `pl_aprovadas_autor_principal` | int | PLs aprovadas onde o senador é autor principal |
| `aprovadas_lista` | array | Lista de PEC+PL aprovadas com sigla, número, ano, ementa, url, normaGerada |
| `emendas_mpv_total` | int | Emendas a MPV desde o início do mandato |
| `emendas_mpv_autor_unico` | int | Emendas sem coautores (campo `autoria` sem `;`) |
| `pec_lista` | array | Lista completa de PECs com sigla, número, ano, ementa, url, data |
| `pl_lista` | array | Lista completa de PLs |
| `emendas_mpv_lista` | array | Lista completa de emendas MPV com identificacao, ementa, url, data, autor_unico |

Campos herdados da estrutura de deputados (compatibilidade com o componente React):

| Campo | Valor para senadores |
|---|---|
| `total_apresentadas` | `pec_total + pl_total` |
| `total_aprovadas` | `pec_aprovadas + pl_aprovadas` |
| `por_tipo` | `{"PEC": N, "PL": N}` |
| `por_ano` | Série temporal de PEC + PL combinados |
| `exemplos` | 5 proposições mais recentes (PEC + PL) |
| `funil` | ausente (não implementado para senadores) |

### Resultado final (5 senadores, coleta em 2026-07-09)

**Totais e autorias:**

| Senador | UF | Partido | id_parlamentar | PEC | PEC principal | PL | PL principal | MPV | MPV único |
|---|---|---|---|---|---|---|---|---|---|
| ROMÁRIO | RJ | PL | 5322 | 242 | 4 | 180 | 176 | 55 | 55 |
| OTTO ALENCAR | BA | PSD | 5523 | 227 | 4 | 51 | 45 | 25 | 25 |
| WELLINGTON FAGUNDES | MT | PL | 1173 | 135 | 12 | 100 | 94 | 145 | 145 |
| DAVI | AP | UNIÃO | 3830 | 170 | 5 | 42 | 42 | 30 | 30 |
| OMAR AZIZ | AM | PSD | 5525 | 162 | 1 | 17 | 17 | 8 | 8 |

**Aprovações (coleta em 2026-07-09):**

| Senador | PEC aprov. | PEC aprov. principal | PL aprov. | PL aprov. principal | Total lista |
|---|---|---|---|---|---|
| ROMÁRIO | 4 | 0 | 4 | 2 | 8 |
| OTTO ALENCAR | 14 | 1 | 2 | 1 | 16 |
| WELLINGTON FAGUNDES | 6 | 0 | 8 | 4 | 14 |
| DAVI | 13 | 0 | 3 | 3 | 16 |
| OMAR AZIZ | 8 | 0 | 0 | 0 | 8 |

> **Observação de dado:** PEC como autor principal é 0 para DAVI, ROMÁRIO, OMAR AZIZ
> e WELLINGTON — coerente com o perfil de coautores prolíficos ou ex-presidentes do
> Senado. OTTO ALENCAR tem 1 PEC aprovada como autor principal.
> O mesmo padrão se repete nas aprovações: PEC aprovada principal = 0 para a maioria.
> Isso é esperado e correto, não um erro de coleta.

### Atualizações no front-end

**`src/lib/legislativo.ts`**
- Campo `data?` adicionado à interface `Exemplo`
- Campo `normaGerada?` adicionado à interface `Exemplo`
- Campos `pec_total`, `pec_autor_principal`, `pl_total`, `pl_autor_principal`,
  `pec_aprovadas`, `pec_aprovadas_autor_principal`, `pl_aprovadas`,
  `pl_aprovadas_autor_principal`, `emendas_mpv_total`, `emendas_mpv_autor_unico`
  adicionados a `LegislativoData`
- Arrays `pec_lista`, `pl_lista`, `emendas_mpv_lista`, `aprovadas_lista` adicionados

**`src/components/PainelAtuacao.tsx`**
- Seção "Autoria legislativa": dois cards (PEC, PL) exibidos para senadores
- Seção "Viraram lei": dois cards (PEC aprovadas, PL aprovadas) com link para
  `/aprovadas` quando `aprovadas_lista.length > 0` — exclusivo de senadores
- Gráfico "Autoria por tipo": barras agrupadas horizontais (total vs autor principal)
  para PEC e PL — exclusivo de senadores
- Gráfico "Por tipo de proposição" (câmara): restrito a deputados federais

**`src/components/ListaProposicoesAprovadas.tsx`** (novo)
- Componente client reutilizado de deputados e senadores
- Exibe `normaGerada` como linha extra em verde por item
  (ex.: `→ Lei nº 14.740 de 29/11/2023`)

**`src/app/[cargo]/[estado]/[numero]/aprovadas/page.tsx`**
- Descrição da página dinâmica por cargo:
  - Deputado: `"56ª Legislatura (2019–2023)"`
  - Senador: `"55ª e 56ª Legislaturas (2015–2023)"`

---

## Dificuldades técnicas e erros encontrados

### 1. Dados completamente inválidos na ingestão original

**Problema:** a versão inicial de `ingestao_legislativa.py` usava
`GET /dadosabertos/processo?autoria={nome}&tipoDocumento={tipo}` para buscar
proposições de senadores. Os dados resultantes no `legislativo.json` eram:

- `total_apresentadas` = 42.664 por senador (todos têm exatamente o mesmo valor)
- `por_tipo` = `{"PL": 10666, "PLP": 10666, "PEC": 10666, "PDL": 10666}` (divisão exata por 4)
- Exemplos com proposições de 1949 ("PDS 16/1984") e mensagens do executivo de 1991

O endpoint retornava **todas** as proposições do tipo — o parâmetro `autoria` era
silenciosamente ignorado, exatamente como o parâmetro `codSituacao` é ignorado
pela API da Câmara (documentado em `Atuacao_Parlamentar.MD`).

**Resolução:** substituir por `GET /senador/{codigo}/autorias`, que retorna
exclusivamente as proposições do parlamentar identificado pelo código.

---

### 2. Endpoint `/processo/emenda` retornando 503 e timeout

**Problema:** a primeira tentativa de coletar emendas a MPV usou:
```
GET /dadosabertos/processo/emenda?codigoParlamentarAutor={codigo}&dataInicio=1990-01-01
```

Isso resultava em timeout (60s) ou HTTP 503 para todos os senadores testados.
A causa: `dataInicio=1990-01-01` faz o servidor processar toda a carreira
parlamentar do candidato, incluindo o período como deputado federal — gerando
payloads de 1–2 MB com mais de 1.000 emendas, o que sobrecarregava o servidor.

**Resolução em duas etapas:**
1. Buscar a data de início do mandato de senador via `GET /senador/{codigo}/mandatos`
   e usar essa data como `dataInicio` (em vez de 1990).
2. Resultado: respostas de ~200 registros, consistentemente rápidas (~2–3s).

---

### 3. Emendas a MPV misturadas com emendas a outros tipos

**Problema:** o endpoint `/processo/emenda` não tem parâmetro de filtro por tipo
de processo — retorna emendas a PL, PLC, PLP, PEC, orçamentárias e MPV juntas,
sem distinção.

**Resolução:** filtrar client-side com regex `\bMPV\b` no campo `identificacao`.
Exemplos de identificações que casam: `"EMENDA 72 - MPV 685/2015"`,
`"EME MPV 1.090/2021"`. O padrão é suficientemente específico para não gerar
falsos positivos nos dados observados.

---

### 4. Nomenclatura PLS vs PL (pré e pós-2019)

**Problema:** até 2019, projetos de lei originados no Senado eram identificados
como **PLS** (Projeto de Lei do Senado). A partir da Resolução do Senado nº 1/2019,
passaram a ser chamados simplesmente **PL** — a mesma sigla usada na Câmara dos
Deputados. O endpoint `/autorias` retorna ambas as siglas dependendo do período.

**Resolução:**
- Script filtra por `siglas_alvo = {"PLS", "PL"}` e normaliza PLS → PL no campo
  `sigla` do JSON de saída (para exibição unificada no front-end).
- Metric `pl_total` soma os dois conjuntos.

---

### 5. Etapa de verificação de autor principal eliminada

**Problema planejado (não ocorreu):** o plano original previa chamar
`GET /processo/{id}` para cada proposição a fim de verificar `autoriaIniciativa[].ordem == 1`.
Isso geraria centenas de chamadas extras (uma por proposição por senador).

**Descoberta:** o endpoint `/senador/{codigo}/autorias` já retorna o campo
`IndicadorAutorPrincipal` (Sim/Não) diretamente em cada item do XML —
eliminando completamente a necessidade de chamadas de detalhe.

**Impacto:** de ~500+ chamadas planejadas para os 5 senadores, o script faz
apenas **3 chamadas por senador** (mandatos + autorias + emendas) = 15 no total.

---

### 6. Determinação de autor único nas emendas MPV

**Problema:** o endpoint de emendas não expõe `IndicadorAutorPrincipal` como o
de autorias. O campo disponível é `autoria` (string de texto livre).

**Resolução:** verificar ausência de `;` no campo `autoria`. Emendas coletivas
têm autores separados por ponto e vírgula. Se não há `;`, o senador é o único
proponente. Validado nos dados: todos os 263 registros de emendas coletados têm
`autor_unico = true`, o que é coerente — emendas individuais a MPV são a norma
no Senado.

---

### 7. Métricas de emendas MPV removidas do front-end

**Problema de confiabilidade identificado após implementação:**
Os dados de emendas a MPV foram coletados e validados tecnicamente, mas apresentam
limitações estruturais que comprometem a confiabilidade da exibição ao usuário:

- **Filtro por regex é frágil:** a identificação de emendas a MPV depende da
  presença da string `MPV` no campo `identificacao`. Não há garantia de que o
  formato seja uniforme para todo o histórico — emendas antigas ou de sistemas
  legados podem usar grafias diferentes (`MP`, `Med. Prov.`, etc.).
- **`autor_unico` via heurística:** a ausência de `;` no campo `autoria` é um
  proxy impreciso. Comissões mistas, lideranças e bancadas podem apresentar formatos
  distintos que a heurística não captura corretamente.
- **100% de `autor_unico = true` é suspeito:** o fato de todos os 263 registros
  retornarem `autor_unico = true` pode indicar que o campo `autoria` não segue o
  padrão esperado para emendas coletivas, e não que todas as emendas sejam de fato
  individuais.
- **Volume desproporcional:** Wellington Fagundes com 145 emendas a MPV vs. Omar
  Aziz com 8 levanta dúvidas sobre consistência de cobertura entre mandatos e
  legislaturas.

**Decisão:** os campos `emendas_mpv_total`, `emendas_mpv_autor_unico` e
`emendas_mpv_lista` foram mantidos no `legislativo.json` (coletados e auditáveis),
mas **removidos do `PainelAtuacao.tsx`** — não são exibidos ao usuário final.

O princípio do projeto ("Dados oficiais — nunca inventar, estimar ou completar")
exige que só exibamos o que pode ser verificado de forma confiável. PEC e PL têm
`IndicadorAutorPrincipal` diretamente na API; emendas MPV dependem de inferência.

---

### 8. `siglaSituacao` ignorado em combinação com `codigoParlamentarAutor`

**Problema:** a tentativa de filtrar diretamente as proposições aprovadas via:
```
GET /processo?codigoParlamentarAutor={codigo}&sigla=PEC&siglaSituacao=TNJR
```
retorna resposta vazia para todos os senadores testados, mesmo quando existem
proposições com situação TNJR (Transformada em Norma Jurídica).

O parâmetro `siglaSituacao` é silenciosamente descartado quando combinado com
`codigoParlamentarAutor` — comportamento análogo ao `codSituacao` ignorado pela
API da Câmara e ao `autoria` ignorado pelo endpoint `/processo` do Senado.

**Resolução:** buscar a lista completa sem `siglaSituacao` e filtrar client-side
pelo campo `normaGerada` (preenchido = aprovado), conforme validado com caso real:
`PL 4815/2019` tinha `normaGerada: "Lei nº 14.531 de 10/01/2023"` mas
`situacaoAtual: "REMETIDA À CÂMARA DOS DEPUTADOS"` — `situacaoAtual` também não
é confiável para determinar aprovação.

---

### 9. API do Senado retorna duplicatas no endpoint `/processo`

**Problema:** o endpoint `/processo?codigoParlamentarAutor=...` retorna entradas
duplicadas para algumas proposições — a mesma PEC ou PL aparece duas ou mais vezes
na resposta, inflando os contadores de aprovações.

Exemplos detectados na primeira execução (sem deduplicação):
- DAVI: 2 duplicatas (`PEC 66/2023`, `PL 4731/2019`)
- OMAR AZIZ: 1 duplicata (`PEC 32/2022`)
- OTTO ALENCAR: 1 duplicata (`PEC 32/2022`)
- WELLINGTON FAGUNDES: 5 duplicatas
- ROMÁRIO: 1 duplicata

**Resolução:** deduplicação client-side em `filtrar_aprovados()` por chave
`(numero, ano)` — suficiente porque o filtro já opera sobre um único valor de
`sigla` por chamada.

---

### 10. Encoding Windows-1252 no endpoint `/processo`

**Problema:** o campo `normaGerada` do endpoint `/processo` contém o caractere
`º` (sinal ordinal, U+00BA) em strings como `"Lei nº 14.531 de 10/01/2023"`.
O servidor envia os bytes como Windows-1252 (`\xba`), mas o header HTTP declara
`UTF-8`. A biblioteca `requests` usa o charset declarado com `errors='replace'`,
convertendo `\xba` em `�` (replacement character — exibido como `?`).

O problema não afetou os endpoints anteriores (`/autorias`, `/emenda`) porque
esses campos não contêm o caractere `º`.

**Resolução:** função `_decode_json_senado()` que decodifica os bytes raw da
resposta (`resp.content`):
1. Tenta `utf-8` com `errors='strict'` — levanta `UnicodeDecodeError` se `\xba` solto.
2. Fallback: decodifica como `windows-1252`, que lê `\xba` corretamente como `º`.

Cache corrompido (da primeira execução) foi invalidado removendo os arquivos
`senado_processo_*.json` antes de re-executar.

---

## O que a API do Senado NÃO permite

| Feature desejada | Endpoint tentado | Resultado | Motivo |
|---|---|---|---|
| Proposições filtradas por autor | `/processo?autoria={nome}&tipoDocumento={tipo}` | Filtro ignorado | `autoria` é silenciosamente descartado |
| Aprovações filtradas diretamente | `/processo?codigoParlamentarAutor=...&siglaSituacao=TNJR` | Retorna vazio | `siglaSituacao` combinado com `codigoParlamentarAutor` é ignorado (bug da API) |
| Emendas MPV filtradas por tipo | `/processo/emenda?sigla=MPV` | Parâmetro inexistente | Endpoint não aceita filtro por tipo |
| CPF do senador | `/senador/{codigo}` (XML) | Ausente | API pública não expõe CPF de senadores |
| Situação atual das proposições | `/autorias` | Ausente | Endpoint não inclui `statusProposicao` |
| Votações nominais do senador | Sem endpoint conhecido | — | Não exposto na API pública atual |

---

## Limitações conhecidas

| Limitação | Impacto | Caminho de resolução |
|---|---|---|
| Apenas 5 senadores com match | 5 dos ~10 senadores candidatos em 2022 têm dados | Matching manual para os sem correspondência na API |
| `por_ano` não separa PEC de PL | Gráfico temporal agrega os dois tipos | Calcular séries separadas se necessário |
| Emendas MPV coletadas mas não exibidas | Métricas no JSON para auditoria; removidas do front-end por confiabilidade insuficiente | Reavaliação futura se a API expuser campo estruturado |
| `autor_unico` via heurística | Inferido pela ausência de `;` no campo `autoria` — impreciso para comissões e lideranças | Nenhum campo estruturado disponível na API |
| Aprovações: cobertura limitada ao mandato atual | `dataInicio` exclui PLs aprovados de mandatos anteriores | Ampliar range ou usar `/processo` sem filtro de data (risco de timeout) |

---

## Como executar

```powershell
# No PowerShell (Windows) — forçar UTF-8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8      = "1"

cd data/scripts
.\.venv\Scripts\Activate.ps1

# Coleta e atualiza legislativo.json para os senadores
python ingestao_senadores.py
# -> atualiza public/legislativo/legislativo.json (5 registros de senadores)
# -> cache em data/.cache/legislativo/senado_mandatos_{id}.xml
#              data/.cache/legislativo/senado_autorias_{id}.xml
#              data/.cache/legislativo/senado_processo_{id}_PEC_{data}.json
#              data/.cache/legislativo/senado_processo_{id}_PL_{data}.json
#              data/.cache/legislativo/senado_emendas_{id}_{data}.json
```

Com cache preenchido (segunda execução): < 5 segundos.
Com cache vazio (primeira execução): ~60–90 segundos (5 chamadas por senador × 5 senadores).

> **Atenção ao re-executar:** se houver suspeita de encoding corrompido nos caches
> de `/processo`, remover os arquivos `senado_processo_*.json` antes de rodar:
> ```powershell
> Remove-Item data/.cache/legislativo/senado_processo_*.json
> ```

---

## Arquivos criados/modificados

```
data/scripts/ingestao_senadores.py                    modificado — etapas 3 e 4 (aprovações)
public/legislativo/legislativo.json                   atualizado — 5 registros com aprovações
src/lib/legislativo.ts                                modificado — normaGerada, pec/pl_aprovadas
src/components/PainelAtuacao.tsx                      modificado — seção "Viraram lei" p/ senadores
src/components/ListaProposicoesAprovadas.tsx          novo — lista reutilizada p/ deputados e senadores
src/app/[cargo]/[estado]/[numero]/aprovadas/page.tsx  modificado — descrição dinâmica por cargo
```

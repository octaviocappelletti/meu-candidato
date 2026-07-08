# Atuação Parlamentar — Documentação da Feature

Exibe histórico de projetos de lei para candidatos que exerceram mandato federal
(deputado federal ou senador) na 56ª/55ª Legislatura.

---

## O que foi construído

### Script de ingestão (`data/scripts/ingestao_legislativa.py`)

Pipeline Python que:

1. Lê `data/output/candidatos.json` (gerado por `ingesta_tse.py`) e filtra apenas
   candidatos à **reeleição federal** — deputados federais com ocupação "DEPUTADO"
   e senadores com ocupação "SENADOR" no cadastro do TSE.
2. Faz o **matching** entre o candidato TSE e o parlamentar nas APIs oficiais:
   - Câmara: `GET /api/v2/deputados?idLegislatura=56` (todos de uma vez)
   - Senado: `GET /dadosabertos/senador/lista/legislatura/{55,56}` (ambas as legislaturas)
3. Para cada parlamentar casado, coleta proposições de sua autoria (PL, PLP, PEC, PDL)
   via `GET /proposicoes?idDeputadoAutor={id}&siglaTipo={tipo}`.
4. Exporta `public/legislativo/legislativo.json` — um dicionário keyed por
   `nr_sequencial` (= `sq_candidato` do TSE) com os agregados de cada parlamentar.

**Resultado:** 333 registros (325 matches por CPF, 5 por data de nascimento+UF,
3 por nome com confiança >= 0.70, 3 para revisão manual, 100 sem correspondência).

### Estratégia de matching (evolução)

A estratégia original usava apenas similaridade de nomes (`SequenceMatcher` +
`palavras_contidas`), o que gerava ambiguidades quando dois parlamentares
compartilham sobrenome. A estratégia foi evoluída para chaves exatas:

#### Deputados Federais — matching por CPF

- `carregar_reeleicao()` lê o campo `NR_CPF_CANDIDATO` do CSV do TSE e
  normaliza para 11 dígitos com `zfill(11)`.
- `buscar_indice_cpf_camara(session, todos_deps)` percorre todos os ~513
  deputados e chama `GET /api/v2/deputados/{id}` individualmente para obter
  o CPF de cada um (único endpoint que expõe esse campo). Cada resposta é
  cacheada em `data/.cache/legislativo/camara_dep_detalhe_{id}.json`.
  Retorna um dicionário `{cpf_11_digitos: deputado}`.
- `match_deputado()` tenta primeiro o índice CPF; se encontrado, retorna
  confiança 1.0 e método `"cpf"`. Se não, cai no matching por nome (limiar 0.70).

#### Senadores — matching por data de nascimento + UF

- A API pública do Senado (`/senador/{codigo}`) não expõe CPF.
- `buscar_indice_nasc_senado(senadores)` chama `GET /dadosabertos/senador/{codigo}`
  (XML) para cada senador, extrai `DataNascimento` e monta a chave
  `(uf_normalizada, data_iso)`. Cada resposta é cacheada em
  `data/.cache/legislativo/senado_dep_detalhe_{codigo}.json`.
- `match_senador()` tenta primeiro o índice nascimento+UF; se encontrado,
  retorna confiança 1.0 e método `"nascimento"`. Se não, cai no matching por nome.

### JSON por parlamentar (`public/legislativo/legislativo.json`)

Campos gravados por registro:

| Campo | Tipo | Descrição |
|---|---|---|
| `sq_candidato` | string | nr_sequencial do TSE (chave do dicionário) |
| `casa` | `"camara"` \| `"senado"` | Casa legislativa |
| `id_parlamentar` | number | ID na API da Câmara ou código no Senado |
| `confianca_match` | float | 1.0 para CPF/nascimento; 0.70–1.0 para nome |
| `total_apresentadas` | int | Total de PL+PLP+PEC+PDL de autoria |
| `total_aprovadas` | int | Campo reservado — não confiável (ver limitações) |
| `por_tipo` | object | Contagem por sigla: `{"PL": 35, "PLP": 4, ...}` |
| `por_ano` | object | Série temporal: `{"2019": 8, "2020": 12, ...}` |
| `exemplos` | array | Até 5 proposições com sigla, número, ano, ementa e URL |
| `data_referencia` | string | Data ISO da coleta (`YYYY-MM-DD`) |

### Componente React (`src/components/PainelAtuacao.tsx`)

Substitui o componente original `AtuacaoParlamentar.tsx` (removido). Exibe:

- **KPIs**: total apresentadas + breakdown por tipo em cards.
- **Série temporal**: gráfico de barras (recharts) com proposições por ano.
- **Distribuição por tipo**: gráfico de barras horizontal (recharts) com PL/PLP/PEC/PDL.
- **Exemplos**: lista com link para a ficha de tramitação na Câmara.
- **Data dinâmica**: "Atualizado em DD/MM/AAAA" lida do campo `data_referencia`.
- **Nota de legislatura diferenciada**: Câmara (56ª) vs Senado (55ª/56ª).
- **Sem dados**: exibe mensagem explicativa em vez de renderizar seção vazia.

Comportamento: busca `/legislativo/legislativo.json` uma vez por sessão (promise
cacheada em escopo de módulo via `src/lib/legislativo.ts`), faz lookup pelo
`nrSequencial` do candidato. Retorna null para cargos não aplicáveis.

### Badge compacto na lista (`src/components/ResumoAtuacao.tsx`)

Aparece no rodapé do `CardCandidato` para deputados federais e senadores com dados
disponíveis. Exibe o total de proposições, o intervalo de anos e um link
"Ver atuação ↗" que leva ao detalhe do candidato com âncora `#atuacao`.

Para evitar `<a>` aninhado (o card já tem um `<Link>`), o `CardCandidato` foi
reestruturado: o `<Link>` principal envolve só o topo do card; o `ResumoAtuacao`
fica em uma faixa separada abaixo, fora do link principal.

### Lib compartilhada (`src/lib/legislativo.ts`)

Centraliza os tipos TypeScript (`LegislativoData`, `Exemplo`) e a função
`fetchLegislativo()` — singleton que garante que ambos os componentes
(`PainelAtuacao` e `ResumoAtuacao`) compartilhem a mesma promise e não façam
duas requisições ao mesmo JSON.

### Integração na página de detalhe (`src/app/[cargo]/[estado]/[numero]/page.tsx`)

Seção condicional para `deputado-federal` e `senador`, entre "Transparência
financeira" e "Proposta de governo". Usa `PainelAtuacao` (antes usava
`AtuacaoParlamentar`).

### `src/types/index.ts` e `src/lib/supabase.ts`

Adicionado o campo `nrSequencial: string` à interface `Candidato` (antes só existia
em `CandidatoDetalhado`). Necessário para o `ResumoAtuacao` no card da lista.
`rowToCandidato()` passou a mapear `row.nr_sequencial`.

---

## Dificuldades encontradas e resoluções

### 1. API da Câmara retornando 504 Gateway Timeout

**Problema:** a estratégia inicial fazia 27 chamadas separadas à API
(`/deputados?siglaUf={UF}` por estado), cada uma suscetível a timeout independente.
Com o servidor da Câmara instável, a maioria das chamadas falhava.

**Resolução:** substituir as 27 chamadas por **uma única sequência paginada** sem
filtro de UF (`/deputados?idLegislatura=56`), baixando todos os ~513 deputados em
~6 páginas. O filtro por UF passou a ser feito em memória. Adicionado também
retry com backoff exponencial (1s → 4s → 16s) para erros 5xx.

---

### 2. Matching falho para nomes de urna curtos

**Problema:** o TSE usa nomes de urna abreviados ("DAVI", "KATIA", "ACIR GURGACZ")
enquanto as APIs da Câmara e do Senado armazenam o nome civil completo
("Davi Alcolumbre", "Kátia Abreu", "Acir Marcos Gurgacz"). O `SequenceMatcher`
puro penaliza essa assimetria e devolvia scores baixíssimos (0.28–0.50).

**Resolução:** criada a função `palavras_contidas(curto, longo)` que verifica se
**todas as palavras** do nome de urna aparecem no nome completo. Se positivo,
o score é elevado para no mínimo 0.85 (nomes com 2+ palavras) ou 0.78 (nome de
uma palavra só). Após a correção, candidatos como Rose de Freitas, Alvaro Dias e
Acir Gurgacz passaram de `sem_match` para `ok`.

---

### 3. Zero deputados federais identificados como reeleição

**Problema:** o filtro usava `isin({"DEPUTADO FEDERAL", "DEPUTADO DISTRITAL"})`,
mas o TSE registra a ocupação simplesmente como `"DEPUTADO"` (sem especificar
federal ou distrital) para parlamentares em exercício.

**Resolução:** substituído por `str.contains(r"\bDEPUTADO\b", regex=True)`,
que captura o termo independentemente de sufixo. Adicionado diagnóstico automático
que imprime as top-5 ocupações por cargo ao iniciar o script.

---

### 4. Senadores da 55ª legislatura não encontrados

**Problema:** senadores eleitos em 2014 (mandato 2015–2023) são candidatos à
reeleição em 2022 mas não aparecem no endpoint
`/senador/lista/legislatura/56` (que lista apenas os eleitos em 2018).
Exemplos afetados: Rose de Freitas (ES), Roberto Rocha (MA), Alvaro Dias (PR),
Acir Gurgacz (RO).

**Resolução:** passar a consultar **ambas as legislaturas** (55 e 56) e fazer merge
deduplicado pelo código do parlamentar. Resultado: de 4 matches a 9 matches entre
senadores.

---

### 5. `codSituacao` completamente ignorado pela API da Câmara

**Problema:** ao implementar o "funil de situação" (apresentadas → em tramitação →
arquivadas → viraram lei), descobriu-se experimentalmente que o parâmetro
`codSituacao` é **silenciosamente ignorado** pela API quando combinado com
`idDeputadoAutor`. Qualquer valor de `codSituacao` (923 = arquivada, 1140 = norma,
ou qualquer outro) retorna o mesmo conjunto completo de proposições do deputado,
como se o filtro não existisse. Isso foi confirmado para um deputado com 351
proposições totais: `codSituacao=923`, `codSituacao=1140` e sem filtro retornaram
todos os mesmos 351 registros.

Consequência: o funil foi gerado com dados incorretos — `arquivadas > total_apresentadas`
porque `arquivadas` contava todas as proposições (de todos os tipos) enquanto
`total_apresentadas` contava só PL/PLP/PEC/PDL.

**Resolução:** remover o funil completamente da pipeline e do front-end.
O painel exibe apenas dados deriváveis da lista de proposições já coletada
(total, por tipo, por ano), que são 100% confiáveis.

---

### 6. `/deputados/{id}/votacoes` retorna 405 Method Not Allowed

**Problema:** o endpoint esperado para buscar os votos de um deputado
(`GET /api/v2/deputados/{id}/votacoes`) retorna **405**. Testado tanto via
WebFetch quanto via `urllib` diretamente. O mesmo ocorre para
`/deputados/{id}/votos`. O endpoint simplesmente não existe na versão atual
da API v2 da Câmara.

A alternativa — iterar todas as votações plenárias e verificar o voto de cada
deputado — exigiria milhares de chamadas e não é viável para a arquitetura estática
do projeto.

**Resolução:** remover a coleta de votações da pipeline. A feature foi desenhada
mas não pode ser implementada com a API pública v2 atual.

---

### 7. Campo `total_aprovadas` sempre igual a `total_apresentadas`

**Problema:** a Câmara API ignora o parâmetro `codSituacao=1140` quando combinado
com `idDeputadoAutor`, retornando todos os projetos independente da situação.
O campo "aprovados" ficou igual ao total, o que seria enganoso ao usuário.

**Resolução:** removida a KPI "Aprovados" do componente front-end. O campo
`total_aprovadas` permanece no JSON para uso futuro.

---

### 8. Arquivo `depara.csv` bloqueado ao re-executar o script

**Problema:** o CSV de de-para ficava aberto no Excel após inspeção, causando
`PermissionError` na escrita seguinte.

**Resolução:** fechar o arquivo antes de reexecutar. Sem alteração no código.

---

### 9. Matching ambíguo por nome causava falsos positivos

**Problema:** ao baixar o limiar de `THRESHOLD_MATCH` de 0.70 para 0.65 (tentativa
de aumentar a cobertura), o script casou WALDECK CARNEIRO com "Laura Carneiro" —
dois parlamentares distintos que compartilham apenas o sobrenome. O score 0.68
ultrapassava o novo limiar.

**Resolução:** reverter o limiar para 0.70. A solução correta para aumentar cobertura
é o matching por chave exata (CPF/nascimento), não relaxar a similaridade de nome.

---

### 10. API da Câmara não expõe CPF no endpoint de listagem

**Problema:** `GET /api/v2/deputados` retorna ~30 campos mas não inclui o CPF.
O CPF só está disponível em `GET /api/v2/deputados/{id}` (endpoint de detalhe),
exigindo uma chamada por parlamentar.

**Resolução:** `buscar_indice_cpf_camara()` percorre os ~513 deputados fazendo uma
chamada individual para cada um, com cache em disco. Na primeira execução soma
~513 requisições extras (~5 min); nas seguintes, todas são servidas do cache
em segundos.

---

### 11. API do Senado não expõe CPF em nenhum endpoint público

**Problema:** `GET /dadosabertos/senador/{codigo}` retorna XML com dados biográficos
mas sem CPF. O endpoint `/senador/{id}/cpf` retorna 404.

**Resolução:** usar **data de nascimento + UF** como chave surrogate. O universo de
senadores é pequeno (~160 ativos), tornando colisão extremamente improvável.
`buscar_indice_nasc_senado()` extrai `DataNascimento` do XML e monta o índice
`{(uf, data_iso): senador}`.

---

### 12. `UnicodeEncodeError` no terminal Windows (cp1252)

**Problema:** mensagens de log com o caractere `→` (U+2192) causavam
`UnicodeEncodeError: 'charmap' codec can't encode character` no terminal Windows,
que usa cp1252 por padrão. O script abortava depois de salvar o `depara.csv`
mas antes de coletar as proposições — deixando o JSON desatualizado.

**Resolução em duas etapas:**
1. Substituir `→` por `->` em todos os `print()` do script.
2. Forçar UTF-8 no terminal antes de executar o Python no PowerShell:
   ```powershell
   $env:PYTHONIOENCODING = "utf-8"
   $env:PYTHONUTF8 = "1"
   python ingestao_legislativa.py
   ```

---

### 13. Contador de resumo exibindo `ok=0` após nova estratégia de matching

**Problema:** os novos status `cpf_ok` e `nasc_ok` não eram contabilizados na
variável `ok` do resumo final, que ficava em 0 mesmo com 330 matches bem-sucedidos.

**Resolução:** separar a contagem por status:
```python
cpf_ok    = (df_depara["status"] == "cpf_ok").sum()
nasc_ok   = (df_depara["status"] == "nasc_ok").sum()
ok        = (df_depara["status"] == "ok").sum()
total_ok  = cpf_ok + nasc_ok + ok
print(f"  matched={total_ok} (cpf_ok={cpf_ok}, nasc_ok={nasc_ok}, nome_ok={ok})")
```

---

## O que a API da Câmara v2 NÃO permite

Documentado aqui para evitar retrabalho em iterações futuras.

| Feature desejada | Endpoint tentado | Resultado | Motivo |
|---|---|---|---|
| Funil de situação | `/proposicoes?codSituacao={cod}&idDeputadoAutor={id}` | Dados incorretos | `codSituacao` é ignorado quando combinado com `idDeputadoAutor` |
| Votações nominais por deputado | `/deputados/{id}/votacoes` | 405 | Endpoint não existe na v2 |
| Votações nominais por deputado | `/deputados/{id}/votos` | 405 | Endpoint não existe na v2 |
| Presença em sessões plenárias | Sem endpoint conhecido | — | Dado não exposto via API v2 pública |
| Temas das proposições | `/proposicoes?idDeputadoAutor={id}` | Campo ausente | `codTema` não retorna na listagem; requer detalhe por proposição (custoso) |

---

## Limitações conhecidas

| Limitação | Impacto | Caminho de resolução |
|---|---|---|
| Dados de 2022, não de 2026 | Todos os números referem-se à 56ª legislatura | Reexecutar o script com dados da 57ª legislatura em 2026 |
| ~100 candidatos sem correspondência | Não exibe a seção para esses candidatos | Revisão manual do `depara.csv`; muitos são nomes de urna de uma palavra (TUM, MAX, ALBA) |
| Inclui coautorias | Total de projetos pode estar inflado | Filtragem por autoria principal disponível na API mas requer chamadas adicionais |
| `total_aprovadas` não confiável | Campo no JSON mas não exibido no front-end | Verificar status individualmente via `GET /proposicoes/{id}` (custoso) |
| Alan Rick e outros por eleição suplementar | Não aparecem nas listas de legislatura da API do Senado | Adicionar manualmente ao de-para |
| ~513 chamadas extras à API da Câmara | Primeira execução lenta (~5 min só para índice de CPF) | Cache em disco mitiga execuções subsequentes |

---

## Como executar

```powershell
# No PowerShell (Windows) — forçar UTF-8 para evitar UnicodeEncodeError
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8      = "1"

cd data/scripts

# Passo 1: verificar matching sem coletar proposições
python ingestao_legislativa.py --dry-run
# -> gera data/output/legislativo/depara.csv para revisão

# Passo 2: ingestão completa (~15 min na primeira execução, ~2 min depois)
python ingestao_legislativa.py
# -> gera public/legislativo/legislativo.json (333 registros)
```

```bash
# No bash/macOS/Linux
cd data/scripts
python ingestao_legislativa.py --dry-run
python ingestao_legislativa.py
```

O cache de respostas brutas da API fica em `data/.cache/legislativo/` (não versionado).
Excluir essa pasta força o re-download completo.

---

## Arquivos de análise gerados

| Arquivo | Descrição |
|---|---|
| `data/output/candidatos_reeleicao.csv` | Todos os 1.046 candidatos à reeleição em 2022 (todos os cargos), filtrados como aptos |
| `data/output/reeleicao_dep_federal_legislativo.csv` | 415 deputados federais candidatos à reeleição cruzados com histórico legislativo |
| `data/output/reeleicao_senador_legislativo.csv` | 10 senadores candidatos à reeleição cruzados com histórico legislativo |
| `data/output/legislativo/depara.csv` | Tabela de matching candidato TSE ↔ parlamentar API (auditoria) |

---

## Arquivos criados/modificados

```
data/scripts/ingestao_legislativa.py              modificado — matching CPF/nascimento + por_ano
public/legislativo/legislativo.json               gerado — JSON público para o front-end (333 registros)
data/output/legislativo/depara.csv                gerado — tabela de matching (não versionado)
src/lib/legislativo.ts                            novo — tipos compartilhados + fetch singleton
src/components/PainelAtuacao.tsx                  novo — painel completo (recharts)
src/components/ResumoAtuacao.tsx                  novo — badge compacto no card da lista
src/components/AtuacaoParlamentar.tsx             removido — substituído pelo PainelAtuacao
src/components/CardCandidato.tsx                  modificado — inclui ResumoAtuacao
src/app/[cargo]/[estado]/[numero]/page.tsx        modificado — usa PainelAtuacao
src/types/index.ts                                modificado — nrSequencial adicionado a Candidato
src/lib/supabase.ts                               modificado — rowToCandidato mapeia nrSequencial
```

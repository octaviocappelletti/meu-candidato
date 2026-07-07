# Atuação Parlamentar — Documentação da Feature

Protótipo com dados de 2022. Exibe histórico de projetos de lei para candidatos
que exerceram mandato federal (deputado federal ou senador) na 56ª/55ª Legislatura.

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

**Resultado:** 330 registros (313 matches confiantes, 17 para revisão manual,
103 sem correspondência).

### Componente React (`src/components/AtuacaoParlamentar.tsx`)

- Renderizado apenas para `cargo = "deputado-federal"` ou `"senador"`.
- Busca `/legislativo/legislativo.json` uma única vez por sessão (promise cacheada
  em escopo de módulo) e faz lookup pelo `nrSequencial` do candidato.
- Exibe: total de projetos apresentados, breakdown por tipo (PL/PLP/PEC/PDL),
  lista de exemplos com link para a Câmara/Senado, e link para o perfil completo.
- Retorna `null` silenciosamente se não há dados (candidato sem mandato anterior
  ou sem correspondência no matching).

### Integração na página de detalhe (`src/app/[cargo]/[estado]/[numero]/page.tsx`)

Seção adicionada condicionalmente (só renderiza para os dois cargos aplicáveis)
entre "Transparência financeira" e "Proposta de governo".

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

### 5. Campo `total_aprovadas` sempre igual a `total_apresentadas`

**Problema:** a Câmara API ignora o parâmetro `codSituacao=1140` quando combinado
com `idDeputadoAutor`, retornando todos os projetos independente da situação.
O campo "aprovados" ficou igual ao total, o que seria enganoso ao usuário.

**Resolução:** removida a KPI "Aprovados" do componente front-end. O display mostra
apenas o total de projetos apresentados e o breakdown por tipo (PL/PLP/PEC/PDL),
que são dados confiáveis. O campo permanece no JSON para uso futuro quando a API
for corrigida ou substituída.

---

### 6. Arquivo `depara.csv` bloqueado ao re-executar o script

**Problema:** o CSV de de-para ficava aberto no Excel após inspeção, causando
`PermissionError` na escrita seguinte.

**Resolução:** fechar o arquivo antes de reexecutar. Sem alteração no código.

---

## Limitações conhecidas (protótipo)

| Limitação | Impacto | Caminho de resolução |
|---|---|---|
| Dados de 2022, não de 2026 | Todos os números referem-se à 56ª legislatura | Reexecutar o script com dados da 57ª legislatura em 2026 |
| 103 candidatos sem correspondência | Não exibe a seção para esses candidatos | Revisão manual do `depara.csv` + matches manuais |
| Inclui coautorias | Total de projetos pode estar inflado | Filtragem por autoria principal disponível na API mas requer chamadas adicionais |
| `codSituacao=1140` ignorado pela API | Não é possível contar aprovações pela API de listagem | Verificar status individualmente via `GET /proposicoes/{id}` (custoso) |
| Alan Rick e outros por eleição suplementar | Não aparecem nas listas de legislatura da API do Senado | Adicionar manualmente ao de-para |

---

## Como executar

```bash
cd data/scripts

# Passo 1: verificar matching sem coletar proposições
python ingestao_legislativa.py --dry-run
# → gera data/output/legislativo/depara.csv para revisão

# Passo 2: ingestão completa (~12 min na primeira execução, instantânea depois)
python ingestao_legislativa.py
# → gera public/legislativo/legislativo.json (330 registros no protótipo)
```

O cache de respostas brutas da API fica em `data/.cache/legislativo/` (não versionado).
Excluir essa pasta força o re-download completo.

---

## Arquivos criados/modificados

```
data/scripts/ingestao_legislativa.py         novo — pipeline de ingestão
data/output/legislativo/depara.csv           gerado — tabela de matching (não versionado)
data/output/legislativo/legislativo.json     gerado — JSON de saída (não versionado)
public/legislativo/legislativo.json          gerado — cópia pública para o front-end
src/components/AtuacaoParlamentar.tsx        novo — componente React
src/app/[cargo]/[estado]/[numero]/page.tsx   modificado — seção adicionada
```

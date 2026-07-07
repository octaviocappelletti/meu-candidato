# Feature & Fix Log — Sessão de Desenvolvimento

Registro das implementações, problemas encontrados e estratégias adotadas.

---

## 1. Propostas de Governo

### O que foi implementado

Ingestão dos PDFs de propostas de governo do TSE e exibição na página do candidato.

**Arquivos criados/modificados:**
- `data/scripts/ingestao_propostas.py` — script de pipeline
- `data/scripts/schema.sql` — nova tabela `propostas_governo`
- `data/scripts/requirements.txt` — adicionado `pypdf>=4.0`
- `src/types/index.ts` — tipo `PropostaGoverno`
- `src/lib/supabase.ts` — função `buscarPropostaGoverno`
- `src/components/PropostaGoverno.tsx` — componente de exibição
- `src/app/[cargo]/[estado]/[numero]/page.tsx` — seção de proposta adicionada

### Fonte dos dados

URL padrão do CDN do TSE:
```
https://cdn.tse.jus.br/estatistica/sead/odsele/proposta_governo/proposta_governo_{ano}_{uf}.zip
```
Cada ZIP contém PDFs nomeados com o `SQ_CANDIDATO` do candidato (ex: `2022AC10001616169.pdf`).

### Decisões de design

- PDFs armazenados no **Supabase Storage** (bucket `propostas-governo`, público).
- Texto extraído com `pypdf` e salvo na tabela `propostas_governo` para buscas futuras.
- UI simplificada: botão "Ver Proposta de Governo (PDF)" que abre o arquivo em nova aba.

### Problemas e soluções

#### Problema 1 — Matching falhou para estados grandes (SP, MG, RJ, GO, PE, RS)
**Causa:** O script pré-carregava todos os candidatos de uma UF com uma única query. O Supabase retorna no máximo 1000 linhas por padrão. Em estados com milhares de candidatos (deputados estaduais, federais etc.), os governadores ficavam além do milésimo registro.

**Solução:** Inverteu-se a lógica. Agora os `nr_sequencial` são extraídos dos nomes dos arquivos PDF primeiro, e só então é feita uma query direcionada com `.in_("nr_sequencial", [...])` — sem risco de paginação, pois há no máximo ~20 PDFs por UF.

#### Problema 2 — Erro de null bytes no Postgres (UF Amapá/AP)
**Causa:** Alguns PDFs continham caracteres `\x00` (null bytes) que o Postgres rejeita com o código de erro `22P05`.

**Solução:** Adicionada limpeza explícita no texto extraído:
```python
return texto_limpo.replace("\x00", "")
```

#### Problema 3 — URL do `.in_()` muito longa para estados grandes
**Causa:** Com muitos `nr_sequencial` no filtro `.in_()`, a URL gerada pelo PostgREST estoura o limite do servidor (erro 400 "JSON could not be generated").

**Solução:** A função `buscar_candidatos_por_sequenciais` foi refatorada para dividir os sequenciais em chunks de 200 e fazer múltiplas queries menores:
```python
CHUNK = 200
for i in range(0, len(sequenciais), CHUNK):
    chunk = sequenciais[i : i + CHUNK]
    resp = client.table("candidatos").select(...).in_("nr_sequencial", chunk).execute()
```

---

## 2. Paginação no Front-end (Lista de Candidatos)

### Problema
Nem todos os candidatos apareciam na listagem. Em SP, por exemplo, apenas 1000 deputados estaduais eram exibidos de ~1500+ existentes no banco.

**Causa:** A função `buscarCandidatos` em `src/lib/supabase.ts` não especificava `.range()`, e o Supabase/PostgREST limita respostas a 1000 linhas por padrão.

### Solução

Implementada paginação automática com loop até esgotar os resultados:
```typescript
const PAGE_SIZE = 1000;
while (true) {
  const { data, error } = await query.range(from, from + PAGE_SIZE - 1);
  todos.push(...data);
  if (data.length < PAGE_SIZE) break;
  from += PAGE_SIZE;
}
```

**Arquivo:** `src/lib/supabase.ts` — função `buscarCandidatos`

---

## 3. Redes Sociais

### O que foi implementado

Ingestão das URLs de redes sociais do TSE e exibição com ícones SVG na página do candidato.

**Arquivos criados/modificados:**
- `data/scripts/ingestao_redes_sociais.py` — script de pipeline
- `src/components/RedesSociais.tsx` — ícones SVG reais para cada rede

### Fonte dos dados

URL padrão do CDN do TSE:
```
https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_{ano}_{uf}.zip
```
CSV com colunas: `SQ_CANDIDATO`, `NR_ORDEM`, `DS_URL`.

### Problemas e soluções

#### Problema 1 — CSV não tem coluna de tipo de rede social
**Causa:** Esperávamos uma coluna `NM_TIPO_REDE_SOCIAL`, mas o CSV do TSE 2022 contém apenas `DS_URL` com a URL completa.

**Solução:** Detecção da rede pelo domínio da URL:
```python
def detectar_rede(url: str) -> str | None:
    u = url.lower()
    if "facebook.com" in u or "fb.com" in u: return "url_facebook"
    if "instagram.com" in u:                  return "url_instagram"
    if "twitter.com" in u or "x.com" in u:   return "url_twitter"
    if "youtube.com" in u or "youtu.be" in u: return "url_youtube"
    if "@" in u and not u.startswith("http"): return "email_campanha"
    return None
```

#### Problema 2 — Upsert falhou com violação de NOT NULL
**Causa:** O `upsert` com `on_conflict="id"` no Supabase Python aciona o caminho do INSERT antes de detectar o conflito. O INSERT falhava porque `nome_urna`, `cargo` e outros campos `NOT NULL` não estavam no payload.

**Solução:** A função `buscar_candidatos_por_sequenciais` passou a buscar também os campos obrigatórios (`nome_urna`, `nome_completo`, `numero_eleitoral`, `cargo`, `uf`, `partido`, `situacao`), que são incluídos no payload do upsert. O `ON CONFLICT (id) DO UPDATE` atualiza apenas as colunas de redes sociais; os outros campos são re-enviados com os mesmos valores já existentes.

#### Problema 3 — Limite de 1000 linhas e URL longa no `.in_()`
**Causa:** Estados como SP têm ~1789 candidatos com redes sociais. A query `.in_("nr_sequencial", sequenciais)` com 1789 valores gerava uma URL enorme (erro 400) e, mesmo quando passava, retornava no máximo 1000 resultados.

**Solução:** Mesma estratégia do script de propostas — chunks de 200 na função `buscar_candidatos_por_sequenciais`.

---

## Padrão de Limite do Supabase

> **Regra geral:** toda query ao Supabase sem `.limit()` explícito retorna no máximo **1000 linhas**. Toda query `.in_()` com mais de ~300 valores gera URLs longas que podem resultar em erro **400**.

**Estratégias adotadas neste projeto:**
| Cenário | Estratégia |
|---|---|
| Listagem de candidatos no front-end | Loop com `.range(from, from + 999)` até retorno incompleto |
| Busca por `nr_sequencial` nos scripts | Chunks de 200 com múltiplas queries |

---

## Pré-requisitos para Rodar os Scripts

```bash
# Ativar o ambiente virtual
data\scripts\.venv\Scripts\Activate.ps1

# Instalar dependências (inclui pypdf)
pip install -r data/scripts/requirements.txt
```

**Variáveis de ambiente necessárias em `.env.local`:**
```
NEXT_PUBLIC_SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

**Tabelas que devem existir no Supabase antes de rodar:**
- `candidatos` — populada via `ingesta_tse.py`
- `bens_candidatos` — populada via `ingesta_tse.py`
- `propostas_governo` — criada via `schema.sql` (bloco de propostas)

**Bucket que deve existir no Supabase Storage:**
- `propostas-governo` (público) — para os PDFs das propostas

## Ordem de execução dos scripts

```bash
# 1. Candidatos e bens
python data/scripts/ingesta_tse.py

# 2. Propostas de governo
python data/scripts/ingestao_propostas.py --ano 2022

# 3. Redes sociais
python data/scripts/ingestao_redes_sociais.py --ano 2022
```

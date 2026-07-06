-- =============================================================================
-- Meu Candidato — Schema Supabase
-- Execute no SQL Editor: app.supabase.com → SQL Editor → New query
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Tabela principal: candidatos
-- ---------------------------------------------------------------------------
create table public.candidatos (
  id                  uuid      primary key default gen_random_uuid(),

  -- Identificação
  nome_urna           text      not null,
  nome_completo       text      not null,
  numero_eleitoral    integer   not null,
  nr_sequencial       text      not null default '',  -- chave TSE para URL da foto

  -- Cargo e localidade
  cargo               text      not null,   -- slug: presidente | governador | senador | deputado-federal | deputado-estadual
  uf                  text      not null,   -- sigla UF (ex: SP) ou BR para presidente

  -- Partido e coligação
  partido             text      not null,
  coligacao           text      not null default '',

  -- Situação
  situacao            text      not null,   -- valor bruto do TSE
  situacao_apta       boolean   not null default false,

  -- Fotos
  url_foto            text      not null default '',
  url_foto_vice       text      not null default '',

  -- Vice (só para presidente e governador)
  nome_vice           text,
  nr_sequencial_vice  text,

  -- Dados pessoais
  data_nascimento     date,
  grau_instrucao      text      not null default '',
  ocupacao            text      not null default '',

  -- Contato e redes sociais
  email_campanha      text      not null default '',
  url_facebook        text      not null default '',
  url_instagram       text      not null default '',
  url_twitter         text      not null default '',
  url_youtube         text      not null default '',

  -- Bens (total calculado durante ingestão)
  total_bens          numeric   not null default 0,

  -- Unicidade: cargo + UF + número eleitoral identifica um candidato
  unique (cargo, uf, numero_eleitoral)
);

-- Índices para as queries do app
create index on public.candidatos (cargo, uf, situacao_apta);
create index on public.candidatos (situacao_apta);

-- ---------------------------------------------------------------------------
-- Tabela auxiliar: bens declarados por candidato
-- ---------------------------------------------------------------------------
create table public.bens_candidatos (
  id               uuid     primary key default gen_random_uuid(),
  numero_eleitoral integer  not null,
  cargo            text     not null,
  uf               text     not null,
  ordem            integer  not null,
  descricao        text     not null,
  valor            numeric  not null default 0,

  -- Mantém referência lógica sem FK rígida (facilita carga em lote)
  unique (cargo, uf, numero_eleitoral, ordem)
);

create index on public.bens_candidatos (numero_eleitoral, cargo, uf);

-- ---------------------------------------------------------------------------
-- Row Level Security: catálogo é somente leitura público
-- ---------------------------------------------------------------------------
alter table public.candidatos      enable row level security;
alter table public.bens_candidatos enable row level security;

create policy "leitura_publica" on public.candidatos
  for select using (true);

create policy "leitura_publica" on public.bens_candidatos
  for select using (true);

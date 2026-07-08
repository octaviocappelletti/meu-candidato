import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { BemCandidato, Candidato, CandidatoDetalhado, CargoSlug, PropostaGoverno, UF } from '@/types';

let _client: SupabaseClient | null = null;

function getClient(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) {
      throw new Error(
        'Supabase não configurado: defina NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_ANON_KEY no .env.local'
      );
    }
    _client = createClient(url, key);
  }
  return _client;
}

// Constrói a URL pública da foto direto do nr_sequencial, sem depender do valor armazenado em url_foto.
function buildFotoUrl(nrSequencial: string | null | undefined): string {
  if (!nrSequencial) return '';
  const base = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? '').replace(/\/+$/, '');
  return `${base}/storage/v1/object/public/fotos-candidatos/${nrSequencial}.jpeg`;
}

// ── Tipos internos (linhas brutas do banco, snake_case) ──────────────────────

interface CandidatoRow {
  nome_urna: string;
  nome_completo: string;
  numero_eleitoral: number;
  cargo: string;
  uf: string;
  partido: string;
  coligacao: string;
  situacao: string;
  nr_sequencial: string;
  nr_sequencial_vice: string | null;
  nome_vice: string | null;
  genero: string;
  cor_raca: string;
  grau_instrucao: string;
  ocupacao: string;
  data_nascimento: string;
}

interface CandidatoDetalhadoRow extends CandidatoRow {
  email_campanha: string;
  url_facebook: string;
  url_instagram: string;
  url_twitter: string;
  url_youtube: string;
  total_bens: number;
}

interface BemRow {
  ordem: number;
  descricao: string;
  valor: number;
}

// ── Mapeamentos snake_case → camelCase ───────────────────────────────────────

function rowToCandidato(row: CandidatoRow): Candidato {
  return {
    nomeUrna: row.nome_urna,
    nomeCompleto: row.nome_completo,
    numeroEleitoral: row.numero_eleitoral,
    nrSequencial: row.nr_sequencial ?? '',
    cargo: row.cargo as CargoSlug,
    uf: row.uf as UF | 'BR',
    partido: row.partido,
    coligacao: row.coligacao ?? '',
    situacao: row.situacao,
    urlFoto: buildFotoUrl(row.nr_sequencial),
    genero: row.genero ?? '',
    corRaca: row.cor_raca ?? '',
    grauInstrucao: row.grau_instrucao ?? '',
    ocupacao: row.ocupacao ?? '',
    dataNascimento: row.data_nascimento ?? '',
    nomeVice: row.nome_vice ?? undefined,
    urlFotoVice: buildFotoUrl(row.nr_sequencial_vice) || undefined,
  };
}

function rowToCandidatoDetalhado(
  row: CandidatoDetalhadoRow,
  bens: BemRow[]
): CandidatoDetalhado {
  return {
    ...rowToCandidato(row),
    nrSequencial: row.nr_sequencial ?? '',
    emailCampanha: row.email_campanha ?? '',
    urlFacebook: row.url_facebook ?? '',
    urlInstagram: row.url_instagram ?? '',
    urlTwitter: row.url_twitter ?? '',
    urlYoutube: row.url_youtube ?? '',
    totalBens: row.total_bens ?? 0,
    bens: bens.map((b) => ({
      ordem: b.ordem,
      descricao: b.descricao,
      valor: b.valor,
    })),
  };
}

// ── Queries públicas ─────────────────────────────────────────────────────────

const PAGE_SIZE = 1000;

export async function buscarCandidatos(
  cargo: string,
  uf?: string
): Promise<Candidato[]> {
  const client = getClient();
  const todos: CandidatoRow[] = [];
  let from = 0;

  while (true) {
    let query = client
      .from('candidatos')
      .select(
        'nome_urna, nome_completo, numero_eleitoral, cargo, uf, partido, coligacao, situacao, nr_sequencial, nr_sequencial_vice, nome_vice, genero, cor_raca, grau_instrucao, ocupacao, data_nascimento'
      )
      .eq('cargo', cargo)
      .eq('situacao_apta', true)
      .order('nome_urna', { ascending: true });

    if (uf) {
      query = query.eq('uf', uf.toUpperCase());
    }

    const { data, error } = await query.range(from, from + PAGE_SIZE - 1);
    if (error) throw error;

    todos.push(...((data as CandidatoRow[]) ?? []));
    if ((data?.length ?? 0) < PAGE_SIZE) break;
    from += PAGE_SIZE;
  }

  return todos.map(rowToCandidato);
}

export async function buscarCandidatoDetalhado(
  cargo: string,
  uf: string,
  numeroEleitoral: number
): Promise<CandidatoDetalhado | null> {
  const client = getClient();

  const { data: candidatoData, error: candidatoError } = await client
    .from('candidatos')
    .select(
      'nome_urna, nome_completo, numero_eleitoral, cargo, uf, partido, coligacao, situacao, nr_sequencial, nr_sequencial_vice, nome_vice, genero, cor_raca, grau_instrucao, ocupacao, data_nascimento, email_campanha, url_facebook, url_instagram, url_twitter, url_youtube, total_bens'
    )
    .eq('cargo', cargo)
    .eq('uf', uf.toUpperCase())
    .eq('numero_eleitoral', numeroEleitoral)
    .single();

  if (candidatoError) {
    if (candidatoError.code === 'PGRST116') return null;
    throw candidatoError;
  }

  const { data: bensData, error: bensError } = await client
    .from('bens_candidatos')
    .select('ordem, descricao, valor')
    .eq('numero_eleitoral', numeroEleitoral)
    .eq('cargo', cargo)
    .eq('uf', uf.toUpperCase())
    .order('ordem', { ascending: true });

  if (bensError) throw bensError;

  return rowToCandidatoDetalhado(
    candidatoData as CandidatoDetalhadoRow,
    (bensData as BemRow[]) ?? []
  );
}

export async function buscarPropostaGoverno(
  cargo: string,
  uf: string,
  numeroEleitoral: number
): Promise<PropostaGoverno | null> {
  const client = getClient();

  const { data, error } = await client
    .from('propostas_governo')
    .select('texto, url_pdf')
    .eq('cargo', cargo)
    .eq('uf', uf.toUpperCase())
    .eq('numero_eleitoral', numeroEleitoral)
    .single();

  if (error) {
    if (error.code === 'PGRST116') return null;
    throw error;
  }

  return {
    texto: (data as { texto: string; url_pdf: string }).texto ?? '',
    urlPdf: (data as { texto: string; url_pdf: string }).url_pdf ?? '',
  };
}

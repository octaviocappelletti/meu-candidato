import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { Candidato } from '@/types';

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

// O Supabase retorna snake_case (conforme as colunas do banco); mapeamos para a interface camelCase.
function mapRow(row: Record<string, unknown>): Candidato {
  return {
    nomeUrna:        String(row.nome_urna ?? ''),
    nomeCompleto:    String(row.nome_completo ?? ''),
    numeroEleitoral: Number(row.numero_eleitoral),
    cargo:           row.cargo as Candidato['cargo'],
    subcargo:        row.subcargo as string | null | undefined,
    uf:              row.uf as Candidato['uf'],
    partido:         String(row.partido ?? ''),
    situacao:        String(row.situacao ?? ''),
    urlFoto:         String(row.url_foto ?? ''),
  };
}

export async function diagnosticar(cargo: string, uf?: string) {
  const client = getClient();
  const q = client.from('candidatos').select('cargo, uf, situacao_apta, situacao', { count: 'exact' }).limit(5);
  if (uf) q.eq('uf', uf.toUpperCase());
  const { data, count, error } = await q;
  return { data, count, error: error?.message };
}

export async function buscarCandidatos(
  cargo: string,
  uf?: string
): Promise<Candidato[]> {
  const client = getClient();

  let query = client
    .from('candidatos')
    .select('*')
    .eq('cargo', cargo)
    .in('situacao', ['APTO', 'DEFERIDO', 'DEFERIDO COM RECURSO'])
    .order('nome_urna', { ascending: true });

  if (uf) {
    query = query.eq('uf', uf.toUpperCase());
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []).map(mapRow);
}

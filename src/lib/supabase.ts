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

export async function buscarCandidatos(
  cargo: string,
  uf?: string
): Promise<Candidato[]> {
  const client = getClient();

  let query = client
    .from('candidatos')
    .select('*')
    .eq('cargo', cargo)
    .eq('situacao_apta', true)
    .order('nome_urna', { ascending: true });

  if (uf) {
    query = query.eq('uf', uf.toUpperCase());
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Candidato[];
}

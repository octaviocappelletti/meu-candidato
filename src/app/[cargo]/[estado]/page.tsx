import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getCargo } from '@/lib/cargos';
import { buscarCandidatos, diagnosticar } from '@/lib/supabase';
import { ESTADOS } from '@/lib/estados';
import { Candidato } from '@/types';
import DescricaoCargo from '@/components/DescricaoCargo';
import ListaCandidatos from '@/components/ListaCandidatos';

interface Props {
  params: Promise<{ cargo: string; estado: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { cargo, estado } = await params;
  const infoCargo = getCargo(cargo);
  if (!infoCargo) return {};
  const uf = estado.toUpperCase();
  const estadoNome = ESTADOS.find((e) => e.uf === uf)?.nome ?? uf;
  const titulo = infoCargo.federal
    ? infoCargo.nome
    : `${infoCargo.nome} — ${estadoNome}`;
  return {
    title: `${titulo} · Meu Candidato`,
  };
}

export default async function PaginaCandidatos({ params }: Props) {
  const { cargo, estado } = await params;
  const infoCargo = getCargo(cargo);

  if (!infoCargo) notFound();

  const uf = estado === 'br' ? undefined : estado.toUpperCase();
  const estadoNome = uf ? ESTADOS.find((e) => e.uf === uf)?.nome ?? uf : null;

  let candidatos: Candidato[] = [];
  let erroSupabase: string | null = null;
  const debug = await diagnosticar(cargo, uf);
  try {
    candidatos = await buscarCandidatos(cargo, uf);
  } catch (err) {
    erroSupabase = err instanceof Error ? err.message : String(err);
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <nav className="mb-4">
          <Link
            href={infoCargo.federal ? '/' : `/${cargo}`}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Voltar
          </Link>
        </nav>

        <header className="mb-4">
          <h1 className="text-xl font-bold text-gray-900">{infoCargo.nome}</h1>
          {estadoNome && (
            <p className="text-sm text-gray-500 mt-0.5">{estadoNome}</p>
          )}
        </header>

        <DescricaoCargo cargo={infoCargo} />
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs font-mono break-all space-y-1">
          <p><strong>DEBUG</strong> — cargo: {cargo} | uf: {uf ?? 'br'} | total linhas (sem filtro): {debug.count ?? '?'}</p>
          {debug.error && <p className="text-red-600">Erro: {debug.error}</p>}
          {debug.data && <p>Amostra: {JSON.stringify(debug.data)}</p>}
        </div>
        {erroSupabase && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 font-mono break-all">
            Erro busca: {erroSupabase}
          </div>
        )}
        <ListaCandidatos candidatos={candidatos} />
      </div>
    </main>
  );
}

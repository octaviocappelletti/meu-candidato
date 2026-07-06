import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getCargo } from '@/lib/cargos';
import { buscarCandidatos } from '@/lib/supabase';
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
  try {
    candidatos = await buscarCandidatos(cargo, uf);
  } catch {
    // Supabase ainda não configurado — exibe lista vazia
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
        <ListaCandidatos candidatos={candidatos} />
      </div>
    </main>
  );
}

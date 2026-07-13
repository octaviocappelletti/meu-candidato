import { notFound } from 'next/navigation';
import Link from 'next/link';
import { buscarCandidatoDetalhado } from '@/lib/supabase';
import { getCargo } from '@/lib/cargos';
import DetalhesDespesas from '@/components/DetalhesDespesas';

interface Props {
  params: Promise<{ cargo: string; estado: string; numero: string }>;
  searchParams: Promise<{ ano?: string; mes?: string; tipo?: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { numero } = await params;
  return { title: `Despesas parlamentares · Nº ${numero} · Meu Candidato` };
}

export default async function PaginaDespesas({ params, searchParams }: Props) {
  const { cargo, estado, numero } = await params;
  const { ano, mes, tipo } = await searchParams;

  const infoCargo = getCargo(cargo);
  if (!infoCargo || !['deputado-federal', 'senador'].includes(cargo)) notFound();

  if (!ano || !mes || !tipo) notFound();

  const candidato = await buscarCandidatoDetalhado(
    cargo,
    estado === 'br' ? 'br' : estado,
    Number(numero),
  ).catch(() => null);

  if (!candidato) notFound();

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <nav className="mb-6">
          <Link
            href={`/${cargo}/${estado}/${numero}`}
            className="text-sm text-blue-600 hover:underline"
          >
            ← {candidato.nomeUrna}
          </Link>
        </nav>

        <DetalhesDespesas
          nrSequencial={candidato.nrSequencial}
          nomeUrna={candidato.nomeUrna}
          ano={ano}
          mes={mes}
          tipo={tipo}
        />

        <p className="mt-6 text-center text-xs text-gray-400">
          Dados oficiais da Câmara dos Deputados · CEAP
        </p>
      </div>
    </main>
  );
}

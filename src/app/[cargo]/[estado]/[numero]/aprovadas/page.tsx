import { notFound } from 'next/navigation';
import Link from 'next/link';
import { buscarCandidatoDetalhado } from '@/lib/supabase';
import { getCargo } from '@/lib/cargos';
import ListaProposicoesAprovadas from '@/components/ListaProposicoesAprovadas';

interface Props {
  params: Promise<{ cargo: string; estado: string; numero: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { numero, cargo } = await params;
  const infoCargo = getCargo(cargo);
  if (!infoCargo) return {};
  return {
    title: `Proposições aprovadas · Nº ${numero} · Meu Candidato`,
  };
}

export default async function PaginaAprovadas({ params }: Props) {
  const { cargo, estado, numero } = await params;

  const infoCargo = getCargo(cargo);
  if (!infoCargo) notFound();

  if (!['deputado-federal', 'senador'].includes(cargo)) notFound();

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

        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <h1 className="text-base font-semibold text-gray-900 mb-1">
            Proposições que viraram lei
          </h1>
          <p className="text-xs text-gray-500 mb-5 leading-relaxed">
            Projetos de autoria de{' '}
            <span className="font-medium text-gray-700">{candidato.nomeUrna}</span>{' '}
            transformados em Norma Jurídica (Lei, Emenda Constitucional ou Decreto
            Legislativo) —{' '}
            {cargo === 'senador'
              ? '55ª e 56ª Legislaturas (2015–2023).'
              : '56ª Legislatura (2019–2023).'}
          </p>

          <ListaProposicoesAprovadas nrSequencial={candidato.nrSequencial} />
        </section>

        <p className="mt-6 text-center text-xs text-gray-400">
          Dados oficiais do TSE · Eleições 2026
        </p>
      </div>
    </main>
  );
}

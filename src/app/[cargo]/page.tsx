import { notFound, redirect } from 'next/navigation';
import Link from 'next/link';
import { getCargo, isFederal } from '@/lib/cargos';
import { ESTADOS } from '@/lib/estados';

interface Props {
  params: Promise<{ cargo: string }>;
}

export default async function PaginaEscolhaEstado({ params }: Props) {
  const { cargo } = await params;
  const infoCargo = getCargo(cargo);

  if (!infoCargo) notFound();

  if (isFederal(cargo)) {
    redirect(`/${cargo}/br`);
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto">
        <nav className="mb-6">
          <Link href="/" className="text-sm text-blue-600 hover:underline">
            ← Voltar
          </Link>
        </nav>

        <header className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">{infoCargo.nome}</h1>
          <p className="mt-1 text-gray-600">Escolha o estado para ver os candidatos.</p>
        </header>

        <ul className="grid grid-cols-2 sm:grid-cols-3 gap-3" aria-label="Estados">
          {ESTADOS.map((estado) => (
            <li key={estado.uf}>
              <Link
                href={`/${cargo}/${estado.uf.toLowerCase()}`}
                className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white px-4 py-4 shadow-sm hover:border-blue-400 hover:shadow-md transition-all"
              >
                <span className="text-xl font-bold text-gray-900">{estado.uf}</span>
                <span className="text-xs text-gray-500 mt-0.5 text-center">
                  {estado.nome}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}

import Link from 'next/link';
import { CARGOS } from '@/lib/cargos';

export default function PaginaCargos() {
  const cargos = Object.values(CARGOS).filter(
    (c) => c.slug !== 'vice-presidente' && c.slug !== 'vice-governador'
  );

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
      <div className="max-w-lg w-full">
        <header className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900">Meu Candidato</h1>
          <p className="mt-2 text-gray-600">
            Consulte informações oficiais sobre os candidatos às eleições de 2026.
          </p>
        </header>

        <nav aria-label="Escolha o cargo">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Escolha o cargo
          </h2>
          <ul className="space-y-3">
            {cargos.map((cargo) => (
              <li key={cargo.slug}>
                <Link
                  href={`/${cargo.slug}`}
                  className="flex items-center justify-between w-full rounded-xl border border-gray-200 bg-white px-6 py-4 shadow-sm hover:border-blue-400 hover:shadow-md transition-all"
                >
                  <span className="text-base font-medium text-gray-900">
                    {cargo.nome}
                  </span>
                  {cargo.federal && (
                    <span className="text-xs text-blue-600 font-medium bg-blue-50 px-2 py-0.5 rounded-full">
                      Nacional
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <footer className="mt-10 text-center text-xs text-gray-400">
          Dados oficiais do TSE · Eleições 2026
        </footer>
      </div>
    </main>
  );
}

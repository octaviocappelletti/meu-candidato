import { PropostaGoverno as PropostaGovernoTipo } from '@/types';

interface Props {
  proposta: PropostaGovernoTipo;
}

export default function PropostaGoverno({ proposta }: Props) {
  if (!proposta.urlPdf) return null;

  return (
    <section aria-labelledby="proposta-titulo">
      <h2
        id="proposta-titulo"
        className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3"
      >
        Proposta de Governo
      </h2>
      <a
        href={proposta.urlPdf}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-white text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors text-sm"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5"
          aria-hidden="true"
        >
          <path d="M5.625 1.5c-1.036 0-1.875.84-1.875 1.875v17.25c0 1.035.84 1.875 1.875 1.875h12.75c1.035 0 1.875-.84 1.875-1.875V12.75A3.75 3.75 0 0016.5 9h-1.875a1.875 1.875 0 01-1.875-1.875V5.25A3.75 3.75 0 009 1.5H5.625z" />
          <path d="M12.971 1.816A5.23 5.23 0 0114.25 5.25v1.875c0 .207.168.375.375.375H16.5a5.23 5.23 0 013.434 1.279 9.768 9.768 0 00-6.963-6.963z" />
        </svg>
        Ver Proposta de Governo (PDF)
      </a>
    </section>
  );
}

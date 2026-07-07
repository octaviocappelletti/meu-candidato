'use client';

interface Props {
  valor: string;
  onChange: (valor: string) => void;
  numFiltrosAtivos?: number;
  onAbrirFiltros?: () => void;
}

export default function BarraDeBusca({ valor, onChange, numFiltrosAtivos = 0, onAbrirFiltros }: Props) {
  return (
    <div className="flex gap-2 mb-4">
      <div className="relative flex-1">
        <div
          className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"
          aria-hidden="true"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5 text-gray-400"
          >
            <path
              fillRule="evenodd"
              d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <input
          type="search"
          value={valor}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Buscar por nome ou número..."
          aria-label="Buscar candidatos por nome ou número eleitoral"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent text-gray-900 placeholder-gray-400"
        />
      </div>

      {onAbrirFiltros && (
        <button
          type="button"
          onClick={onAbrirFiltros}
          aria-label={`Filtros${numFiltrosAtivos > 0 ? ` (${numFiltrosAtivos} ativos)` : ''}`}
          className="relative flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-gray-200 bg-white shadow-sm text-sm text-gray-700 hover:border-blue-400 transition-colors flex-shrink-0"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-4 h-4"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.973.206 7.372.601a.75.75 0 01.628.74v2.288a2.25 2.25 0 01-.659 1.59l-4.682 4.683a2.25 2.25 0 00-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 018 18.25v-5.757a2.25 2.25 0 00-.659-1.591L2.659 6.22A2.25 2.25 0 012 4.629V2.34a.75.75 0 01.628-.74z"
              clipRule="evenodd"
            />
          </svg>
          <span>Filtros</span>
          {numFiltrosAtivos > 0 && (
            <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-medium leading-none">
              {numFiltrosAtivos}
            </span>
          )}
        </button>
      )}
    </div>
  );
}

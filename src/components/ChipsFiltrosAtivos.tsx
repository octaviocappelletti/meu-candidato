'use client';

import { EstadoFiltros, FAIXAS_ETARIAS, FILTROS_VAZIOS } from '@/lib/filtros';

function cap(s: string) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

interface Chip {
  label: string;
  onRemover: () => void;
}

interface Props {
  filtros: EstadoFiltros;
  totalFiltrado: number;
  totalGeral: number;
  labelColigacao: string;
  onChange: (filtros: EstadoFiltros) => void;
}

export default function ChipsFiltrosAtivos({
  filtros, totalFiltrado, totalGeral, labelColigacao, onChange,
}: Props) {
  const chips: Chip[] = [];

  filtros.partidos.forEach((p) =>
    chips.push({ label: p, onRemover: () => onChange({ ...filtros, partidos: filtros.partidos.filter((x) => x !== p) }) })
  );
  filtros.coligacoes.forEach((c) =>
    chips.push({ label: `${labelColigacao}: ${c}`, onRemover: () => onChange({ ...filtros, coligacoes: filtros.coligacoes.filter((x) => x !== c) }) })
  );
  filtros.generos.forEach((g) =>
    chips.push({ label: cap(g), onRemover: () => onChange({ ...filtros, generos: filtros.generos.filter((x) => x !== g) }) })
  );
  filtros.coresRaca.forEach((r) =>
    chips.push({ label: cap(r), onRemover: () => onChange({ ...filtros, coresRaca: filtros.coresRaca.filter((x) => x !== r) }) })
  );
  filtros.faixasEtarias.forEach((f) =>
    chips.push({
      label: FAIXAS_ETARIAS.find((x) => x.valor === f)?.label ?? f,
      onRemover: () => onChange({ ...filtros, faixasEtarias: filtros.faixasEtarias.filter((x) => x !== f) }),
    })
  );
  filtros.escolaridades.forEach((e) =>
    chips.push({ label: cap(e), onRemover: () => onChange({ ...filtros, escolaridades: filtros.escolaridades.filter((x) => x !== e) }) })
  );
  filtros.ocupacoes.forEach((o) =>
    chips.push({ label: cap(o), onRemover: () => onChange({ ...filtros, ocupacoes: filtros.ocupacoes.filter((x) => x !== o) }) })
  );
  if (filtros.apenasFavoritos)
    chips.push({ label: 'Apenas favoritos', onRemover: () => onChange({ ...filtros, apenasFavoritos: false }) });
  if (filtros.apenasReeleicao)
    chips.push({ label: 'Reeleição', onRemover: () => onChange({ ...filtros, apenasReeleicao: false }) });

  const filtrado = totalFiltrado < totalGeral;

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-500">
          <span className="font-semibold text-gray-800">{totalFiltrado}</span>{' '}
          {totalFiltrado === 1 ? 'candidato' : 'candidatos'}
          {filtrado && <span className="text-gray-400"> de {totalGeral}</span>}
        </p>
        {chips.length > 0 && (
          <button
            onClick={() => onChange({ ...FILTROS_VAZIOS, busca: filtros.busca })}
            className="text-xs text-blue-600 hover:underline"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5" role="list" aria-label="Filtros ativos">
          {chips.map((chip, i) => (
            <span
              key={i}
              role="listitem"
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs border border-blue-200"
            >
              {chip.label}
              <button
                onClick={chip.onRemover}
                aria-label={`Remover filtro: ${chip.label}`}
                className="hover:text-blue-900 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

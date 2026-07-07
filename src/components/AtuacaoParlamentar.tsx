'use client';

import { useState, useEffect } from 'react';

interface Exemplo {
  sigla: string;
  numero: number | string | null;
  ano: number | string | null;
  ementa: string;
  url: string;
}

interface LegislativoData {
  sq_candidato: string;
  casa: 'camara' | 'senado';
  id_parlamentar: number | string;
  confianca_match: number;
  total_apresentadas: number;
  total_aprovadas: number;
  por_tipo: Record<string, number>;
  exemplos: Exemplo[];
  data_referencia: string;
}

const CARGOS_APLICAVEIS = ['deputado-federal', 'senador'];

let _fetch: Promise<Record<string, LegislativoData> | null> | null = null;
function fetchLegislativo() {
  if (!_fetch) {
    _fetch = fetch('/legislativo/legislativo.json')
      .then((r) => (r.ok ? (r.json() as Promise<Record<string, LegislativoData>>) : null))
      .catch(() => null);
  }
  return _fetch;
}

interface Props {
  nrSequencial: string;
  cargo: string;
}

export default function AtuacaoParlamentar({ nrSequencial, cargo }: Props) {
  const [dados, setDados] = useState<LegislativoData | null | undefined>(undefined);

  useEffect(() => {
    if (!CARGOS_APLICAVEIS.includes(cargo) || !nrSequencial) {
      setDados(null);
      return;
    }
    fetchLegislativo().then((mapa) => {
      setDados(mapa ? (mapa[nrSequencial] ?? null) : null);
    });
  }, [nrSequencial, cargo]);

  if (!CARGOS_APLICAVEIS.includes(cargo) || dados === null) return null;

  if (dados === undefined) {
    return <p className="py-4 text-sm text-gray-400 text-center">Carregando dados parlamentares…</p>;
  }

  const casa = dados.casa === 'camara' ? 'Câmara dos Deputados' : 'Senado Federal';
  const urlPortal =
    dados.casa === 'camara'
      ? `https://www.camara.leg.br/deputados/${dados.id_parlamentar}`
      : `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${dados.id_parlamentar}`;

  const tipoEntries = Object.entries(dados.por_tipo).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      {/* Cabeçalho */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-gray-900">Atuação parlamentar</h2>
        <span className="text-xs font-medium text-amber-600">Dados de 2022 (protótipo)</span>
      </div>

      {/* Nota metodológica */}
      <p className="text-xs text-gray-500 mb-4 leading-relaxed bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
        Projetos da 56ª Legislatura (2019–2023). Inclui coautorias.
        O volume de projetos não é indicador de qualidade legislativa.
      </p>

      {/* KPI principal + breakdown por tipo */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="bg-gray-50 rounded-xl px-5 py-3 text-center border border-gray-200">
          <p className="text-xs text-gray-500 mb-0.5">Projetos apresentados</p>
          <p className="text-2xl font-bold text-gray-900">{dados.total_apresentadas.toLocaleString('pt-BR')}</p>
        </div>
        {tipoEntries.map(([tipo, qtd]) => (
          <div key={tipo} className="bg-gray-50 rounded-xl px-4 py-3 text-center border border-gray-200">
            <p className="text-xs text-gray-500 mb-0.5">{tipo}</p>
            <p className="text-lg font-bold text-gray-900">{qtd}</p>
          </div>
        ))}
      </div>

      {/* Exemplos */}
      {dados.exemplos.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-gray-600 mb-2">Exemplos de projetos</p>
          <ul className="space-y-2">
            {dados.exemplos.map((ex, i) => (
              <li key={i} className="text-xs text-gray-700 leading-snug">
                <span className="font-semibold text-gray-400 mr-1">
                  {ex.sigla} {ex.numero}/{ex.ano} ·
                </span>
                {ex.url ? (
                  <a
                    href={ex.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-600 hover:underline"
                  >
                    {ex.ementa}
                  </a>
                ) : (
                  ex.ementa
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <a
        href={urlPortal}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-blue-600 hover:underline"
      >
        Ver perfil completo na {casa} ↗
      </a>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';

interface OrigemItem {
  valor: number;
  pct: number;
}

interface FinanceiroData {
  sq_candidato: string;
  total_arrecadado: number;
  total_gasto: number;
  num_doadores: number;
  origem_recursos: {
    publico: OrigemItem;
    proprio: OrigemItem;
    pessoa_fisica: OrigemItem;
    outros: OrigemItem;
  };
  pct_autofinanciamento: number;
  despesas_por_categoria: { categoria: string; valor: number }[];
  data_referencia: string;
}

function brl(n: number) {
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

interface Props {
  nrSequencial: string;
  uf: string;
}

export default function TransparenciaFinanceira({ nrSequencial, uf }: Props) {
  const [dados, setDados] = useState<FinanceiroData | null | undefined>(undefined);

  useEffect(() => {
    if (!nrSequencial) { setDados(null); return; }
    fetch(`/financeiro/${uf.toLowerCase()}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<Record<string, FinanceiroData>>) : null))
      .then((mapa) => setDados(mapa ? (mapa[nrSequencial] ?? null) : null))
      .catch(() => setDados(null));
  }, [nrSequencial, uf]);

  if (dados === undefined) {
    return <p className="py-4 text-sm text-gray-400 text-center">Carregando dados financeiros…</p>;
  }

  if (!dados) {
    return (
      <p className="py-4 text-sm text-gray-400 text-center">
        Sem prestação de contas disponível para este candidato.
      </p>
    );
  }

  const origens = [
    { label: 'Fundo público',    cor: 'bg-blue-500',   ...dados.origem_recursos.publico },
    { label: 'Recursos próprios', cor: 'bg-emerald-500', ...dados.origem_recursos.proprio },
    { label: 'Pessoas físicas',  cor: 'bg-amber-400',   ...dados.origem_recursos.pessoa_fisica },
    { label: 'Outros',           cor: 'bg-gray-300',    ...dados.origem_recursos.outros },
  ].filter((o) => o.valor > 0);

  const topDespesas = dados.despesas_por_categoria.slice(0, 8);
  const maxDesp = topDespesas[0]?.valor ?? 1;

  const dataRef = dados.data_referencia
    ? new Date(dados.data_referencia + 'T12:00:00').toLocaleDateString('pt-BR')
    : null;

  return (
    <div>
      {/* Cabeçalho */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-900">Transparência financeira</h2>
        <div className="text-right">
          {dataRef && <p className="text-xs text-gray-400">Ref.: {dataRef}</p>}
          <p className="text-xs font-medium text-amber-600">Dados de 2022 (protótipo)</p>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        {[
          { label: 'Arrecadado', valor: brl(dados.total_arrecadado) },
          { label: 'Gasto',      valor: brl(dados.total_gasto) },
          { label: 'Doadores',   valor: dados.num_doadores.toLocaleString('pt-BR') },
        ].map(({ label, valor }) => (
          <div key={label} className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className="text-sm font-bold text-gray-900 leading-tight">{valor}</p>
          </div>
        ))}
      </div>

      {/* Origem dos recursos */}
      {origens.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-gray-600 mb-2">Origem dos recursos</p>
          <div className="flex h-3 rounded-full overflow-hidden mb-2 bg-gray-100">
            {origens.map((o) => (
              <div
                key={o.label}
                className={o.cor}
                style={{ width: `${o.pct}%` }}
                title={`${o.label}: ${o.pct}%`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {origens.map((o) => (
              <div key={o.label} className="flex items-center gap-1.5">
                <span className={`w-2.5 h-2.5 rounded-sm flex-shrink-0 ${o.cor}`} />
                <span className="text-xs text-gray-600">
                  {o.label}{' '}
                  <span className="font-semibold text-gray-800">{o.pct}%</span>
                  <span className="text-gray-400"> · {brl(o.valor)}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Composição das despesas */}
      {topDespesas.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-medium text-gray-600 mb-3">Composição das despesas pagas</p>
          <div className="space-y-2.5">
            {topDespesas.map((d) => (
              <div key={d.categoria}>
                <div className="flex justify-between text-xs text-gray-700 mb-1">
                  <span className="truncate pr-2">{d.categoria}</span>
                  <span className="flex-shrink-0 font-medium text-gray-900">{brl(d.valor)}</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-400 rounded-full"
                    style={{ width: `${Math.round((d.valor / maxDesp) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <a
        href={`https://divulgacandcontas.tse.jus.br/divulga/#/candidato/${nrSequencial}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-blue-600 hover:underline"
      >
        Ver detalhes completos no DivulgaCandContas ↗
      </a>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchDespesas, type DespesasData, type TabelaAno } from '@/lib/despesas';

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

function brl(n: number) {
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

interface Props {
  nrSequencial: string;
  cargo: string;
  estado: string;
  numero: string;
}

export default function PainelDespesas({ nrSequencial, cargo, estado, numero }: Props) {
  const [dados, setDados] = useState<DespesasData | null | undefined>(undefined);
  const [anoSel, setAnoSel] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    if (!['deputado-federal', 'senador'].includes(cargo) || !nrSequencial) {
      setDados(null);
      return;
    }
    fetchDespesas(nrSequencial).then((d) => {
      setDados(d);
      if (d?.anos_coletados?.length) {
        setAnoSel(String(Math.max(...d.anos_coletados)));
      }
    });
  }, [nrSequencial, cargo]);

  if (!['deputado-federal', 'senador'].includes(cargo)) return null;

  if (dados === undefined) {
    return (
      <p className="py-4 text-sm text-gray-400 text-center">
        Carregando despesas parlamentares…
      </p>
    );
  }

  if (!dados) {
    return (
      <div>
        <h2 className="text-base font-semibold text-gray-900 mb-2">Cota parlamentar (CEAP)</h2>
        <p className="text-sm text-gray-400">
          Dados de despesas não disponíveis para este candidato.
        </p>
      </div>
    );
  }

  const tabela: TabelaAno | undefined = dados.tabela[anoSel];
  const base = `/${cargo}/${estado}/${numero}/despesas`;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-900">Cota parlamentar (CEAP)</h2>
        <span className="text-xs text-gray-400">Ref. {dados.data_referencia}</span>
      </div>

      {/* Seletor de ano */}
      <div className="flex flex-wrap gap-2 mb-4">
        {[...dados.anos_coletados].sort((a, b) => b - a).map((ano) => (
          <button
            key={ano}
            onClick={() => setAnoSel(String(ano))}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              anoSel === String(ano)
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {ano}
          </button>
        ))}
      </div>

      {tabela ? (
        <>
          <p className="text-sm text-gray-500 mb-3">
            Total em {anoSel}:{' '}
            <span className="font-semibold text-gray-800">{brl(tabela.total_ano)}</span>
          </p>

          {/* Tabela mês × tipo de despesa */}
          <div className="overflow-x-auto -mx-2 rounded-lg border border-gray-100">
            <table className="min-w-full text-xs border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="sticky left-0 bg-gray-50 py-2 px-3 text-left font-semibold text-gray-500 z-10 whitespace-nowrap border-r border-gray-200">
                    Mês
                  </th>
                  {tabela.tipos_ordenados.map((tipo) => (
                    <th
                      key={tipo}
                      title={tipo}
                      className="py-2 px-2 text-right font-medium text-gray-500 whitespace-nowrap"
                    >
                      <span className="block max-w-[110px] truncate">
                        {tipo.replace(/\.$/, '')}
                      </span>
                    </th>
                  ))}
                  <th className="py-2 px-3 text-right font-semibold text-gray-700 whitespace-nowrap border-l border-gray-200">
                    Subtotal
                  </th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((mes) => {
                  const row = tabela.meses[String(mes)];
                  const sub = tabela.subtotal_mes[String(mes)] ?? 0;
                  if (!row && !sub) return null;
                  return (
                    <tr key={mes} className="border-b border-gray-100 hover:bg-gray-50/60">
                      <td className="sticky left-0 bg-white py-2 px-3 font-medium text-gray-600 z-10 whitespace-nowrap border-r border-gray-100">
                        {MESES[mes - 1]}
                      </td>
                      {tabela.tipos_ordenados.map((tipo) => {
                        const valor = row?.[tipo];
                        return (
                          <td key={tipo} className="py-1.5 px-2 text-right">
                            {valor ? (
                              <button
                                onClick={() =>
                                  router.push(
                                    `${base}?ano=${anoSel}&mes=${mes}&tipo=${encodeURIComponent(tipo)}`
                                  )
                                }
                                className="text-indigo-600 hover:text-indigo-800 hover:underline font-medium cursor-pointer"
                              >
                                {brl(valor)}
                              </button>
                            ) : (
                              <span className="text-gray-200">—</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="py-1.5 px-3 text-right font-semibold text-gray-800 border-l border-gray-100">
                        {brl(sub)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-gray-200 bg-gray-50">
                  <td className="sticky left-0 bg-gray-50 py-2 px-3 font-bold text-gray-700 z-10 border-r border-gray-200">
                    Total
                  </td>
                  {tabela.tipos_ordenados.map((tipo) => {
                    const t = Object.values(tabela.meses).reduce(
                      (acc, r) => acc + (r[tipo] ?? 0),
                      0
                    );
                    return (
                      <td key={tipo} className="py-2 px-2 text-right font-semibold text-gray-700">
                        {t > 0 ? brl(t) : <span className="text-gray-300">—</span>}
                      </td>
                    );
                  })}
                  <td className="py-2 px-3 text-right font-bold text-gray-900 border-l border-gray-200">
                    {brl(tabela.total_ano)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="mt-3 text-xs text-gray-400">
            Clique em um valor para ver os documentos e fornecedores detalhados.
          </p>
        </>
      ) : (
        <p className="text-sm text-gray-400">
          Nenhuma despesa registrada em {anoSel}.
        </p>
      )}
    </div>
  );
}

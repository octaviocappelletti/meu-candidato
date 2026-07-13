'use client';

import { useState, useEffect } from 'react';
import { fetchDespesas, type DespesasData, type DespesaDoc } from '@/lib/despesas';

const MESES_NOME = [
  'Janeiro','Fevereiro','Março','Abril','Maio','Junho',
  'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro',
];

function brl(n: number) {
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatData(iso: string) {
  if (!iso) return '—';
  const parte = iso.split('T')[0];
  const [y, m, d] = parte.split('-');
  return `${d}/${m}/${y}`;
}

interface FornecedorAgregado {
  nomeFornecedor: string;
  cnpjCpfFornecedor: string;
  totalLiquido: number;
  qtdDocumentos: number;
}

interface Props {
  nrSequencial: string;
  nomeUrna: string;
  ano: string;
  mes: string;
  tipo: string;
}

export default function DetalhesDespesas({ nrSequencial, nomeUrna, ano, mes, tipo }: Props) {
  const [dados, setDados] = useState<DespesasData | null | undefined>(undefined);

  useEffect(() => {
    fetchDespesas(nrSequencial).then(setDados);
  }, [nrSequencial]);

  if (dados === undefined) {
    return (
      <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <p className="text-sm text-gray-400 text-center py-4">Carregando…</p>
      </section>
    );
  }

  if (!dados) {
    return (
      <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <p className="text-sm text-gray-400">Dados não disponíveis.</p>
      </section>
    );
  }

  const anoNum = Number(ano);
  const mesNum = Number(mes);

  const docs: DespesaDoc[] = dados.documentos.filter(
    (d) => d.ano === anoNum && d.mes === mesNum && d.tipoDespesa === tipo
  );

  // Calcular ranking de fornecedores a partir dos documentos filtrados
  const fornMap = new Map<string, FornecedorAgregado>();
  for (const d of docs) {
    const chave = d.cnpjCpfFornecedor || d.nomeFornecedor;
    if (!chave) continue;
    if (!fornMap.has(chave)) {
      fornMap.set(chave, {
        nomeFornecedor:    d.nomeFornecedor,
        cnpjCpfFornecedor: d.cnpjCpfFornecedor,
        totalLiquido:      0,
        qtdDocumentos:     0,
      });
    }
    const f = fornMap.get(chave)!;
    f.totalLiquido  += d.valorLiquido;
    f.qtdDocumentos += 1;
  }
  const fornecedores = [...fornMap.values()].sort((a, b) => b.totalLiquido - a.totalLiquido);
  const totalFiltrado = docs.reduce((s, d) => s + d.valorLiquido, 0);

  const mesNome = MESES_NOME[mesNum - 1] ?? mes;
  const tituloTipo = tipo.replace(/\.$/, '');

  return (
    <>
      {/* Cabeçalho da despesa */}
      <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
        <h1 className="text-base font-semibold text-gray-900 mb-1">{tituloTipo}</h1>
        <p className="text-xs text-gray-500 mb-5">
          {nomeUrna} · {mesNome} de {ano}
        </p>

        <div className="flex flex-wrap gap-6 border-t border-gray-100 pt-4">
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Valor líquido total</p>
            <p className="text-xl font-bold text-gray-900">{brl(totalFiltrado)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Documentos</p>
            <p className="text-xl font-bold text-gray-900">{docs.length}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Fornecedores</p>
            <p className="text-xl font-bold text-gray-900">{fornecedores.length}</p>
          </div>
        </div>
      </section>

      {/* Ranking de fornecedores */}
      {fornecedores.length > 0 && (
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Fornecedores</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-2 pr-4 text-left font-semibold text-gray-500">Fornecedor</th>
                  <th className="py-2 pr-4 text-left font-semibold text-gray-500">CNPJ / CPF</th>
                  <th className="py-2 pr-4 text-right font-semibold text-gray-500">Docs</th>
                  <th className="py-2 text-right font-semibold text-gray-500">Total líquido</th>
                </tr>
              </thead>
              <tbody>
                {fornecedores.map((f, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 text-gray-800 font-medium">
                      {f.nomeFornecedor || '—'}
                    </td>
                    <td className="py-2 pr-4 text-gray-500 font-mono">
                      {f.cnpjCpfFornecedor || '—'}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-600">{f.qtdDocumentos}</td>
                    <td className="py-2 text-right font-semibold text-gray-800">
                      {brl(f.totalLiquido)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Lista de documentos individuais */}
      {docs.length > 0 && (
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Documentos</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-2 pr-4 text-left font-semibold text-gray-500">Data</th>
                  <th className="py-2 pr-4 text-left font-semibold text-gray-500">Fornecedor</th>
                  <th className="py-2 pr-4 text-right font-semibold text-gray-500">Valor doc.</th>
                  <th className="py-2 pr-4 text-right font-semibold text-gray-500">Valor líq.</th>
                  {docs.some((d) => d.valorGlosa > 0) && (
                    <th className="py-2 pr-4 text-right font-semibold text-gray-500">Glosa</th>
                  )}
                  <th className="py-2 text-center font-semibold text-gray-500">Nota</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 whitespace-nowrap text-gray-600">
                      {formatData(d.dataDocumento)}
                    </td>
                    <td
                      className="py-2 pr-4 text-gray-800 max-w-[200px] truncate"
                      title={d.nomeFornecedor}
                    >
                      {d.nomeFornecedor || '—'}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-600">
                      {brl(d.valorDocumento)}
                    </td>
                    <td className="py-2 pr-4 text-right font-semibold text-gray-800">
                      {brl(d.valorLiquido)}
                    </td>
                    {docs.some((doc) => doc.valorGlosa > 0) && (
                      <td className="py-2 pr-4 text-right text-red-500">
                        {d.valorGlosa > 0 ? brl(d.valorGlosa) : '—'}
                      </td>
                    )}
                    <td className="py-2 text-center">
                      {d.urlDocumento ? (
                        <a
                          href={d.urlDocumento}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 hover:underline"
                        >
                          ver ↗
                        </a>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {docs.length === 0 && (
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <p className="text-sm text-gray-400">
            Nenhum documento encontrado para esta combinação.
          </p>
        </section>
      )}
    </>
  );
}

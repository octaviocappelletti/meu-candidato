import { BemCandidato } from '@/types';

interface Props {
  bens: BemCandidato[];
  total: number;
}

const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export default function ListaBens({ bens, total }: Props) {
  if (bens.length === 0) {
    return (
      <section aria-labelledby="bens-titulo">
        <h2 id="bens-titulo" className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Bens Declarados
        </h2>
        <p className="text-sm text-gray-500">Nenhum bem declarado.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="bens-titulo">
      <h2 id="bens-titulo" className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Bens Declarados
      </h2>
      <div className="rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Descrição</th>
              <th className="text-right px-4 py-2 font-medium whitespace-nowrap">Valor (R$)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {bens.map((bem) => (
              <tr key={bem.ordem} className="bg-white">
                <td className="px-4 py-2 text-gray-700">{bem.descricao}</td>
                <td className="px-4 py-2 text-right text-gray-900 font-mono tabular-nums whitespace-nowrap">
                  {BRL.format(bem.valor)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-gray-50 font-semibold text-gray-900">
            <tr>
              <td className="px-4 py-2">Total</td>
              <td className="px-4 py-2 text-right font-mono tabular-nums whitespace-nowrap">
                {BRL.format(total)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

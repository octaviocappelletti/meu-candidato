'use client';

import { useEffect, useState } from 'react';
import { fetchLegislativo, type Exemplo } from '@/lib/legislativo';

interface Props {
  nrSequencial: string;
}

export default function ListaProposicoesAprovadas({ nrSequencial }: Props) {
  const [lista, setLista] = useState<Exemplo[] | undefined>(undefined);

  useEffect(() => {
    fetchLegislativo().then((mapa) => {
      const dados = mapa?.[nrSequencial];
      setLista(dados?.aprovadas_lista ?? []);
    });
  }, [nrSequencial]);

  if (lista === undefined) {
    return <p className="text-sm text-gray-400">Carregando…</p>;
  }

  if (lista.length === 0) {
    return <p className="text-sm text-gray-500">Nenhuma proposição aprovada encontrada.</p>;
  }

  return (
    <ul className="space-y-4">
      {lista.map((ex, i) => (
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
          {ex.normaGerada && (
            <span className="block mt-0.5 text-green-600 font-medium">
              → {ex.normaGerada}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

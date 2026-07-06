'use client';

import { useState } from 'react';
import { Candidato } from '@/types';
import BarraDeBusca from './BarraDeBusca';
import CardCandidato from './CardCandidato';

interface Props {
  candidatos: Candidato[];
}

export default function ListaCandidatos({ candidatos }: Props) {
  const [busca, setBusca] = useState('');

  const filtrados = busca
    ? candidatos.filter((c) => {
        const termo = busca.toLowerCase();
        return (
          c.nomeUrna.toLowerCase().includes(termo) ||
          String(c.numeroEleitoral).includes(termo)
        );
      })
    : candidatos;

  return (
    <section>
      <BarraDeBusca valor={busca} onChange={setBusca} />

      {filtrados.length === 0 ? (
        <p className="text-center text-gray-500 py-12">
          {candidatos.length === 0
            ? 'Nenhum candidato encontrado para este cargo e estado.'
            : 'Nenhum candidato corresponde à busca.'}
        </p>
      ) : (
        <>
          <p className="text-xs text-gray-400 mb-3">
            {filtrados.length}{' '}
            {filtrados.length === 1 ? 'candidato' : 'candidatos'}
            {busca ? ' encontrados' : ''}
          </p>
          <ul
            className="space-y-3"
            aria-label={`Lista de ${filtrados.length} candidatos`}
          >
            {filtrados.map((candidato) => (
              <li key={candidato.numeroEleitoral}>
                <CardCandidato candidato={candidato} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

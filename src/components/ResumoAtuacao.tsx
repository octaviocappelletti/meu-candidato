'use client';

import { useState, useEffect } from 'react';
import { fetchLegislativo, type LegislativoData } from '@/lib/legislativo';

interface Props {
  nrSequencial: string;
  cargo: string;
  href: string;
}

export default function ResumoAtuacao({ nrSequencial, cargo, href }: Props) {
  const [dados, setDados] = useState<LegislativoData | null | undefined>(undefined);

  useEffect(() => {
    if (!['deputado-federal', 'senador'].includes(cargo) || !nrSequencial) {
      setDados(null);
      return;
    }
    fetchLegislativo().then((mapa) => setDados(mapa ? (mapa[nrSequencial] ?? null) : null));
  }, [nrSequencial, cargo]);

  if (dados === undefined || dados === null) return null;

  const partes: string[] = [];
  partes.push(`${dados.total_apresentadas} proposições`);
  if (dados.por_ano) {
    const anos = Object.keys(dados.por_ano);
    if (anos.length > 1) {
      partes.push(`${anos[0]}–${anos[anos.length - 1]}`);
    }
  }

  return (
    <div className="border-t border-gray-100 px-4 py-2 flex items-center justify-between gap-3">
      <span className="text-xs text-gray-500">{partes.join(' · ')}</span>
      <a
        href={`${href}#atuacao`}
        className="text-xs text-blue-600 hover:underline flex-shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        Ver atuação ↗
      </a>
    </div>
  );
}

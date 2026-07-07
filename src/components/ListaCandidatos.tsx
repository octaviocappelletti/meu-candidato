'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { Candidato } from '@/types';
import {
  EstadoFiltros,
  filtrarCandidatos,
  filtrosFromSearchParams,
  filtrosToSearchParams,
  contarFiltrosPainel,
} from '@/lib/filtros';
import { getFavoritos } from '@/lib/favoritos';
import BarraDeBusca from './BarraDeBusca';
import CardCandidato from './CardCandidato';
import PainelFiltros from './PainelFiltros';
import ChipsFiltrosAtivos from './ChipsFiltrosAtivos';

const CARGOS_COM_FEDERACAO = ['deputado-federal', 'deputado-estadual'];

interface Props {
  candidatos: Candidato[];
  cargo: string;
  uf: string;
}

export default function ListaCandidatos({ candidatos, cargo, uf }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [filtros, setFiltros] = useState<EstadoFiltros>(() =>
    filtrosFromSearchParams(searchParams)
  );
  const [painelAberto, setPainelAberto] = useState(false);
  const [favoritos, setFavoritos] = useState<number[]>([]);

  useEffect(() => {
    setFavoritos(getFavoritos());
  }, []);

  useEffect(() => {
    if (!painelAberto) setFavoritos(getFavoritos());
  }, [painelAberto]);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pushToUrl = useCallback(
    (novos: EstadoFiltros) => {
      router.replace(pathname + filtrosToSearchParams(novos), { scroll: false });
    },
    [router, pathname],
  );

  function handleBuscaChange(busca: string) {
    const novos = { ...filtros, busca };
    setFiltros(novos);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => pushToUrl(novos), 300);
  }

  function handleFiltrosChange(novos: EstadoFiltros) {
    setFiltros(novos);
    pushToUrl(novos);
  }

  const numFiltrosAtivos = contarFiltrosPainel(filtros);
  const filtrados = filtrarCandidatos(candidatos, filtros, favoritos);
  const labelColigacao = 'Agremiação';

  return (
    <section>
      <BarraDeBusca
        valor={filtros.busca}
        onChange={handleBuscaChange}
        numFiltrosAtivos={numFiltrosAtivos}
        onAbrirFiltros={() => setPainelAberto(true)}
      />

      <ChipsFiltrosAtivos
        filtros={filtros}
        totalFiltrado={filtrados.length}
        totalGeral={candidatos.length}
        labelColigacao={labelColigacao}
        onChange={handleFiltrosChange}
      />

      {filtrados.length === 0 ? (
        <p className="text-center text-gray-500 py-12">
          {candidatos.length === 0
            ? 'Nenhum candidato encontrado para este cargo e estado.'
            : 'Nenhum candidato corresponde aos filtros.'}
        </p>
      ) : (
        <ul
          className="space-y-3"
          aria-label={`Lista de ${filtrados.length} candidatos`}
        >
          {filtrados.map((candidato) => (
            <li key={candidato.numeroEleitoral}>
              <CardCandidato candidato={candidato} cargo={cargo} uf={uf} />
            </li>
          ))}
        </ul>
      )}

      <PainelFiltros
        aberto={painelAberto}
        candidatos={candidatos}
        cargo={cargo}
        filtros={filtros}
        onAplicar={handleFiltrosChange}
        onFechar={() => setPainelAberto(false)}
      />
    </section>
  );
}

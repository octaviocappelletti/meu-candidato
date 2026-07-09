'use client';

import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';
import { fetchLegislativo, type LegislativoData } from '@/lib/legislativo';

const CARGOS_APLICAVEIS = ['deputado-federal', 'senador'];

// Paleta neutra — sem conotação de aprovação/reprovação
const CORES_TIPO = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd'];

interface Props {
  nrSequencial: string;
  cargo: string;
}

export default function PainelAtuacao({ nrSequencial, cargo }: Props) {
  const [dados, setDados] = useState<LegislativoData | null | undefined>(undefined);

  useEffect(() => {
    if (!CARGOS_APLICAVEIS.includes(cargo) || !nrSequencial) {
      setDados(null);
      return;
    }
    fetchLegislativo().then((mapa) => setDados(mapa ? (mapa[nrSequencial] ?? null) : null));
  }, [nrSequencial, cargo]);

  if (!CARGOS_APLICAVEIS.includes(cargo)) return null;

  if (dados === undefined) {
    return (
      <p className="py-4 text-sm text-gray-400 text-center">Carregando dados parlamentares…</p>
    );
  }

  if (dados === null) {
    return (
      <div>
        <h2 className="text-base font-semibold text-gray-900 mb-2">Atuação parlamentar</h2>
        <p className="text-sm text-gray-400">
          Dados de atuação parlamentar não disponíveis para este candidato.
        </p>
      </div>
    );
  }

  const casa = dados.casa === 'camara' ? 'Câmara dos Deputados' : 'Senado Federal';
  const urlPortal =
    dados.casa === 'camara'
      ? `https://www.camara.leg.br/deputados/${dados.id_parlamentar}`
      : `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${dados.id_parlamentar}`;

  const dataRef = dados.data_referencia
    ? new Date(dados.data_referencia + 'T00:00:00').toLocaleDateString('pt-BR')
    : null;

  const notaLegislatura =
    dados.casa === 'camara'
      ? 'Proposições da 56ª Legislatura (2019–2023).'
      : 'Proposições das 55ª e 56ª Legislaturas (2015–2023).';

  const dadosTipo = Object.entries(dados.por_tipo)
    .sort((a, b) => b[1] - a[1])
    .map(([tipo, qtd]) => ({ tipo, qtd }));

  const dadosAno = dados.por_ano
    ? Object.entries(dados.por_ano).map(([ano, qtd]) => ({ ano, qtd }))
    : [];

  return (
    <div id="atuacao">
      {/* Cabeçalho */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-gray-900">Atuação parlamentar</h2>
        {dataRef && <span className="text-xs text-gray-400">Atualizado em {dataRef}</span>}
      </div>

      {/* Nota metodológica */}
      <p className="text-xs text-gray-500 mb-5 leading-relaxed bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
        {notaLegislatura} Inclui coautorias. Volume de proposições não indica qualidade
        legislativa — inclui projetos de todos os alcances, de homenagens a reformas estruturais.
      </p>

      {/* KPI principal + por tipo */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="bg-gray-50 rounded-xl px-5 py-3 text-center border border-gray-200">
          <p className="text-xs text-gray-500 mb-0.5">Apresentadas</p>
          <p className="text-2xl font-bold text-gray-900">
            {dados.total_apresentadas.toLocaleString('pt-BR')}
          </p>
        </div>
        {dadosTipo.map(({ tipo, qtd }) => (
          <div key={tipo} className="bg-gray-50 rounded-xl px-4 py-3 text-center border border-gray-200">
            <p className="text-xs text-gray-500 mb-0.5">{tipo}</p>
            <p className="text-xl font-bold text-gray-900">{qtd}</p>
          </div>
        ))}
      </div>

      {/* Funil de situação */}
      {dados.funil && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wider">
            Situação atual
          </p>
          <div className="flex flex-wrap gap-3">
            <div className="bg-blue-50 rounded-xl px-4 py-3 text-center border border-blue-100">
              <p className="text-xs text-blue-600 mb-0.5">Em tramitação</p>
              <p className="text-xl font-bold text-blue-800">
                {dados.funil.em_tramitacao.toLocaleString('pt-BR')}
              </p>
            </div>
            <div className="bg-green-50 rounded-xl px-4 py-3 text-center border border-green-100">
              <p className="text-xs text-green-600 mb-0.5">Viraram lei</p>
              <p className="text-xl font-bold text-green-800">
                {dados.funil.aprovadas.toLocaleString('pt-BR')}
              </p>
            </div>
            <div className="bg-gray-50 rounded-xl px-4 py-3 text-center border border-gray-200">
              <p className="text-xs text-gray-500 mb-0.5">Arquivadas</p>
              <p className="text-xl font-bold text-gray-700">
                {dados.funil.arquivadas.toLocaleString('pt-BR')}
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            "Viraram lei" = Transformadas em Norma Jurídica (Lei, EC ou Decreto Legislativo).
          </p>
        </div>
      )}

      {/* Série temporal */}
      {dadosAno.length > 1 && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wider">
            Proposições por ano
          </p>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={dadosAno} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis dataKey="ano" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
                formatter={(v) => [v, 'Proposições']}
              />
              <Bar dataKey="qtd" fill="#94a3b8" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Distribuição por tipo */}
      {dadosTipo.length > 0 && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wider">
            Por tipo de proposição
          </p>
          <ResponsiveContainer width="100%" height={Math.max(80, dadosTipo.length * 34)}>
            <BarChart
              data={dadosTipo}
              layout="vertical"
              margin={{ top: 4, right: 40, bottom: 4, left: 24 }}
            >
              <XAxis
                type="number"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <YAxis
                type="category"
                dataKey="tipo"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={38}
              />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
                formatter={(v) => [v, 'Proposições']}
              />
              <Bar dataKey="qtd" radius={[0, 3, 3, 0]}>
                {dadosTipo.map((_, i) => (
                  <Cell key={i} fill={CORES_TIPO[i % CORES_TIPO.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 mt-1">
            PL = Projeto de Lei · PLP = Complementar · PEC = Emenda Constitucional ·
            PDL = Decreto Legislativo
          </p>
        </div>
      )}

      {/* Exemplos de projetos */}
      {dados.exemplos.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wider">
            Exemplos de proposições
          </p>
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

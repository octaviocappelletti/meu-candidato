'use client';

import { useState, useEffect } from 'react';
import { Candidato } from '@/types';
import {
  EstadoFiltros, FILTROS_VAZIOS, FAIXAS_ETARIAS, ORDEM_ESCOLARIDADE,
} from '@/lib/filtros';

// ── Sub-componentes ──────────────────────────────────────────────────────────

interface ChipOpcao { valor: string; label: string }

function GrupoChips({
  titulo, opcoes, selecionados, onChange,
}: {
  titulo: string;
  opcoes: ChipOpcao[];
  selecionados: string[];
  onChange: (vals: string[]) => void;
}) {
  if (opcoes.length === 0) return null;
  function toggle(valor: string) {
    onChange(
      selecionados.includes(valor)
        ? selecionados.filter((v) => v !== valor)
        : [...selecionados, valor],
    );
  }
  return (
    <fieldset>
      <legend className="text-sm font-medium text-gray-700 mb-2">{titulo}</legend>
      <div className="flex flex-wrap gap-2">
        {opcoes.map((op) => (
          <button
            key={op.valor}
            type="button"
            onClick={() => toggle(op.valor)}
            aria-pressed={selecionados.includes(op.valor)}
            className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
              selecionados.includes(op.valor)
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-200 hover:border-blue-400'
            }`}
          >
            {op.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function ListaCheckbox({
  titulo, opcoes, selecionados, onChange, placeholderBusca,
}: {
  titulo: string;
  opcoes: string[];
  selecionados: string[];
  onChange: (vals: string[]) => void;
  placeholderBusca?: string;
}) {
  const [busca, setBusca] = useState('');
  if (opcoes.length === 0) return null;
  const filtradas = busca
    ? opcoes.filter((op) => op.toLowerCase().includes(busca.toLowerCase()))
    : opcoes;

  function toggle(valor: string) {
    onChange(
      selecionados.includes(valor)
        ? selecionados.filter((v) => v !== valor)
        : [...selecionados, valor],
    );
  }

  return (
    <fieldset>
      <legend className="text-sm font-medium text-gray-700 mb-2">{titulo}</legend>
      {opcoes.length > 6 && (
        <input
          type="search"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder={placeholderBusca ?? `Buscar ${titulo.toLowerCase()}...`}
          aria-label={`Buscar ${titulo.toLowerCase()}`}
          className="w-full mb-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      )}
      <div className="max-h-44 overflow-y-auto space-y-0.5 pr-1">
        {filtradas.map((op) => (
          <label key={op} className="flex items-center gap-2 cursor-pointer py-1 rounded hover:bg-gray-50 px-1">
            <input
              type="checkbox"
              checked={selecionados.includes(op)}
              onChange={() => toggle(op)}
              className="w-4 h-4 rounded text-blue-600 border-gray-300 focus:ring-blue-400 flex-shrink-0"
            />
            <span className="text-sm text-gray-700 leading-tight">{op}</span>
          </label>
        ))}
        {filtradas.length === 0 && (
          <p className="text-sm text-gray-400 py-2 text-center">Nenhuma opção</p>
        )}
      </div>
    </fieldset>
  );
}

function ToggleFavoritos({
  valor, onChange,
}: { valor: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm font-medium text-gray-700">Apenas favoritos</span>
      <button
        type="button"
        role="switch"
        aria-checked={valor}
        onClick={() => onChange(!valor)}
        className={`relative w-10 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 ${
          valor ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      >
        <span
          className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
            valor ? 'translate-x-4' : ''
          }`}
        />
      </button>
    </label>
  );
}

// ── Painel principal ─────────────────────────────────────────────────────────

function cap(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;
}

const CARGOS_COM_COLIGACAO = ['governador', 'vice-governador', 'senador'];
const CARGOS_COM_FEDERACAO = ['deputado-federal', 'deputado-estadual'];

interface Props {
  aberto: boolean;
  candidatos: Candidato[];
  cargo: string;
  filtros: EstadoFiltros;
  onAplicar: (filtros: EstadoFiltros) => void;
  onFechar: () => void;
}

export default function PainelFiltros({
  aberto, candidatos, cargo, filtros, onAplicar, onFechar,
}: Props) {
  const [local, setLocal] = useState<EstadoFiltros>(FILTROS_VAZIOS);

  // Inicializa o estado local com os filtros atuais ao abrir o painel
  useEffect(() => {
    if (aberto) setLocal(filtros);
  }, [aberto]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!aberto) return null;

  // Deriva opções únicas a partir da lista completa de candidatos
  const partidos = [...new Set(candidatos.map((c) => c.partido).filter(Boolean))].sort();
  const generos  = [...new Set(candidatos.map((c) => c.genero).filter(Boolean))].sort();
  const coresRaca = [...new Set(
    candidatos.map((c) => c.corRaca === 'NÃO DIVULGÁVEL' ? 'NÃO INFORMADO' : c.corRaca).filter(Boolean)
  )].sort();
  const escolaridades = ORDEM_ESCOLARIDADE.filter((e) =>
    candidatos.some((c) => c.grauInstrucao === e)
  );
  const ocupacoes = [...new Set(candidatos.map((c) => c.ocupacao).filter(Boolean))].sort();
  const coligacoes = [...new Set(candidatos.map((c) => c.coligacao).filter(Boolean))].sort();

  const labelColigacao = 'Agremiação';
  const mostrarColigacao =
    CARGOS_COM_COLIGACAO.includes(cargo) || CARGOS_COM_FEDERACAO.includes(cargo);

  const temFaixas = candidatos.some((c) => !!c.dataNascimento);

  function limpar() {
    const novos = { ...FILTROS_VAZIOS, busca: filtros.busca };
    setLocal(novos);
    onAplicar(novos);
    onFechar();
  }

  function aplicar() {
    onAplicar(local);
    onFechar();
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onFechar}
        aria-hidden="true"
      />

      {/* Painel: bottom sheet no mobile, drawer lateral no desktop */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Filtros de candidatos"
        className="fixed bottom-0 inset-x-0 z-50 bg-white rounded-t-2xl shadow-2xl flex flex-col max-h-[88vh] md:inset-y-0 md:right-0 md:left-auto md:w-96 md:rounded-none md:rounded-l-2xl md:max-h-full"
      >
        {/* Cabeçalho */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 flex-shrink-0">
          <h2 className="text-base font-semibold text-gray-900">Filtros</h2>
          <button
            onClick={onFechar}
            aria-label="Fechar painel de filtros"
            className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-800 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Conteúdo rolável */}
        <div className="overflow-y-auto flex-1 px-5 py-5 space-y-6">
          <ListaCheckbox
            titulo="Partido"
            opcoes={partidos}
            selecionados={local.partidos}
            onChange={(v) => setLocal({ ...local, partidos: v })}
            placeholderBusca="Buscar partido..."
          />

          <GrupoChips
            titulo="Sexo"
            opcoes={generos.map((g) => ({ valor: g, label: cap(g) }))}
            selecionados={local.generos}
            onChange={(v) => setLocal({ ...local, generos: v })}
          />

          <ToggleFavoritos
            valor={local.apenasFavoritos}
            onChange={(v) => setLocal({ ...local, apenasFavoritos: v })}
          />

          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm font-medium text-gray-700">Apenas candidatos à reeleição</span>
            <button
              type="button"
              role="switch"
              aria-checked={local.apenasReeleicao}
              onClick={() => setLocal({ ...local, apenasReeleicao: !local.apenasReeleicao })}
              className={`relative w-10 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 ${
                local.apenasReeleicao ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  local.apenasReeleicao ? 'translate-x-4' : ''
                }`}
              />
            </button>
          </label>

          {mostrarColigacao && (
            <ListaCheckbox
              titulo={labelColigacao}
              opcoes={coligacoes}
              selecionados={local.coligacoes}
              onChange={(v) => setLocal({ ...local, coligacoes: v })}
            />
          )}

          <GrupoChips
            titulo="Cor/Raça"
            opcoes={coresRaca.map((r) => ({ valor: r, label: cap(r) }))}
            selecionados={local.coresRaca}
            onChange={(v) => setLocal({ ...local, coresRaca: v })}
          />

          {temFaixas && (
            <GrupoChips
              titulo="Faixa etária"
              opcoes={FAIXAS_ETARIAS.map((f) => ({ valor: f.valor, label: f.label }))}
              selecionados={local.faixasEtarias}
              onChange={(v) => setLocal({ ...local, faixasEtarias: v })}
            />
          )}

          <ListaCheckbox
            titulo="Escolaridade"
            opcoes={escolaridades}
            selecionados={local.escolaridades}
            onChange={(v) => setLocal({ ...local, escolaridades: v })}
          />

          <ListaCheckbox
            titulo="Profissão"
            opcoes={ocupacoes}
            selecionados={local.ocupacoes}
            onChange={(v) => setLocal({ ...local, ocupacoes: v })}
            placeholderBusca="Buscar profissão..."
          />
        </div>

        {/* Rodapé com ações */}
        <div className="flex gap-3 px-5 py-4 border-t border-gray-100 flex-shrink-0">
          <button
            type="button"
            onClick={limpar}
            className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Limpar filtros
          </button>
          <button
            type="button"
            onClick={aplicar}
            className="flex-1 py-2.5 rounded-xl bg-blue-600 text-sm text-white font-medium hover:bg-blue-700 transition-colors"
          >
            Aplicar
          </button>
        </div>
      </div>
    </>
  );
}

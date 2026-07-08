import { Candidato } from '@/types';

export interface EstadoFiltros {
  busca: string;
  partidos: string[];
  coligacoes: string[];
  generos: string[];
  coresRaca: string[];
  faixasEtarias: string[];
  escolaridades: string[];
  ocupacoes: string[];
  apenasFavoritos: boolean;
  apenasReeleicao: boolean;
}

export const FILTROS_VAZIOS: EstadoFiltros = {
  busca: '',
  partidos: [],
  coligacoes: [],
  generos: [],
  coresRaca: [],
  faixasEtarias: [],
  escolaridades: [],
  ocupacoes: [],
  apenasFavoritos: false,
  apenasReeleicao: false,
};

// Mapa cargo → substrings de DS_OCUPACAO que indicam reeleição
const OCUPACOES_REELEICAO: Record<string, string[]> = {
  'presidente':        ['PRESIDENTE DA REPÚBLICA', 'PRESIDENTE'],
  'vice-presidente':   ['VICE-PRESIDENTE'],
  'governador':        ['GOVERNADOR'],
  'vice-governador':   ['VICE-GOVERNADOR'],
  'senador':           ['SENADOR'],
  // TSE registra simplesmente "DEPUTADO" para parlamentares em exercício —
  // sem especificar federal ou estadual. "DEPUTADO" requer match exato para
  // não casar com "DEPUTADO ESTADUAL" ao filtrar deputados federais.
  'deputado-federal':  ['DEPUTADO FEDERAL', 'DEPUTADO DISTRITAL', 'DEPUTADO'],
  'deputado-estadual': ['DEPUTADO ESTADUAL', 'DEPUTADO DISTRITAL', 'DEPUTADO'],
};

export function isReeleicao(candidato: Candidato): boolean {
  const ocup  = (candidato.ocupacao ?? '').toUpperCase().trim();
  const alvos = OCUPACOES_REELEICAO[candidato.cargo] ?? [];
  return alvos.some((a) =>
    // "DEPUTADO" precisa ser match exato — "DEPUTADO ESTADUAL".includes("DEPUTADO") seria verdadeiro
    a === 'DEPUTADO' ? ocup === 'DEPUTADO' : ocup.includes(a)
  );
}

export type FaixaEtaria = '18-29' | '30-44' | '45-59' | '60+';

export const FAIXAS_ETARIAS: { valor: FaixaEtaria; label: string }[] = [
  { valor: '18-29', label: '18–29 anos' },
  { valor: '30-44', label: '30–44 anos' },
  { valor: '45-59', label: '45–59 anos' },
  { valor: '60+',   label: '60 anos ou mais' },
];

export const ORDEM_ESCOLARIDADE = [
  'LÊ E ESCREVE',
  'ENSINO FUNDAMENTAL INCOMPLETO',
  'ENSINO FUNDAMENTAL COMPLETO',
  'ENSINO MÉDIO INCOMPLETO',
  'ENSINO MÉDIO COMPLETO',
  'SUPERIOR INCOMPLETO',
  'SUPERIOR COMPLETO',
  'PÓS-GRADUAÇÃO',
];

export function calcularFaixaEtaria(dataNascimento: string): FaixaEtaria | '' {
  if (!dataNascimento) return '';
  const partes = dataNascimento.split('-').map(Number);
  if (partes.length < 3) return '';
  const [ano, mes, dia] = partes;

  const hoje = new Date();
  let idade = hoje.getFullYear() - ano;
  const mesHoje = hoje.getMonth() + 1;
  if (mesHoje < mes || (mesHoje === mes && hoje.getDate() < dia)) idade--;

  if (idade < 30) return '18-29';
  if (idade < 45) return '30-44';
  if (idade < 60) return '45-59';
  return '60+';
}

export function filtrarCandidatos(
  candidatos: Candidato[],
  filtros: EstadoFiltros,
  favoritos: number[],
): Candidato[] {
  const busca = filtros.busca.trim().toLowerCase();

  return candidatos.filter((c) => {
    if (busca) {
      const matchNome   = c.nomeUrna.toLowerCase().includes(busca);
      const matchNumero = String(c.numeroEleitoral).includes(busca);
      if (!matchNome && !matchNumero) return false;
    }
    if (filtros.partidos.length     && !filtros.partidos.includes(c.partido))           return false;
    if (filtros.coligacoes.length   && !filtros.coligacoes.includes(c.coligacao))       return false;
    if (filtros.generos.length      && !filtros.generos.includes(c.genero))             return false;
    if (filtros.coresRaca.length) {
      const raca = c.corRaca === 'NÃO DIVULGÁVEL' ? 'NÃO INFORMADO' : c.corRaca;
      if (!filtros.coresRaca.includes(raca)) return false;
    }
    if (filtros.escolaridades.length && !filtros.escolaridades.includes(c.grauInstrucao)) return false;
    if (filtros.ocupacoes.length    && !filtros.ocupacoes.includes(c.ocupacao))         return false;
    if (filtros.faixasEtarias.length) {
      const faixa = calcularFaixaEtaria(c.dataNascimento);
      if (!filtros.faixasEtarias.includes(faixa)) return false;
    }
    if (filtros.apenasFavoritos && !favoritos.includes(c.numeroEleitoral)) return false;
    if (filtros.apenasReeleicao && !isReeleicao(c)) return false;
    return true;
  });
}

export function contarFiltrosPainel(filtros: EstadoFiltros): number {
  return (
    filtros.partidos.length +
    filtros.coligacoes.length +
    filtros.generos.length +
    filtros.coresRaca.length +
    filtros.faixasEtarias.length +
    filtros.escolaridades.length +
    filtros.ocupacoes.length +
    (filtros.apenasFavoritos ? 1 : 0) +
    (filtros.apenasReeleicao ? 1 : 0)
  );
}

export function filtrosFromSearchParams(params: URLSearchParams): EstadoFiltros {
  return {
    busca:         params.get('busca') ?? '',
    partidos:      params.get('partido')?.split(',').filter(Boolean)     ?? [],
    coligacoes:    params.get('coligacao')?.split(',').filter(Boolean)   ?? [],
    generos:       params.get('sexo')?.split(',').filter(Boolean)        ?? [],
    coresRaca:     params.get('raca')?.split(',').filter(Boolean)        ?? [],
    faixasEtarias: params.get('idade')?.split(',').filter(Boolean)       ?? [],
    escolaridades: params.get('escolaridade')?.split(',').filter(Boolean) ?? [],
    ocupacoes:     params.get('profissao')?.split(',').filter(Boolean)   ?? [],
    apenasFavoritos: params.get('favoritos') === '1',
    apenasReeleicao: params.get('reeleicao') === '1',
  };
}

export function filtrosToSearchParams(filtros: EstadoFiltros): string {
  const p = new URLSearchParams();
  if (filtros.busca)              p.set('busca',       filtros.busca);
  if (filtros.partidos.length)    p.set('partido',     filtros.partidos.join(','));
  if (filtros.coligacoes.length)  p.set('coligacao',   filtros.coligacoes.join(','));
  if (filtros.generos.length)     p.set('sexo',        filtros.generos.join(','));
  if (filtros.coresRaca.length)   p.set('raca',        filtros.coresRaca.join(','));
  if (filtros.faixasEtarias.length) p.set('idade',     filtros.faixasEtarias.join(','));
  if (filtros.escolaridades.length) p.set('escolaridade', filtros.escolaridades.join(','));
  if (filtros.ocupacoes.length)   p.set('profissao',   filtros.ocupacoes.join(','));
  if (filtros.apenasFavoritos)    p.set('favoritos',   '1');
  if (filtros.apenasReeleicao)    p.set('reeleicao',   '1');
  const qs = p.toString();
  return qs ? `?${qs}` : '';
}

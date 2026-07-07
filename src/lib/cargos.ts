import { CargoSlug } from '@/types';

export interface InfoCargo {
  slug: CargoSlug;
  nome: string;
  federal: boolean;
  descricao: string;
  atribuicoes: string[];
}

export const CARGO_TITULAR: Partial<Record<CargoSlug, CargoSlug>> = {
  'vice-presidente': 'presidente',
  'vice-governador': 'governador',
};

export const CARGO_VICE: Partial<Record<CargoSlug, CargoSlug>> = {
  'presidente': 'vice-presidente',
  'governador': 'vice-governador',
};

export const CARGOS: Record<CargoSlug, InfoCargo> = {
  presidente: {
    slug: 'presidente',
    nome: 'Presidente / Vice-Presidente',
    federal: true,
    descricao:
      'Chefe de Estado e de Governo, eleito em âmbito nacional pelo voto direto, com mandato de 4 anos, podendo ser reeleito uma única vez.',
    atribuicoes: [
      'Chefia o Poder Executivo federal',
      'Nomeia Ministros de Estado e altos cargos públicos',
      'Sanciona, promulga e veta leis aprovadas pelo Congresso',
      'Representa o Brasil nas relações internacionais',
      'Exerce o comando supremo das Forças Armadas',
    ],
  },
  'vice-presidente': {
    slug: 'vice-presidente',
    nome: 'Vice-Presidente',
    federal: true,
    descricao:
      'Substitui o Presidente em casos de impedimento ou vacância e auxilia na condução do governo federal.',
    atribuicoes: [
      'Substitui o Presidente quando necessário',
      'Preside o Conselho da República e o Conselho de Defesa Nacional',
      'Exerce missões especiais delegadas pelo Presidente',
      'Participa das reuniões do Conselho de Governo',
    ],
  },
  governador: {
    slug: 'governador',
    nome: 'Governador / Vice-Governador',
    federal: false,
    descricao:
      'Chefe do Poder Executivo estadual, eleito pelo voto direto dos cidadãos do estado, com mandato de 4 anos.',
    atribuicoes: [
      'Chefia o Poder Executivo estadual',
      'Administra os recursos e serviços públicos do estado',
      'Sanciona e veta leis aprovadas pela Assembleia Legislativa',
      'Nomeia Secretários de Estado e demais cargos estaduais',
      'Representa o estado em âmbito nacional e internacional',
    ],
  },
  'vice-governador': {
    slug: 'vice-governador',
    nome: 'Vice-Governador',
    federal: false,
    descricao:
      'Substitui o Governador em casos de impedimento ou vacância e auxilia na administração do estado.',
    atribuicoes: [
      'Substitui o Governador quando necessário',
      'Exerce missões e representações delegadas pelo Governador',
      'Participa do Conselho de Governo estadual',
    ],
  },
  senador: {
    slug: 'senador',
    nome: 'Senador',
    federal: false,
    descricao:
      'Representante do estado no Senado Federal, eleito pelo voto direto com mandato de 8 anos. Cada estado elege 3 senadores.',
    atribuicoes: [
      'Elabora e vota leis de competência da União',
      'Aprova indicações de autoridades federais (ministros do STF, embaixadores, etc.)',
      'Fiscaliza a execução do orçamento federal',
      'Processa e julga autoridades em crimes de responsabilidade',
      'Aprova tratados e convênios internacionais',
    ],
  },
  'deputado-federal': {
    slug: 'deputado-federal',
    nome: 'Deputado Federal',
    federal: false,
    descricao:
      'Representante do estado na Câmara dos Deputados, eleito pelo voto proporcional, com mandato de 4 anos.',
    atribuicoes: [
      'Elabora e vota leis federais',
      'Fiscaliza o Poder Executivo federal',
      'Aprova o orçamento anual da União',
      'Inicia e aprova o processo de impeachment do Presidente',
      'Representa os interesses dos cidadãos do estado',
    ],
  },
  'deputado-estadual': {
    slug: 'deputado-estadual',
    nome: 'Deputado Estadual',
    federal: false,
    descricao:
      'Membro da Assembleia Legislativa do estado, eleito pelo voto proporcional, com mandato de 4 anos.',
    atribuicoes: [
      'Elabora e vota leis estaduais',
      'Fiscaliza o Poder Executivo do estado',
      'Aprova o orçamento estadual anual',
      'Representa os interesses dos cidadãos do estado',
      'Pode criar, extinguir e modificar municípios dentro do estado',
    ],
  },
};

export function getCargo(slug: string): InfoCargo | undefined {
  return CARGOS[slug as CargoSlug];
}

export function isFederal(slug: string): boolean {
  return CARGOS[slug as CargoSlug]?.federal ?? false;
}

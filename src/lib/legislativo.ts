export interface Exemplo {
  sigla: string;
  numero: number | string | null;
  ano: number | string | null;
  ementa: string;
  url: string;
  data?: string;
  normaGerada?: string;
}

export interface Funil {
  aprovadas: number;
  arquivadas: number;
  em_tramitacao: number;
}

export interface LegislativoData {
  sq_candidato: string;
  casa: 'camara' | 'senado';
  id_parlamentar: number | string;
  confianca_match: number;
  total_apresentadas: number;
  total_aprovadas: number;
  funil?: Funil;
  por_tipo: Record<string, number>;
  por_ano?: Record<string, number>;
  exemplos: Exemplo[];
  aprovadas_lista?: Exemplo[];
  pec_total?: number;
  pec_autor_principal?: number;
  pl_total?: number;
  pl_autor_principal?: number;
  pec_aprovadas?: number;
  pec_aprovadas_autor_principal?: number;
  pl_aprovadas?: number;
  pl_aprovadas_autor_principal?: number;
  emendas_mpv_total?: number;
  emendas_mpv_autor_unico?: number;
  pec_lista?: Exemplo[];
  pl_lista?: Exemplo[];
  emendas_mpv_lista?: Array<{ identificacao: string; ementa: string; url: string; data: string; autor_unico: boolean }>;
  data_referencia: string;
}

let _fetch: Promise<Record<string, LegislativoData> | null> | null = null;

export function fetchLegislativo(): Promise<Record<string, LegislativoData> | null> {
  if (!_fetch) {
    _fetch = fetch('/legislativo/legislativo.json')
      .then((r) => (r.ok ? (r.json() as Promise<Record<string, LegislativoData>>) : null))
      .catch(() => null);
  }
  return _fetch;
}

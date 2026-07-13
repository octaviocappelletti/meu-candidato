export interface DespesaDoc {
  ano: number;
  mes: number;
  tipoDespesa: string;
  dataDocumento: string;
  numDocumento: string;
  valorDocumento: number;
  valorLiquido: number;
  valorGlosa: number;
  nomeFornecedor: string;
  cnpjCpfFornecedor: string;
  urlDocumento: string;
}

export interface FornecedorRanking {
  nomeFornecedor: string;
  cnpjCpfFornecedor: string;
  totalLiquido: number;
  qtdDocumentos: number;
  tipos: string[];
}

export interface TabelaAno {
  tipos_ordenados: string[];
  meses: Record<string, Record<string, number>>;
  subtotal_mes: Record<string, number>;
  total_ano: number;
}

export interface DespesasData {
  id_parlamentar: number;
  nome: string;
  anos_coletados: number[];
  tabela: Record<string, TabelaAno>;
  documentos: DespesaDoc[];
  ranking_fornecedores: FornecedorRanking[];
  data_referencia: string;
}

const _cache = new Map<string, Promise<DespesasData | null>>();

export function fetchDespesas(nrSequencial: string): Promise<DespesasData | null> {
  if (!_cache.has(nrSequencial)) {
    const p = fetch(`/despesas/${nrSequencial}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<DespesasData>) : null))
      .catch(() => null);
    _cache.set(nrSequencial, p);
  }
  return _cache.get(nrSequencial)!;
}

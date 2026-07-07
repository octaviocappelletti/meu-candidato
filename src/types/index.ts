export type CargoSlug =
  | 'presidente'
  | 'vice-presidente'
  | 'governador'
  | 'vice-governador'
  | 'senador'
  | 'deputado-federal'
  | 'deputado-estadual';

export type UF =
  | 'AC' | 'AL' | 'AP' | 'AM' | 'BA' | 'CE' | 'DF' | 'ES' | 'GO'
  | 'MA' | 'MT' | 'MS' | 'MG' | 'PA' | 'PB' | 'PR' | 'PE' | 'PI'
  | 'RJ' | 'RN' | 'RS' | 'RO' | 'RR' | 'SC' | 'SP' | 'SE' | 'TO';

export interface Candidato {
  nomeUrna: string;
  nomeCompleto: string;
  numeroEleitoral: number;
  cargo: CargoSlug;
  uf: UF | 'BR';
  partido: string;
  coligacao: string;
  situacao: string;
  urlFoto: string;
  genero: string;
  corRaca: string;
  grauInstrucao: string;
  ocupacao: string;
  dataNascimento: string;
  // Apenas para presidente e governador
  nomeVice?: string;
  urlFotoVice?: string;
}

export interface BemCandidato {
  ordem: number;
  descricao: string;
  valor: number;
}

export interface CandidatoDetalhado extends Candidato {
  emailCampanha: string;
  urlFacebook: string;
  urlInstagram: string;
  urlTwitter: string;
  urlYoutube: string;
  totalBens: number;
  bens: BemCandidato[];
}

export interface PropostaGoverno {
  texto: string;
  urlPdf: string;
}

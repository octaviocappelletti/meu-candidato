export type CargoSlug =
  | 'presidente'
  | 'governador'
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
  situacao: string;
  urlFoto: string;
}

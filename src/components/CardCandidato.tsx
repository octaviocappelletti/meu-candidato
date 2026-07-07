import Link from 'next/link';
import { Candidato } from '@/types';
import BotaoFavoritar from './BotaoFavoritar';
import FotoAvatar from './FotoAvatar';

interface Props {
  candidato: Candidato;
  cargo: string;
  uf: string;
}

export default function CardCandidato({ candidato, cargo, uf }: Props) {
  const temVice = !!(candidato.nomeVice);
  const href = `/${cargo}/${uf}/${candidato.numeroEleitoral}`;

  return (
    <article className="flex items-center gap-4 bg-white rounded-xl border border-gray-200 px-4 py-3 shadow-sm hover:border-blue-300 hover:shadow-md transition-all">
      <Link href={href} className="flex items-center gap-4 flex-1 min-w-0" aria-label={`Ver detalhes de ${candidato.nomeUrna}`}>
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <FotoAvatar src={candidato.urlFoto} alt={candidato.nomeUrna} size="md" />
          {temVice && (
            <FotoAvatar src={candidato.urlFotoVice ?? ''} alt={candidato.nomeVice!} size="sm" />
          )}
        </div>


        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 truncate">{candidato.nomeUrna}</p>
          {temVice && (
            <p className="text-xs text-gray-500 truncate">Vice: {candidato.nomeVice}</p>
          )}
          <p className="text-sm text-gray-500 truncate">{candidato.partido}</p>
          <p className="text-sm font-mono text-gray-700">Nº {candidato.numeroEleitoral}</p>
        </div>
      </Link>

      <BotaoFavoritar numeroEleitoral={candidato.numeroEleitoral} nomeUrna={candidato.nomeUrna} />
    </article>
  );
}

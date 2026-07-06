import Image from 'next/image';
import { Candidato } from '@/types';
import BotaoFavoritar from './BotaoFavoritar';

interface Props {
  candidato: Candidato;
}

export default function CardCandidato({ candidato }: Props) {
  return (
    <article className="flex items-center gap-4 bg-white rounded-xl border border-gray-200 px-4 py-3 shadow-sm">
      <div className="relative w-14 h-14 rounded-full overflow-hidden bg-gray-100 flex-shrink-0">
        {candidato.urlFoto ? (
          <Image
            src={candidato.urlFoto}
            alt={candidato.nomeUrna}
            fill
            sizes="56px"
            className="object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-8 h-8"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-semibold text-gray-900 truncate">{candidato.nomeUrna}</p>
        <p className="text-sm text-gray-500 truncate">{candidato.partido}</p>
        <p className="text-sm font-mono text-gray-700">Nº {candidato.numeroEleitoral}</p>
      </div>

      <BotaoFavoritar
        numeroEleitoral={candidato.numeroEleitoral}
        nomeUrna={candidato.nomeUrna}
      />
    </article>
  );
}

import Image from 'next/image';
import Link from 'next/link';
import { Candidato } from '@/types';
import BotaoFavoritar from './BotaoFavoritar';

interface Props {
  candidato: Candidato;
  cargo: string;
  uf: string;
}

// Aceita apenas URLs do Supabase Storage para evitar crash do next/image com domínios não configurados
function urlFotoValida(url: string): string {
  if (!url) return '';
  try {
    const { hostname } = new URL(url);
    return hostname === 'ujuiceqnvkwcizliwvcf.supabase.co' ? url : '';
  } catch {
    return '';
  }
}

function FotoAvatar({ src, alt, size }: { src: string; alt: string; size: 'md' | 'sm' }) {
  const dim = size === 'md' ? 'w-14 h-14' : 'w-8 h-8';
  const iconSize = size === 'md' ? 'w-8 h-8' : 'w-5 h-5';
  const srcValido = urlFotoValida(src);
  return (
    <div className={`relative ${dim} rounded-full overflow-hidden bg-gray-100 flex-shrink-0`}>
      {srcValido ? (
        <Image src={srcValido} alt={alt} fill sizes={size === 'md' ? '56px' : '32px'} className="object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-gray-400">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={iconSize} aria-hidden="true">
            <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clipRule="evenodd" />
          </svg>
        </div>
      )}
    </div>
  );
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

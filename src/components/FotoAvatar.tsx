'use client';

import { useState } from 'react';
import Image from 'next/image';

const TAMANHOS = {
  sm: { css: 'w-8 h-8',   icon: 'w-5 h-5', px: '32px',  borda: '' },
  md: { css: 'w-14 h-14', icon: 'w-8 h-8', px: '56px',  borda: '' },
  lg: { css: 'w-28 h-28', icon: 'w-14 h-14', px: '112px', borda: 'border-4 border-white shadow-md' },
};

function Placeholder({ iconClass }: { iconClass: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center text-gray-400">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={iconClass} aria-hidden="true">
        <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clipRule="evenodd" />
      </svg>
    </div>
  );
}

interface Props {
  src: string;
  alt: string;
  size: 'sm' | 'md' | 'lg';
}

export default function FotoAvatar({ src, alt, size }: Props) {
  const [erro, setErro] = useState(false);
  const t = TAMANHOS[size];

  return (
    <div className={`relative ${t.css} rounded-full overflow-hidden bg-gray-100 flex-shrink-0 ${t.borda}`}>
      {src && !erro ? (
        <Image
          src={src}
          alt={alt}
          fill
          sizes={t.px}
          className="object-cover"
          onError={() => setErro(true)}
        />
      ) : (
        <Placeholder iconClass={t.icon} />
      )}
    </div>
  );
}

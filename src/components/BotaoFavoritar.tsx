'use client';

import { useState, useEffect } from 'react';
import { isFavorito, toggleFavorito } from '@/lib/favoritos';

interface Props {
  numeroEleitoral: number;
  nomeUrna: string;
}

export default function BotaoFavoritar({ numeroEleitoral, nomeUrna }: Props) {
  const [favoritado, setFavoritado] = useState(false);

  useEffect(() => {
    setFavoritado(isFavorito(numeroEleitoral));
  }, [numeroEleitoral]);

  function handleClick() {
    toggleFavorito(numeroEleitoral);
    setFavoritado((prev) => !prev);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={
        favoritado
          ? `Remover ${nomeUrna} dos favoritos`
          : `Favoritar ${nomeUrna}`
      }
      aria-pressed={favoritado}
      className="p-2 rounded-full hover:bg-pink-50 transition-colors focus:outline-none focus:ring-2 focus:ring-pink-400 focus:ring-offset-1"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        aria-hidden="true"
        className={`w-6 h-6 transition-colors ${
          favoritado
            ? 'fill-pink-500 stroke-pink-500'
            : 'fill-none stroke-gray-400 hover:stroke-pink-400'
        }`}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12Z"
        />
      </svg>
    </button>
  );
}

const STORAGE_KEY = 'favoritos';

export function getFavoritos(): number[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

export function toggleFavorito(numeroEleitoral: number): void {
  const favoritos = getFavoritos();
  const index = favoritos.indexOf(numeroEleitoral);
  if (index === -1) {
    favoritos.push(numeroEleitoral);
  } else {
    favoritos.splice(index, 1);
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favoritos));
}

export function isFavorito(numeroEleitoral: number): boolean {
  return getFavoritos().includes(numeroEleitoral);
}

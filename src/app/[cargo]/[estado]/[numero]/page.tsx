import { notFound } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { getCargo } from '@/lib/cargos';
import { ESTADOS } from '@/lib/estados';
import { buscarCandidatoDetalhado } from '@/lib/supabase';
import BotaoFavoritar from '@/components/BotaoFavoritar';
import RedesSociais from '@/components/RedesSociais';
import ListaBens from '@/components/ListaBens';

interface Props {
  params: Promise<{ cargo: string; estado: string; numero: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { cargo, numero } = await params;
  const infoCargo = getCargo(cargo);
  if (!infoCargo) return {};
  return {
    title: `Candidato Nº ${numero} · ${infoCargo.nome} · Meu Candidato`,
  };
}

function urlFotoValida(url: string): string {
  if (!url) return '';
  try {
    const { hostname } = new URL(url);
    return hostname === 'ujuiceqnvkwcizliwvcf.supabase.co' ? url : '';
  } catch {
    return '';
  }
}

function AvatarGrande({ src, alt }: { src: string; alt: string }) {
  const srcValido = urlFotoValida(src);
  return (
    <div className="relative w-28 h-28 rounded-full overflow-hidden bg-gray-100 border-4 border-white shadow-md flex-shrink-0">
      {srcValido ? (
        <Image src={srcValido} alt={alt} fill sizes="112px" className="object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-gray-400">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-14 h-14" aria-hidden="true">
            <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clipRule="evenodd" />
          </svg>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="flex flex-col sm:flex-row sm:gap-4">
      <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wider sm:w-36 flex-shrink-0">{label}</dt>
      <dd className="text-sm text-gray-900 mt-0.5 sm:mt-0">{value}</dd>
    </div>
  );
}

export default async function PaginaDetalhe({ params }: Props) {
  const { cargo, estado, numero } = await params;
  const infoCargo = getCargo(cargo);

  if (!infoCargo) notFound();

  const numeroEleitoral = Number(numero);
  if (!Number.isInteger(numeroEleitoral) || numeroEleitoral <= 0) notFound();

  const uf = estado.toUpperCase();
  const estadoNome = ESTADOS.find((e) => e.uf === uf)?.nome ?? uf;

  let candidato;
  try {
    candidato = await buscarCandidatoDetalhado(cargo, uf === 'BR' ? 'br' : estado, numeroEleitoral);
  } catch {
    candidato = null;
  }

  if (!candidato) notFound();

  const voltarHref = `/${cargo}/${estado}`;

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <nav className="mb-6">
          <Link href={voltarHref} className="text-sm text-blue-600 hover:underline">
            ← {infoCargo.nome}{uf !== 'BR' ? ` — ${estadoNome}` : ''}
          </Link>
        </nav>

        {/* Cabeçalho do candidato */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <div className="flex items-start gap-5">
            <div className="flex flex-col items-center gap-2">
              <AvatarGrande src={candidato.urlFoto} alt={candidato.nomeUrna} />
              {candidato.nomeVice && (
                <div className="flex flex-col items-center">
                  <AvatarGrande src={candidato.urlFotoVice ?? ''} alt={candidato.nomeVice} />
                  <span className="text-xs text-gray-500 mt-1">Vice</span>
                </div>
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-gray-900">{candidato.nomeUrna}</h1>
                  {candidato.nomeVice && (
                    <p className="text-sm text-gray-500">Vice: {candidato.nomeVice}</p>
                  )}
                </div>
                <BotaoFavoritar numeroEleitoral={candidato.numeroEleitoral} nomeUrna={candidato.nomeUrna} />
              </div>

              <p className="mt-1 text-sm text-gray-700 font-medium">{candidato.partido}</p>
              {candidato.coligacao && (
                <p className="text-xs text-gray-500 mt-0.5">{candidato.coligacao}</p>
              )}
              <p className="mt-2 text-lg font-mono font-semibold text-gray-800">
                Nº {candidato.numeroEleitoral}
              </p>
            </div>
          </div>

          {/* Dados pessoais */}
          <dl className="mt-5 space-y-2 border-t border-gray-100 pt-4">
            <InfoRow label="Nome completo" value={candidato.nomeCompleto} />
            <InfoRow label="Nascimento" value={candidato.dataNascimento} />
            <InfoRow label="Grau de instrução" value={candidato.grauInstrucao} />
            <InfoRow label="Ocupação" value={candidato.ocupacao} />
            <InfoRow label="Situação" value={candidato.situacao} />
          </dl>
        </section>

        {/* Redes sociais */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <RedesSociais
            email={candidato.emailCampanha}
            facebook={candidato.urlFacebook}
            instagram={candidato.urlInstagram}
            twitter={candidato.urlTwitter}
            youtube={candidato.urlYoutube}
          />
        </section>

        {/* Bens declarados */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <ListaBens bens={candidato.bens} total={candidato.totalBens} />
        </section>

        <p className="mt-6 text-center text-xs text-gray-400">
          Dados oficiais do TSE · Eleições 2026
        </p>
      </div>
    </main>
  );
}

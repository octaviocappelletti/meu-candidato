import { notFound } from 'next/navigation';
import Link from 'next/link';
import FotoAvatar from '@/components/FotoAvatar';
import { getCargo, CARGO_TITULAR, CARGO_VICE } from '@/lib/cargos';
import { ESTADOS } from '@/lib/estados';
import { buscarCandidatoDetalhado, buscarPropostaGoverno } from '@/lib/supabase';
import BotaoFavoritar from '@/components/BotaoFavoritar';
import RedesSociais from '@/components/RedesSociais';
import ListaBens from '@/components/ListaBens';
import PropostaGoverno from '@/components/PropostaGoverno';
import TransparenciaFinanceira from '@/components/TransparenciaFinanceira';

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

  const cargoSlug = cargo as import('@/types').CargoSlug;
  const titularCargo = CARGO_TITULAR[cargoSlug];
  const viceCargo = CARGO_VICE[cargoSlug];
  const isVice = !!titularCargo;

  let candidato;
  let proposta = null;
  let titular = null;
  try {
    const promises: [
      ReturnType<typeof buscarCandidatoDetalhado>,
      ReturnType<typeof buscarPropostaGoverno>,
      ReturnType<typeof buscarCandidatoDetalhado> | Promise<null>,
    ] = [
      buscarCandidatoDetalhado(cargo, uf === 'BR' ? 'br' : estado, numeroEleitoral),
      buscarPropostaGoverno(cargo, uf === 'BR' ? 'BR' : estado, numeroEleitoral).catch(() => null),
      isVice
        ? buscarCandidatoDetalhado(titularCargo!, uf === 'BR' ? 'br' : estado, numeroEleitoral).catch(() => null)
        : Promise.resolve(null),
    ];
    [candidato, proposta, titular] = await Promise.all(promises);
  } catch {
    candidato = null;
  }

  if (!candidato) notFound();

  // Vice: volta para página do titular. Titular: volta para lista do cargo.
  const voltarHref = isVice
    ? `/${titularCargo}/${estado}/${numero}`
    : `/${cargo}/${estado}`;
  const voltarLabel = isVice && titular
    ? `← ${titular.nomeUrna}`
    : `← ${infoCargo.nome}${uf !== 'BR' ? ` — ${estadoNome}` : ''}`;

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <nav className="mb-6">
          <Link href={voltarHref} className="text-sm text-blue-600 hover:underline">
            {voltarLabel}
          </Link>
        </nav>

        {/* Banner de titular (exibido apenas na página do vice) */}
        {isVice && titular && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 flex items-center gap-3">
            <FotoAvatar src={titular.urlFoto} alt={titular.nomeUrna} size="sm" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-blue-600 font-semibold uppercase tracking-wider">Chapa de</p>
              <p className="text-sm font-bold text-blue-900 truncate">{titular.nomeUrna}</p>
            </div>
            <Link href={voltarHref} className="text-xs text-blue-600 hover:underline flex-shrink-0">
              Ver titular ↗
            </Link>
          </div>
        )}

        {/* Cabeçalho do candidato */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <div className="flex items-start gap-5">
            <div className="flex flex-col items-center gap-2">
              <FotoAvatar src={candidato.urlFoto} alt={candidato.nomeUrna} size="lg" />
              {candidato.nomeVice && viceCargo && (
                <Link
                  href={`/${viceCargo}/${estado}/${numero}`}
                  className="flex flex-col items-center group"
                  title={`Ver informações de ${candidato.nomeVice}`}
                >
                  <div className="ring-2 ring-transparent group-hover:ring-blue-400 rounded-full transition-all">
                    <FotoAvatar src={candidato.urlFotoVice ?? ''} alt={candidato.nomeVice} size="lg" />
                  </div>
                  <span className="text-xs text-blue-600 group-hover:underline mt-1">Vice ↗</span>
                </Link>
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-gray-900">{candidato.nomeUrna}</h1>
                  {candidato.nomeVice && viceCargo && (
                    <Link
                      href={`/${viceCargo}/${estado}/${numero}`}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Vice: {candidato.nomeVice} ↗
                    </Link>
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
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <ListaBens bens={candidato.bens} total={candidato.totalBens} />
        </section>

        {/* Transparência financeira */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <TransparenciaFinanceira nrSequencial={candidato.nrSequencial} uf={uf} />
        </section>

        {/* Proposta de governo */}
        {proposta && (
          <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <PropostaGoverno proposta={proposta} />
          </section>
        )}

        <p className="mt-6 text-center text-xs text-gray-400">
          Dados oficiais do TSE · Eleições 2026
        </p>
      </div>
    </main>
  );
}

interface Props {
  email?: string;
  facebook?: string;
  instagram?: string;
  twitter?: string;
  youtube?: string;
}

interface Rede {
  label: string;
  href: string;
  icon: React.ReactNode;
}

export default function RedesSociais({ email, facebook, instagram, twitter, youtube }: Props) {
  const redes: Rede[] = [
    email && {
      label: 'E-mail',
      href: `mailto:${email}`,
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
        </svg>
      ),
    },
    facebook && { label: 'Facebook', href: facebook, icon: <span className="text-sm font-bold">f</span> },
    instagram && { label: 'Instagram', href: instagram, icon: <span className="text-sm font-bold">ig</span> },
    twitter && { label: 'X / Twitter', href: twitter, icon: <span className="text-sm font-bold">𝕏</span> },
    youtube && { label: 'YouTube', href: youtube, icon: <span className="text-sm font-bold">▶</span> },
  ].filter(Boolean) as Rede[];

  if (redes.length === 0) return null;

  return (
    <section aria-labelledby="redes-titulo">
      <h2 id="redes-titulo" className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Contato e Redes Sociais
      </h2>
      <div className="flex flex-wrap gap-2">
        {redes.map((rede) => (
          <a
            key={rede.label}
            href={rede.href}
            target={rede.href.startsWith('mailto') ? undefined : '_blank'}
            rel="noopener noreferrer"
            aria-label={rede.label}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-white text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors text-sm"
          >
            {rede.icon}
            <span>{rede.label}</span>
          </a>
        ))}
      </div>
    </section>
  );
}

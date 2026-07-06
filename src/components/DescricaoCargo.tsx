import { InfoCargo } from '@/lib/cargos';

interface Props {
  cargo: InfoCargo;
}

export default function DescricaoCargo({ cargo }: Props) {
  return (
    <section
      aria-label={`Sobre o cargo de ${cargo.nome}`}
      className="mb-6 p-4 bg-blue-50 rounded-xl border border-blue-100"
    >
      <h2 className="font-semibold text-blue-900 mb-1">Sobre o cargo</h2>
      <p className="text-sm text-blue-800 mb-3">{cargo.descricao}</p>

      <h3 className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2">
        Principais atribuições
      </h3>
      <ul className="text-sm text-blue-800 space-y-1">
        {cargo.atribuicoes.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden="true" className="mt-0.5 text-blue-500">
              •
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

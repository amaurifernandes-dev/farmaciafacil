import type { Loja } from "../api/tipos";

/** Escolha de loja. Com `todas`, a primeira opção é ver todas as lojas juntas. */
export default function SeletorLoja({
  lojas,
  valor,
  aoMudar,
  todas,
  rotulo = "Loja",
}: {
  lojas: Loja[];
  valor: string;
  aoMudar: (lojaId: string) => void;
  todas?: string;
  rotulo?: string;
}) {
  // Com uma loja só não há o que escolher.
  if (lojas.length <= 1 && todas) return null;
  return (
    <label className="seletor-loja">
      {rotulo}
      <select value={valor} onChange={(e) => aoMudar(e.target.value)}>
        {todas && <option value="">{todas}</option>}
        {lojas.map((l) => (
          <option key={l.id} value={l.id}>
            {l.nome}
          </option>
        ))}
      </select>
    </label>
  );
}

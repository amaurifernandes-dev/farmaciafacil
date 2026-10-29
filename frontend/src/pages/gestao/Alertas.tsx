import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Alertas as TipoAlertas, LoteComProduto } from "../../api/tipos";
import { data, quantidade } from "../../formato";

export default function Alertas() {
  const [dias, setDias] = useState(90);
  const [alertas, setAlertas] = useState<TipoAlertas | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<TipoAlertas>(`/estoque/alertas?dias=${dias}`)
      .then(setAlertas)
      .catch((e) => setErro(mensagem(e)));
  }, [dias]);

  if (erro) return <p className="erro">{erro}</p>;
  if (!alertas) return <p>Carregando...</p>;

  return (
    <div className="pagina">
      <h1>Alertas de estoque</h1>

      <h2>Vencidos ({alertas.vencidos.length})</h2>
      <TabelaLotes lotes={alertas.vencidos} />

      <h2>
        Vencendo em até{" "}
        <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
          <option value={30}>30</option>
          <option value={60}>60</option>
          <option value={90}>90</option>
        </select>{" "}
        dias ({alertas.vencendo.length})
      </h2>
      <TabelaLotes lotes={alertas.vencendo} />

      <h2>Abaixo do estoque mínimo ({alertas.abaixo_do_minimo.length})</h2>
      <table className="tabela">
        <thead>
          <tr>
            <th>Produto</th>
            <th className="num">Saldo</th>
            <th className="num">Mínimo</th>
          </tr>
        </thead>
        <tbody>
          {alertas.abaixo_do_minimo.map((p) => (
            <tr key={p.produto_id}>
              <td>{p.nome}</td>
              <td className="num">{quantidade(p.saldo)}</td>
              <td className="num">{quantidade(p.estoque_minimo)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TabelaLotes({ lotes }: { lotes: LoteComProduto[] }) {
  if (lotes.length === 0) return <p className="vazio">Nenhum lote</p>;
  return (
    <table className="tabela">
      <thead>
        <tr>
          <th>Produto</th>
          <th>Lote</th>
          <th>Validade</th>
          <th className="num">Dias</th>
          <th className="num">Quantidade</th>
        </tr>
      </thead>
      <tbody>
        {lotes.map((l) => (
          <tr key={l.id}>
            <td>{l.produto_nome}</td>
            <td>{l.numero_lote}</td>
            <td>{data(l.validade)}</td>
            <td className="num">{l.dias_para_vencer}</td>
            <td className="num">{quantidade(l.quantidade)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

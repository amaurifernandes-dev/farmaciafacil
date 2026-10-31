import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/cliente";
import type { AtendimentoServico } from "../../api/tipos";

/** Na ficha do cliente: as pressões, glicemias e aplicações feitas na farmácia. */
export default function ServicosDoCliente({ clienteId }: { clienteId: string }) {
  const [lista, setLista] = useState<AtendimentoServico[] | null>(null);

  useEffect(() => {
    api<AtendimentoServico[]>(`/servicos/cliente/${clienteId}`)
      .then(setLista)
      .catch(() => setLista([]));
  }, [clienteId]);

  if (!lista || lista.length === 0) return null;
  return (
    <div className="cartao cartao-separado servicos-ficha">
      <div className="cartao-cabecalho">
        <h2>Serviços farmacêuticos</h2>
        <Link to="/servicos" className="botao-pequeno">
          Novo atendimento
        </Link>
      </div>
      <table className="tabela">
        <thead>
          <tr>
            <th>Data</th>
            <th>Serviço</th>
            <th>Resultado</th>
            <th>Farmacêutico</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {lista.map((a) => (
            <tr key={a.id}>
              <td>{new Date(a.criado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</td>
              <td>{a.servico_nome}</td>
              <td>
                <strong>{a.resultado_texto}</strong>
                {a.aviso && <span className="livro-detalhe aviso-mini">{a.aviso.texto}</span>}
              </td>
              <td>{a.farmaceutico}</td>
              <td className="acoes-tabela">
                <button type="button" className="botao-pequeno" onClick={() => window.open(`/servicos/declaracao/${a.id}`, "_blank")}>
                  Declaração
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

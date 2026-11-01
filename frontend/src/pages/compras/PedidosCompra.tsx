import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { PedidoCompraResumo, StatusPedidoCompra } from "../../api/tipos";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";

export const STATUS_PEDIDO: Record<StatusPedidoCompra, { rotulo: string; classe: string }> = {
  aberto: { rotulo: "Não enviado", classe: "etiqueta etiqueta-neutra" },
  enviado: { rotulo: "Aguardando nota", classe: "etiqueta" },
  parcial: { rotulo: "Chegou em parte", classe: "etiqueta etiqueta-alerta" },
  recebido: { rotulo: "Recebido", classe: "etiqueta ok" },
  cancelado: { rotulo: "Cancelado", classe: "etiqueta erro-etiqueta" },
};

const FILTROS = [
  { valor: "abertos", rotulo: "Em aberto" },
  { valor: "recebido", rotulo: "Recebidos" },
  { valor: "cancelado", rotulo: "Cancelados" },
  { valor: "", rotulo: "Todos" },
];

/** Pedidos de compra guardados: o que foi pedido a cada fornecedor e se a nota já chegou. */
export default function PedidosCompra() {
  const lojas = useLojas();
  const [filtro, setFiltro] = useState("abertos");
  const [pedidos, setPedidos] = useState<PedidoCompraResumo[] | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setPedidos(null);
    api<PedidoCompraResumo[]>(`/compras/pedidos${filtro ? `?status=${filtro}` : ""}`)
      .then(setPedidos)
      .catch((e) => setErro(mensagem(e)));
  }, [filtro]);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Pedidos de compra</h1>
          <p className="vazio">
            O que foi pedido a cada fornecedor. Quando a nota chega, o sistema confere com o pedido e mostra o que faltou.
          </p>
        </div>
        <Link to="/compras/sugestao" className="botao-contorno">
          Montar pela sugestão
        </Link>
      </div>

      <div className="acoes espaco-acima filtros-pedido" role="group" aria-label="Mostrar">
        {FILTROS.map((f) => (
          <button
            key={f.valor}
            type="button"
            className={filtro === f.valor ? "botao-pequeno ativo" : "botao-pequeno"}
            aria-pressed={filtro === f.valor}
            onClick={() => setFiltro(f.valor)}
          >
            {f.rotulo}
          </button>
        ))}
      </div>
      {erro && <p className="erro espaco-acima">{erro}</p>}

      <section className="cartao espaco-acima">
        {pedidos && pedidos.length === 0 ? (
          <p className="lista-vazia">
            {filtro === "abertos"
              ? "Nenhum pedido em aberto. Peça ao assistente para montar um pedido e toque em “Salvar pedido”."
              : "Nenhum pedido aqui."}
          </p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Pedido</th>
                  <th>Fornecedor</th>
                  <th>Feito em</th>
                  {lojas.length > 1 && <th>Loja</th>}
                  <th className="num">Itens</th>
                  <th className="num">Estimado</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {pedidos?.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link to={`/compras/pedidos/${p.id}`}>nº {p.numero}</Link>
                    </td>
                    <td>{p.fornecedor_nome}</td>
                    <td>{data(p.criado_em)}</td>
                    {lojas.length > 1 && <td>{p.loja_nome}</td>}
                    <td className="num">{p.quantidade_itens}</td>
                    <td className="num">{reais(p.total_estimado)}</td>
                    <td>
                      <span className={STATUS_PEDIDO[p.status].classe}>{STATUS_PEDIDO[p.status].rotulo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

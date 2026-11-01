import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { PedidoCompra as Pedido } from "../../api/tipos";
import { data, quantidade, reais } from "../../formato";
import { STATUS_NOTA } from "./Notas";
import { STATUS_PEDIDO } from "./PedidosCompra";

/** Um pedido de compra: itens pedidos, quanto já chegou e as notas que deram baixa nele. */
export default function PedidoCompra() {
  const { id } = useParams();
  const [pedido, setPedido] = useState<Pedido | null>(null);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [cancelando, setCancelando] = useState(false);

  useEffect(() => {
    api<Pedido>(`/compras/pedidos/${id}`)
      .then(setPedido)
      .catch((e) => setErro(mensagem(e)));
  }, [id]);

  async function acao(caminho: "enviado" | "cancelar") {
    setErro("");
    setOk("");
    try {
      setPedido(await api<Pedido>(`/compras/pedidos/${id}/${caminho}`, { corpo: {} }));
      setOk(caminho === "enviado" ? "Marcado como enviado. Quando a nota chegar, ela já vem ligada a este pedido." : "Pedido cancelado.");
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setCancelando(false);
    }
  }

  async function copiar() {
    if (!pedido) return;
    try {
      await navigator.clipboard.writeText(pedido.texto);
      setOk("Texto do pedido copiado.");
    } catch {
      setErro("Não deu para copiar. Selecione o texto abaixo e copie.");
    }
  }

  if (!pedido) return erro ? <p className="erro">{erro}</p> : <p>Carregando...</p>;

  const aberto = ["aberto", "enviado", "parcial"].includes(pedido.status);
  const nadaChegou = pedido.itens.every((i) => Number(i.recebido) === 0);
  const situacao = STATUS_PEDIDO[pedido.status];

  return (
    <div className="pagina">
      <p className="sobretitulo">
        <Link to="/compras/pedidos">Pedidos de compra</Link>
      </p>
      <div className="pagina-titulo">
        <div>
          <h1>
            Pedido nº {pedido.numero} <span className={situacao.classe}>{situacao.rotulo}</span>
          </h1>
          <p className="vazio">
            {pedido.fornecedor_nome} · feito em {data(pedido.criado_em)}
            {pedido.criado_por && ` por ${pedido.criado_por}`} · para {pedido.loja_nome}
            {pedido.enviado_em && ` · enviado em ${data(pedido.enviado_em)}`}
          </p>
        </div>
        <div className="acoes">
          {aberto && nadaChegou && (
            <button type="button" className="botao-secundario" onClick={() => setCancelando(true)}>
              Cancelar pedido
            </button>
          )}
          {pedido.status === "aberto" && (
            <button type="button" className="botao" onClick={() => void acao("enviado")}>
              Marcar como enviado
            </button>
          )}
        </div>
      </div>

      {cancelando && (
        <p className="aviso-conferencia">
          Cancelar o pedido nº {pedido.numero}? As notas que ainda não foram conferidas deixam de apontar para ele.{" "}
          <button type="button" className="botao-pequeno" onClick={() => void acao("cancelar")}>
            Sim, cancelar
          </button>{" "}
          <button type="button" className="botao-pequeno" onClick={() => setCancelando(false)}>
            Não
          </button>
        </p>
      )}
      {erro && <p className="erro">{erro}</p>}
      {ok && <p className="ok">{ok}</p>}

      <section className="cartao espaco-acima">
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Produto</th>
                <th className="num">Pedido</th>
                <th className="num">Chegou</th>
                <th className="num">Falta</th>
                <th className="num">Custo estimado</th>
              </tr>
            </thead>
            <tbody>
              {pedido.itens.map((i) => {
                const falta = Number(i.falta_receber);
                return (
                  <tr key={i.produto_id}>
                    <td>
                      {i.nome}
                      {i.ean && (
                        <>
                          <br />
                          <small>{i.ean}</small>
                        </>
                      )}
                    </td>
                    <td className="num">{quantidade(i.quantidade)}</td>
                    <td className="num">{quantidade(i.recebido)}</td>
                    <td className="num">
                      {falta > 0 && pedido.status !== "cancelado" ? (
                        <strong className="falta-receber">{quantidade(falta)}</strong>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="num">{i.custo_estimado ? reais(i.custo_estimado) : "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <dl className="dados">
          <dt>Total estimado</dt>
          <dd>
            <strong>{reais(pedido.total_estimado)}</strong>
          </dd>
          {pedido.observacao && (
            <>
              <dt>Observação</dt>
              <dd>{pedido.observacao}</dd>
            </>
          )}
        </dl>
      </section>

      <div className="grade-pedido espaco-acima">
        <section className="cartao">
          <div className="cartao-cabecalho">
            <h2>Mensagem para o fornecedor</h2>
          </div>
          <pre className="texto-pedido">{pedido.texto}</pre>
          <div className="acoes">
            <button type="button" className="botao-pequeno" onClick={() => void copiar()}>
              Copiar texto
            </button>
            {pedido.whatsapp && (
              <a
                className="botao-pequeno-link"
                href={`https://wa.me/${pedido.whatsapp}?text=${encodeURIComponent(pedido.texto)}`}
                target="_blank"
                rel="noreferrer"
              >
                WhatsApp
              </a>
            )}
            {pedido.email && (
              <a
                className="botao-pequeno-link"
                href={`mailto:${pedido.email}?subject=${encodeURIComponent(`Pedido de compra nº ${pedido.numero}`)}&body=${encodeURIComponent(pedido.texto)}`}
              >
                E-mail
              </a>
            )}
          </div>
        </section>

        <section className="cartao">
          <div className="cartao-cabecalho">
            <h2>Notas deste pedido</h2>
          </div>
          {pedido.notas.length === 0 ? (
            <p className="lista-vazia">
              Nenhuma nota ainda. Quando importar a nota deste fornecedor em Notas de entrada, ela é ligada aqui sozinha.
            </p>
          ) : (
            <ul className="lista-notas-pedido">
              {pedido.notas.map((n) => (
                <li key={n.id}>
                  <Link to={`/compras/notas/${n.id}`}>Nota {n.numero}</Link> · {data(n.emitida_em)} · {reais(n.valor_total)}{" "}
                  <span className={STATUS_NOTA[n.status].classe}>{STATUS_NOTA[n.status].rotulo}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

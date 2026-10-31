import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Devolucao, Loja } from "../../api/tipos";
import { data, quantidade as fmtQtd, reais } from "../../formato";
import { textoPontos } from "./calculo";

/** Comprovante da devolução, com o vale-troca destacado para o cliente guardar. */
export default function ComprovanteDevolucao() {
  const { id } = useParams();
  const [devolucao, setDevolucao] = useState<Devolucao | null>(null);
  const [loja, setLoja] = useState<Loja | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Devolucao>(`/devolucoes/${id}`)
      .then(async (d) => {
        setDevolucao(d);
        const lojas = await api<Loja[]>("/lojas");
        setLoja(lojas.find((l) => l.id === d.loja_id) ?? null);
      })
      .catch((e) => setErro(mensagem(e)));
  }, [id]);

  if (erro) return <p className="erro declaracao">{erro}</p>;
  if (!devolucao || !loja) return <p className="declaracao">Carregando...</p>;

  const d = devolucao;
  const quando = new Date(d.criado_em);
  const endereco = [loja.endereco, loja.bairro, loja.cidade && `${loja.cidade}/${loja.uf}`].filter(Boolean).join(", ");

  return (
    <div className="declaracao">
      <div className="nao-imprimir declaracao-topo">
        <button type="button" className="botao" onClick={() => window.print()}>
          Imprimir
        </button>
        <small>Entregue uma via ao cliente. Ele precisa do código para usar o vale.</small>
      </div>

      <header className="declaracao-cabecalho">
        <div>
          <strong>{loja.nome_fantasia}</strong>
          <span>{loja.razao_social}</span>
          <span>CNPJ {loja.cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5")}</span>
          {endereco && <span>{endereco}</span>}
          {loja.telefone && <span>Telefone {loja.telefone}</span>}
        </div>
        <div className="declaracao-numero">
          <span>Devolução nº {String(d.numero).padStart(6, "0")}</span>
          <span>
            {quando.toLocaleDateString("pt-BR")} às {quando.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          </span>
          <span>Venda nº {d.venda_numero}</span>
        </div>
      </header>

      <h1>{d.vale ? "Vale-troca" : "Comprovante de devolução"}</h1>

      {d.vale && (
        <section className="vale-destaque">
          <span>Código</span>
          <strong className="codigo-vale">
            {d.vale.codigo.slice(0, 4)} {d.vale.codigo.slice(4)}
          </strong>
          <span>
            Valor <b>{reais(d.vale.valor)}</b> · válido até <b>{data(d.vale.validade)}</b>
            {d.vale.cliente_nome && <> · {d.vale.cliente_nome}</>}
          </span>
        </section>
      )}

      <section>
        <h2>Itens devolvidos</h2>
        <table className="declaracao-tabela">
          <tbody>
            {d.itens.map((i) => (
              <tr key={i.venda_item_id}>
                <th>
                  {fmtQtd(i.quantidade)}x {i.descricao}
                </th>
                <td>{reais(i.valor)}</td>
              </tr>
            ))}
            <tr>
              <th>Total</th>
              <td>{reais(d.valor_total)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <p>
        <strong>Motivo:</strong> {d.motivo}
      </p>
      <p>
        <strong>Como recebeu:</strong>{" "}
        {d.vale ? "vale-troca para usar em outra compra nesta farmácia" : `${reais(d.valor_total)} em dinheiro`}
      </p>

      {(d.pontos ?? 0) !== 0 && <p>{textoPontos(d.pontos ?? 0)}</p>}

      <p className="declaracao-legal">
        {d.vale
          ? "Apresente este código no caixa para usar o crédito, de uma vez ou em várias compras, até a data de validade. O vale não pode ser trocado por dinheiro."
          : "O cliente declara que recebeu o valor acima em dinheiro."}{" "}
        Atendido por {d.usuario}.
      </p>

      <div className="declaracao-assinaturas">
        <div>
          <span className="linha-assinatura" />
          <strong>{d.usuario}</strong>
          <span>Pela farmácia</span>
        </div>
        <div>
          <span className="linha-assinatura" />
          <strong>Cliente</strong>
          <span>Recebi o {d.vale ? "vale-troca" : "valor"}</span>
        </div>
      </div>
    </div>
  );
}

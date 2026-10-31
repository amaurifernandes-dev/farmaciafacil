import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { LojaPublica, PedidoPublico, StatusPedido } from "../../api/tipos";
import PixQrCode from "../../components/PixQrCode";
import { quantidade, reais } from "../../formato";
import Icone from "../../components/Icone";
import { CabecalhoLoja, whatsappDaLoja } from "./LojaOnline";

const PASSOS: { status: StatusPedido; nome: string; texto: (entrega: boolean) => string }[] = [
  { status: "novo", nome: "Recebido", texto: () => "A farmácia já recebeu e vai conferir o pedido." },
  { status: "separando", nome: "Separando", texto: () => "Estamos separando os produtos." },
  {
    status: "pronto",
    nome: "Pronto",
    texto: (entrega) => (entrega ? "Saindo para entrega." : "Pode vir buscar no balcão."),
  },
  { status: "entregue", nome: "Entregue", texto: () => "Pedido entregue. Obrigado!" },
];

function passo(status: StatusPedido): number {
  if (status === "saiu") return 2;
  return PASSOS.findIndex((p) => p.status === status);
}

export default function AcompanharPedido() {
  const { endereco = "", codigo = "" } = useParams();
  const [loja, setLoja] = useState<LojaPublica | null>(null);
  const [pedido, setPedido] = useState<PedidoPublico | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<LojaPublica>(`/loja/${endereco}`).then(setLoja).catch(() => setLoja(null));
  }, [endereco]);

  useEffect(() => {
    function carregar() {
      api<PedidoPublico>(`/loja/${endereco}/pedidos/${codigo}`)
        .then((p) => {
          setPedido(p);
          setErro("");
        })
        .catch((e) => setErro(mensagem(e)));
    }
    carregar();
    // A página fica aberta no celular: atualiza sozinha.
    const intervalo = setInterval(carregar, 30000);
    return () => clearInterval(intervalo);
  }, [endereco, codigo]);

  const atual = pedido ? passo(pedido.status) : -1;
  const whatsapp = loja && pedido
    ? whatsappDaLoja(loja.whatsapp, `Olá! Fiz o pedido nº ${pedido.numero} pela loja online.`)
    : null;

  return (
    <div className="vitrine">
      {loja && <CabecalhoLoja loja={loja} endereco={endereco} />}
      <main className="vitrine-largura vitrine-acompanhar">
        {erro && <p className="erro">{erro}</p>}
        {pedido && (
          <>
            <h1>Pedido nº {pedido.numero}</h1>
            {pedido.status === "cancelado" ? (
              <p className="erro">
                Este pedido foi cancelado{pedido.motivo_cancelamento ? `: ${pedido.motivo_cancelamento}` : "."}
              </p>
            ) : (
              <>
                <ol className="vitrine-passos">
                  {PASSOS.map((p, i) => (
                    <li key={p.status} className={i < atual ? "feito" : i === atual ? "atual" : ""}>
                      <span>{i + 1}</span>
                      {p.status === "pronto" && pedido.entrega ? "A caminho" : p.nome}
                    </li>
                  ))}
                </ol>
                <p className="vitrine-recado">{PASSOS[atual]?.texto(pedido.entrega)}</p>
              </>
            )}

            {pedido.pix_copia_e_cola && <PixQrCode codigo={pedido.pix_copia_e_cola} valor={reais(pedido.total)} />}
            {pedido.pix_pago && (
              <div className="vitrine-cartao vitrine-pix-pago">
                <Icone nome="entrada" /> Pix recebido pela farmácia. Obrigado!
              </div>
            )}

            <div className="vitrine-cartao">
              <ul className="vitrine-itens">
                {pedido.itens.map((i) => (
                  <li key={i.produto_id}>
                    <span>
                      {quantidade(i.quantidade)}× {i.descricao}
                    </span>
                    <span>{reais(i.total)}</span>
                  </li>
                ))}
                {pedido.entrega && (
                  <li>
                    <span>Entrega</span>
                    <span>{Number(pedido.taxa_entrega) === 0 ? "grátis" : reais(pedido.taxa_entrega)}</span>
                  </li>
                )}
              </ul>
              <p className="vitrine-total">
                Total <strong>{reais(pedido.total)}</strong>
              </p>
              <p className="vazio">
                {pedido.entrega ? "Entrega em casa" : "Retirar na loja"} · pagamento{" "}
                {pedido.forma_pagamento === "pix" ? "por Pix" : pedido.forma_pagamento === "cartao" ? "no cartão" : "em dinheiro"}
                {pedido.troco_para && ` (troco para ${reais(pedido.troco_para)})`}
                {pedido.pix_pago ? " (já pago)" : pedido.pix_copia_e_cola ? " pelo QR Code acima" : " na hora de receber"}
              </p>
            </div>

            <div className="vitrine-acoes">
              {whatsapp && (
                <a className="vitrine-whatsapp" href={whatsapp} target="_blank" rel="noreferrer">
                  Falar com a farmácia
                </a>
              )}
              <Link to={`/loja/${endereco}`}>Voltar para a loja</Link>
            </div>
            <p className="vazio vitrine-letra-miuda">Guarde este link para acompanhar o pedido.</p>
          </>
        )}
      </main>
    </div>
  );
}

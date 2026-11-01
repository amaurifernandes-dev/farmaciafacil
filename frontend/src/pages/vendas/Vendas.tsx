import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { EsteTerminal, PreVenda, Venda } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import { reais } from "../../formato";
import { useModulos } from "../../modulos";
import { ehGerente, useSessao } from "../../sessao";
import { lerEsteTerminal } from "../caixas/Caixas";

const FORMAS: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo",
  convenio: "Convênio",
  popular: "Farmácia Popular",
  vale: "Vale-troca",
};

function dataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Vendas() {
  const { sessao } = useSessao();
  const trocas = useModulos(sessao).ligado("devolucoes");
  const gerente = ehGerente(sessao);
  const [este, setEste] = useState<EsteTerminal | null | undefined>(undefined);
  const [preVendas, setPreVendas] = useState<PreVenda[]>([]);
  const [vendas, setVendas] = useState<Venda[]>([]);
  const [cancelando, setCancelando] = useState<Venda | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    try {
      const [terminal, pre, ultimas] = await Promise.all([
        lerEsteTerminal(),
        api<PreVenda[]>("/pre-vendas"),
        api<Venda[]>("/vendas?por_pagina=30"),
      ]);
      setEste(terminal);
      setPreVendas(pre);
      setVendas(ultimas);
    } catch (e) {
      setErro(mensagem(e));
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function cancelarPreVenda(pre: PreVenda) {
    try {
      await api(`/pre-vendas/${pre.id}/cancelar`, { corpo: {} });
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Vendas / PDV</h1>
          <p className="vazio">Frente de caixa, pré-vendas do balcão e as últimas vendas.</p>
        </div>
        <div className="acoes">
          {gerente && trocas && (
            <Link to="/devolucoes" className="botao-contorno">
              <Icone nome="troca" /> Trocas e devoluções
            </Link>
          )}
          <Link to="/vendas/pre-venda" className="botao-contorno">
            <Icone nome="recibo" /> Nova pré-venda
          </Link>
          {este?.pode_receber && (
            <Link to="/pdv" className="botao">
              <Icone nome="caixa" /> Abrir frente de caixa
            </Link>
          )}
        </div>
      </div>
      {erro && <p className="erro">{erro}</p>}

      {este !== undefined && (
        <section className="cartao este-computador">
          <span className="atalho-icone">
            <Icone nome="monitor" />
          </span>
          <div>
            <p className="sobretitulo">Este computador</p>
            {este ? (
              <>
                <h2>
                  {este.terminal.nome} · {este.loja.nome}
                </h2>
                <p className={este.pode_receber ? "positivo" : "vazio"}>
                  {este.pode_receber ? "Recebe pagamentos e emite o cupom aqui." : este.motivo}
                </p>
              </>
            ) : (
              <>
                <h2>Balcão (sem caixa)</h2>
                <p className="vazio">
                  Monte a pré-venda aqui e o cliente paga no caixa.{" "}
                  {gerente && (
                    <>
                      Para este computador receber pagamentos, registre-o em <Link to="/caixas">Caixas</Link>.
                    </>
                  )}
                </p>
              </>
            )}
          </div>
        </section>
      )}

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>Pré-vendas aguardando o caixa</h2>
          <small>{preVendas.length} aberta(s)</small>
        </div>
        {preVendas.length === 0 ? (
          <p className="lista-vazia">Nenhuma pré-venda aguardando.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nº</th>
                  <th>Itens</th>
                  <th>Atendente</th>
                  <th>Hora</th>
                  <th className="num">Total</th>
                  <th>NFC-e</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {preVendas.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.numero}</strong>
                    </td>
                    <td>{p.itens.map((i) => `${Number(i.quantidade)}x ${i.descricao}`).join(", ")}</td>
                    <td>{p.vendedor}</td>
                    <td>{dataHora(p.criado_em)}</td>
                    <td className="num">{reais(p.total)}</td>
                    <td className="num">
                      <button type="button" className="botao-pequeno" onClick={() => cancelarPreVenda(p)}>
                        Cancelar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="nota">No PDV, aperte F7 e digite o número da pré-venda para receber.</p>
      </section>

      <section className="cartao espaco-acima">
        <h2>Últimas vendas</h2>
        {vendas.length === 0 ? (
          <p className="lista-vazia">Nenhuma venda ainda.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nº</th>
                  <th>Data</th>
                  <th>Itens</th>
                  <th>Pagamento</th>
                  <th className="num">Total</th>
                  <th>NFC-e</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {vendas.map((v) => (
                  <tr key={v.id} className={v.status === "cancelada" ? "inativo" : ""}>
                    <td>
                      <strong>{v.numero}</strong>
                    </td>
                    <td>{dataHora(v.finalizada_em)}</td>
                    <td>{v.itens.length} item(ns)</td>
                    <td>{v.pagamentos.map((p) => FORMAS[p.forma]).join(" + ")}</td>
                    <td className="num">{reais(v.total)}</td>
                    <td>
                      <SituacaoNota venda={v} aoMudar={carregar} />
                    </td>
                    <td className="num">
                      {v.status === "cancelada" ? (
                        <span className="etiqueta erro-etiqueta" title={v.motivo_cancelamento ?? ""}>
                          Cancelada
                        </span>
                      ) : (
                        gerente && (
                          <span className="acoes-tabela">
                            {trocas && (
                              <Link to={`/devolucoes?venda=${v.numero}`} className="botao-pequeno" title="Devolver itens desta venda">
                                Trocar
                              </Link>
                            )}
                            <button type="button" className="botao-pequeno" onClick={() => setCancelando(v)}>
                              Cancelar
                            </button>
                          </span>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {cancelando && (
        <CancelarVenda
          venda={cancelando}
          aoFechar={() => {
            setCancelando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}

function SituacaoNota({ venda, aoMudar }: { venda: Venda; aoMudar: () => void }) {
  const [enviando, setEnviando] = useState(false);
  const [falha, setFalha] = useState("");
  const nota = venda.nota;

  async function tentar(caminho: string, metodo?: "GET") {
    setEnviando(true);
    setFalha("");
    try {
      await api(caminho, metodo ? undefined : { corpo: {} });
      aoMudar();
    } catch (e) {
      setFalha(mensagem(e));
    } finally {
      setEnviando(false);
    }
  }

  if (nota?.status === "autorizada" || nota?.status === "cancelada") {
    const texto = `${nota.status === "cancelada" ? "Cancelada" : "Nº"} ${nota.numero}`;
    return nota.url_danfe ? (
      <a href={nota.url_danfe} target="_blank" rel="noreferrer">
        {texto}
      </a>
    ) : (
      <span>{texto}</span>
    );
  }
  if (venda.status === "cancelada") return <span className="vazio">—</span>;
  if (nota?.status === "processando") {
    return (
      <>
        <button
          type="button"
          className="botao-pequeno"
          disabled={enviando}
          onClick={() => tentar(`/vendas/${venda.id}/nfce?atualizar=true`, "GET")}
        >
          Consultar
        </button>
        {falha && <small className="erro">{falha}</small>}
      </>
    );
  }
  return (
    <span title={nota?.mensagem ?? "Nota não emitida"}>
      {nota && <span className="etiqueta erro-etiqueta">{nota.status === "rejeitada" ? "Rejeitada" : "Erro"}</span>}{" "}
      <button
        type="button"
        className="botao-pequeno"
        disabled={enviando}
        onClick={() => tentar(`/vendas/${venda.id}/nfce`)}
      >
        {nota ? "Reenviar" : "Emitir"}
      </button>
      {falha && <small className="erro">{falha}</small>}
    </span>
  );
}

function CancelarVenda({ venda, aoFechar }: { venda: Venda; aoFechar: () => void }) {
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");
  // A SEFAZ exige justificativa de pelo menos 15 caracteres.
  const temNota = venda.nota?.status === "autorizada";

  async function cancelar() {
    try {
      await api(`/vendas/${venda.id}/cancelar`, { corpo: { motivo } });
      aoFechar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo={`Cancelar venda nº ${venda.numero}`} aoFechar={aoFechar}>
      <form
        className="campos"
        onSubmit={(e) => {
          e.preventDefault();
          cancelar();
        }}
      >
        <p className="largo">
          Total de {reais(venda.total)}. Os produtos voltam para o estoque, nos mesmos lotes.
          {temNota && " A NFC-e também é cancelada na SEFAZ (em geral só até 30 minutos depois da emissão)."}
        </p>
        <label className="largo">
          Motivo
          <input
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            required
            minLength={temNota ? 15 : 3}
            autoFocus
          />
        </label>
        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit" className="perigo">
            Cancelar venda
          </button>
        </div>
      </form>
    </Janela>
  );
}

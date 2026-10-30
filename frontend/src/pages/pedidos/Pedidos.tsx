import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { api, mensagem } from "../../api/cliente";
import type { FormaPedido, ListaPedidos, Loja, PaginaProdutos, Pedido, Produto, StatusPedido } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";

const SITUACOES = [
  { valor: "abertos", nome: "Em andamento" },
  { valor: "novo", nome: "Novos" },
  { valor: "separando", nome: "Separando" },
  { valor: "pronto", nome: "Prontos para retirar" },
  { valor: "saiu", nome: "Saíram para entrega" },
  { valor: "entregue", nome: "Entregues" },
  { valor: "cancelado", nome: "Cancelados" },
  { valor: "todos", nome: "Todos" },
];

const STATUS: Record<StatusPedido, { nome: string; classe: string }> = {
  novo: { nome: "Novo", classe: "etiqueta etiqueta-promocao" },
  separando: { nome: "Separando", classe: "etiqueta" },
  pronto: { nome: "Pronto para retirar", classe: "etiqueta ok" },
  saiu: { nome: "Saiu para entrega", classe: "etiqueta ok" },
  entregue: { nome: "Entregue", classe: "etiqueta etiqueta-neutra" },
  cancelado: { nome: "Cancelado", classe: "etiqueta etiqueta-neutra" },
};

const CANAIS: Record<Pedido["canal"], string> = { site: "Loja online", whatsapp: "WhatsApp", telefone: "Telefone" };
const FORMAS: Record<FormaPedido, string> = { pix: "Pix", cartao: "Cartão", dinheiro: "Dinheiro" };

function quando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Mensagem pronta para o cliente, conforme o andamento do pedido. */
function linkAviso(pedido: Pedido, farmacia: string): string | null {
  let numero = pedido.telefone.replace(/\D/g, "");
  if (numero.length < 10) return null;
  if (numero.length <= 11) numero = `55${numero}`;
  const ola = `Olá, ${pedido.nome.split(" ")[0]}! Aqui é da ${farmacia}.`;
  const textos: Partial<Record<StatusPedido, string>> = {
    novo: `${ola} Recebemos seu pedido nº ${pedido.numero} (${reais(pedido.total)}). Já vamos separar.`,
    separando: `${ola} Seu pedido nº ${pedido.numero} (${reais(pedido.total)}) está sendo separado.`,
    pronto: `${ola} Seu pedido nº ${pedido.numero} está pronto. Pode vir buscar no balcão.`,
    saiu: `${ola} Seu pedido nº ${pedido.numero} saiu para entrega.`,
  };
  const texto = textos[pedido.status];
  return texto ? `https://wa.me/${numero}?text=${encodeURIComponent(texto)}` : null;
}

export default function Pedidos() {
  const lojas = useLojas();
  const [situacao, setSituacao] = useState("abertos");
  const [lojaId, setLojaId] = useState("");
  const [lista, setLista] = useState<ListaPedidos | null>(null);
  const [anotando, setAnotando] = useState(false);
  const [cancelando, setCancelando] = useState<Pedido | null>(null);
  const [erro, setErro] = useState("");
  const farmacia = lojas.find((l) => l.matriz)?.nome_fantasia ?? "farmácia";

  function carregar() {
    const params = new URLSearchParams({ situacao });
    if (lojaId) params.set("loja_id", lojaId);
    api<ListaPedidos>(`/pedidos?${params}`)
      .then((r) => {
        setLista(r);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(() => {
    carregar();
    // Pedido do site chega a qualquer hora: confere de minuto em minuto.
    const intervalo = setInterval(carregar, 60000);
    return () => clearInterval(intervalo);
  }, [situacao, lojaId]);

  async function acao(pedido: Pedido, qual: string, corpo: object = {}) {
    try {
      await api(`/pedidos/${pedido.id}/${qual}`, { corpo });
      carregar();
      return true;
    } catch (e) {
      setErro(mensagem(e));
      return false;
    }
  }

  const resumo = lista?.resumo;

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Vendas</p>
          <h1>Pedidos</h1>
          <p className="vazio">
            Pedidos da loja online, do WhatsApp e do telefone. Ao aceitar, o pedido vira pré-venda: separe os produtos e
            o caixa recebe com F7 quando o cliente pagar.
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setAnotando(true)}>
          <Icone nome="mais" /> Anotar pedido
        </button>
      </div>

      {resumo && (
        <div className="indicadores indicadores-financeiro">
          <Filtro titulo="Novos" valor={String(resumo.novo)} marcado={situacao === "novo"} destaque={resumo.novo > 0}
            aoClicar={() => setSituacao("novo")}>esperando a farmácia aceitar</Filtro>
          <Filtro titulo="Separando" valor={String(resumo.separando)} marcado={situacao === "separando"}
            aoClicar={() => setSituacao("separando")}>já viraram pré-venda</Filtro>
          <Filtro titulo="Prontos ou a caminho" valor={String(resumo.pronto + resumo.saiu)}
            marcado={situacao === "abertos"} aoClicar={() => setSituacao("abertos")}>
            {resumo.pronto} para retirar · {resumo.saiu} na entrega
          </Filtro>
          <Filtro titulo="Entregues hoje" valor={reais(resumo.total_hoje)} marcado={situacao === "entregue"}
            aoClicar={() => setSituacao("entregue")}>{resumo.entregues_hoje} pedido(s)</Filtro>
        </div>
      )}

      <div className="barra">
        <select value={situacao} onChange={(e) => setSituacao(e.target.value)}>
          {SITUACOES.map((s) => (
            <option key={s.valor} value={s.valor}>
              {s.nome}
            </option>
          ))}
        </select>
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Todas as lojas" />
      </div>
      {erro && <p className="erro">{erro}</p>}

      <div className="pedidos-lista">
        {(lista?.pedidos ?? []).map((p) => {
          const aviso = linkAviso(p, farmacia);
          return (
            <article key={p.id} className={`cartao pedido pedido-${p.status}`}>
              <header>
                <div>
                  <strong>Pedido nº {p.numero}</strong> <span className={STATUS[p.status].classe}>{STATUS[p.status].nome}</span>
                  <small className="linha-detalhe">
                    {CANAIS[p.canal]} · {quando(p.criado_em)}
                    {lojas.length > 1 && ` · ${p.loja_nome}`}
                    {p.pre_venda_numero && ` · pré-venda nº ${p.pre_venda_numero}${p.pago ? " (paga)" : ""}`}
                  </small>
                </div>
                <strong className="pedido-total">{reais(p.total)}</strong>
              </header>
              <div className="pedido-corpo">
                <div>
                  <p>
                    <strong>{p.nome}</strong> · {p.telefone}
                  </p>
                  <p>
                    {p.entrega ? <>Entregar em: {p.endereco}</> : "Retira na loja"}
                  </p>
                  <p className="vazio">
                    {FORMAS[p.forma_pagamento]}
                    {p.troco_para && ` · troco para ${reais(p.troco_para)}`}
                    {p.observacao && ` · "${p.observacao}"`}
                  </p>
                  {p.motivo_cancelamento && <p className="erro">Cancelado: {p.motivo_cancelamento}</p>}
                </div>
                <ul className="pedido-itens">
                  {p.itens.map((i) => (
                    <li key={i.produto_id}>
                      <span>
                        {quantidade(i.quantidade)}× {i.descricao}
                      </span>
                      <span>{reais(i.total)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <footer className="acoes-linha">
                {p.status === "novo" && (
                  <button type="button" className="botao-pequeno botao-cheio" onClick={() => acao(p, "confirmar")}>
                    Aceitar e separar
                  </button>
                )}
                {p.status === "separando" && !p.entrega && (
                  <button type="button" className="botao-pequeno botao-cheio" onClick={() => acao(p, "pronto")}>
                    Pronto para retirar
                  </button>
                )}
                {(p.status === "separando" || p.status === "pronto") && p.entrega && (
                  <button type="button" className="botao-pequeno botao-cheio" onClick={() => acao(p, "saiu")}>
                    Saiu para entrega
                  </button>
                )}
                {aviso && (
                  <a className="botao-pequeno botao-whatsapp" href={aviso} target="_blank" rel="noreferrer">
                    Avisar no WhatsApp
                  </a>
                )}
                {["separando", "pronto", "saiu"].includes(p.status) && (
                  <button type="button" className="botao-pequeno" onClick={() => acao(p, "entregue")}
                    title="Use quando o pagamento não passou pelo caixa. Pela pré-venda, fica entregue sozinho.">
                    Entregue
                  </button>
                )}
                {!["entregue", "cancelado"].includes(p.status) && (
                  <button type="button" className="botao-pequeno" onClick={() => setCancelando(p)}>
                    Cancelar
                  </button>
                )}
              </footer>
            </article>
          );
        })}
      </div>
      {lista && lista.pedidos.length === 0 && (
        <p className="lista-vazia cartao">
          {situacao === "abertos" ? "Nenhum pedido em andamento." : "Nenhum pedido aqui."}
        </p>
      )}

      {anotando && (
        <FormularioPedido
          lojas={lojas}
          aoFechar={() => setAnotando(false)}
          aoSalvar={() => {
            setAnotando(false);
            setSituacao("abertos");
            carregar();
          }}
        />
      )}
      {cancelando && (
        <CancelarPedido
          pedido={cancelando}
          aoFechar={() => setCancelando(null)}
          aoConfirmar={async (motivo) => {
            if (await acao(cancelando, "cancelar", { motivo })) setCancelando(null);
          }}
        />
      )}
    </div>
  );
}

function Filtro({ titulo, valor, marcado, destaque, aoClicar, children }: {
  titulo: string;
  valor: string;
  marcado: boolean;
  destaque?: boolean;
  aoClicar: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" className={`cartao indicador ${marcado ? "indicador-marcado" : ""}`} onClick={aoClicar}>
      <small>{titulo}</small>
      <strong className={destaque ? "texto-ok" : ""}>{valor}</strong>
      <small>{children}</small>
    </button>
  );
}

function CancelarPedido({ pedido, aoFechar, aoConfirmar }: {
  pedido: Pedido;
  aoFechar: () => void;
  aoConfirmar: (motivo: string) => void;
}) {
  const [motivo, setMotivo] = useState("");
  return (
    <Janela titulo={`Cancelar o pedido nº ${pedido.numero}`} aoFechar={aoFechar}>
      <form
        className="campos"
        onSubmit={(e) => {
          e.preventDefault();
          aoConfirmar(motivo.trim());
        }}
      >
        <label className="largo">
          Motivo (o cliente vê na página do pedido)
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} required minLength={3} maxLength={200}
            placeholder="ex.: Cliente desistiu" />
        </label>
        {pedido.pre_venda_numero && (
          <p className="vazio largo">A pré-venda nº {pedido.pre_venda_numero} sai da fila do caixa.</p>
        )}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit">Cancelar pedido</button>
        </div>
      </form>
    </Janela>
  );
}

interface ItemEscolhido {
  id: string;
  nome: string;
  preco: string;
  quantidade: string;
}

function FormularioPedido({ lojas, aoFechar, aoSalvar }: {
  lojas: Loja[];
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [canal, setCanal] = useState<"whatsapp" | "telefone">("whatsapp");
  const [busca, setBusca] = useState("");
  const [encontrados, setEncontrados] = useState<Produto[]>([]);
  const [itens, setItens] = useState<ItemEscolhido[]>([]);
  const [nome, setNome] = useState("");
  const [telefone, setTelefone] = useState("");
  const [entrega, setEntrega] = useState(false);
  const [endereco, setEndereco] = useState("");
  const [forma, setForma] = useState<FormaPedido>("pix");
  const [troco, setTroco] = useState("");
  const [observacao, setObservacao] = useState("");
  const [loja, setLoja] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    const termo = busca.trim();
    if (termo.length < 2) return setEncontrados([]);
    const espera = setTimeout(() => {
      api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(termo)}&por_pagina=6`)
        .then((pagina) => setEncontrados(pagina.itens))
        .catch(() => setEncontrados([]));
    }, 250);
    return () => clearTimeout(espera);
  }, [busca]);

  function incluir(produto: Produto) {
    if (!itens.some((i) => i.id === produto.id)) {
      const nomeCompleto = produto.apresentacao ? `${produto.nome} ${produto.apresentacao}` : produto.nome;
      setItens([...itens, { id: produto.id, nome: nomeCompleto, preco: produto.preco_venda, quantidade: "1" }]);
    }
    setBusca("");
    setEncontrados([]);
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (itens.length === 0) return setErro("Inclua pelo menos um produto");
    try {
      await api("/pedidos", {
        corpo: {
          canal,
          itens: itens.map((i) => ({ produto_id: i.id, quantidade: i.quantidade.replace(",", ".") })),
          nome: nome.trim(),
          telefone: telefone.trim(),
          entrega,
          endereco: entrega ? endereco.trim() : null,
          forma_pagamento: forma,
          troco_para: forma === "dinheiro" && troco.trim() ? troco.replace(".", "").replace(",", ".") : null,
          observacao: observacao.trim() || null,
          loja_id: loja || null,
        },
      });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Anotar pedido" aoFechar={aoFechar}>
      <form className="campos" onSubmit={salvar}>
        <label>
          Chegou por
          <select value={canal} onChange={(e) => setCanal(e.target.value as "whatsapp" | "telefone")}>
            <option value="whatsapp">WhatsApp</option>
            <option value="telefone">Telefone</option>
          </select>
        </label>
        {lojas.length > 1 ? (
          <SeletorLoja lojas={lojas} valor={loja} aoMudar={setLoja} todas="Loja da loja online" />
        ) : (
          <span />
        )}
        <div className="largo">
          <label>
            Produtos *
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Digite o nome do produto" />
          </label>
          {encontrados.length > 0 && (
            <ul className="sugestoes">
              {encontrados.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => incluir(p)}>
                    {p.nome} {p.apresentacao} <span>{reais(p.preco_venda)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {itens.length > 0 && (
            <ul className="escolhidos">
              {itens.map((i) => (
                <li key={i.id}>
                  <span>
                    {i.nome}
                    <small>{reais(i.preco)} cada</small>
                  </span>
                  <input
                    className="quantidade"
                    value={i.quantidade}
                    inputMode="decimal"
                    aria-label="Quantidade"
                    onChange={(e) => setItens(itens.map((x) => (x.id === i.id ? { ...x, quantidade: e.target.value } : x)))}
                  />
                  <button type="button" className="botao-icone" title="Tirar"
                    onClick={() => setItens(itens.filter((x) => x.id !== i.id))}>
                    <Icone nome="x" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <label>
          Nome do cliente *
          <input value={nome} onChange={(e) => setNome(e.target.value)} required minLength={2} />
        </label>
        <label>
          Telefone / WhatsApp *
          <input value={telefone} onChange={(e) => setTelefone(e.target.value)} required inputMode="tel" />
        </label>
        <label className="checkbox caixa-marcacao largo">
          <input type="checkbox" checked={entrega} onChange={(e) => setEntrega(e.target.checked)} />
          <span>Entregar em casa</span>
        </label>
        {entrega && (
          <label className="largo">
            Endereço *
            <input value={endereco} onChange={(e) => setEndereco(e.target.value)} required />
          </label>
        )}
        <label>
          Pagamento
          <select value={forma} onChange={(e) => setForma(e.target.value as FormaPedido)}>
            <option value="pix">Pix</option>
            <option value="cartao">Cartão</option>
            <option value="dinheiro">Dinheiro</option>
          </select>
        </label>
        {forma === "dinheiro" ? (
          <label>
            Troco para
            <input value={troco} onChange={(e) => setTroco(e.target.value)} inputMode="decimal" />
          </label>
        ) : (
          <span />
        )}
        <label className="largo">
          Observação
          <input value={observacao} onChange={(e) => setObservacao(e.target.value)} maxLength={300} />
        </label>
        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit">Anotar pedido</button>
        </div>
      </form>
    </Janela>
  );
}

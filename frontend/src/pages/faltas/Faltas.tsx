import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Cliente, Falta, ListaFaltas, Loja, PaginaProdutos, Produto, SituacaoFalta } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { quantidade } from "../../formato";
import { useLojas } from "../../lojas";

const SITUACOES: { valor: SituacaoFalta; nome: string }[] = [
  { valor: "encomendas", nome: "Encomendas esperando" },
  { valor: "chegaram", nome: "Chegaram: avisar o cliente" },
  { valor: "avisados", nome: "Avisados, ainda não buscaram" },
  { valor: "faltas", nome: "Faltas anotadas (sem contato)" },
  { valor: "encerradas", nome: "Entregues e canceladas" },
  { valor: "todas", nome: "Todas" },
];

const STATUS: Record<Falta["status"], { nome: string; classe: string }> = {
  registrada: { nome: "Faltou", classe: "etiqueta etiqueta-neutra" },
  aberta: { nome: "Esperando", classe: "etiqueta" },
  avisado: { nome: "Avisado", classe: "etiqueta etiqueta-promocao" },
  entregue: { nome: "Entregue", classe: "etiqueta ok" },
  cancelada: { nome: "Cancelada", classe: "etiqueta etiqueta-neutra" },
};

function quando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Link do WhatsApp com a mensagem pronta. Sem DDI, assume Brasil. */
function linkWhatsApp(falta: Falta, loja: Loja | undefined): string | null {
  let numero = (falta.telefone ?? "").replace(/\D/g, "");
  if (numero.length < 10) return null;
  if (numero.length <= 11) numero = `55${numero}`;
  const ola = falta.nome ? `Olá, ${falta.nome.split(" ")[0]}!` : "Olá!";
  const daonde = loja ? ` Aqui é da ${loja.nome_fantasia}.` : "";
  const texto = `${ola}${daonde} O ${falta.descricao} que você pediu já chegou. Separamos para você, é só vir buscar.`;
  return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
}

export default function Faltas() {
  const lojas = useLojas();
  const [situacao, setSituacao] = useState<SituacaoFalta>("encomendas");
  const [lojaId, setLojaId] = useState("");
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState<ListaFaltas | null>(null);
  const [anotando, setAnotando] = useState(false);
  const [erro, setErro] = useState("");

  function carregar() {
    const params = new URLSearchParams({ situacao });
    if (lojaId) params.set("loja_id", lojaId);
    if (busca.trim()) params.set("busca", busca.trim());
    api<ListaFaltas>(`/faltas?${params}`)
      .then((resposta) => {
        setLista(resposta);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(() => {
    const espera = setTimeout(carregar, busca ? 250 : 0);
    return () => clearTimeout(espera);
  }, [situacao, lojaId, busca]);

  async function acao(falta: Falta, qual: "avisar" | "entregar" | "cancelar") {
    try {
      await api(`/faltas/${falta.id}/${qual}`, { corpo: {} });
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  const resumo = lista?.resumo;
  const variasLojas = lojas.length > 1;

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Vendas</p>
          <h1>Faltas e encomendas</h1>
          <p className="vazio">
            Anote o que o cliente pediu e não tinha. Com nome ou telefone vira encomenda: quando o produto chega, ele
            aparece aqui para avisar. No caixa, é só apertar F1.
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setAnotando(true)}>
          <Icone nome="mais" /> Anotar falta
        </button>
      </div>

      {resumo && (
        <div className="indicadores indicadores-financeiro">
          <Filtro marcado={situacao === "chegaram"} aoClicar={() => setSituacao("chegaram")}
            titulo="Chegaram" valor={resumo.chegaram} destaque={resumo.chegaram > 0}>
            encomendas prontas para avisar
          </Filtro>
          <Filtro marcado={situacao === "encomendas"} aoClicar={() => setSituacao("encomendas")}
            titulo="Esperando" valor={resumo.encomendas}>
            encomendas aguardando o produto
          </Filtro>
          <Filtro marcado={situacao === "avisados"} aoClicar={() => setSituacao("avisados")}
            titulo="Avisados" valor={resumo.avisados}>
            ainda não vieram buscar
          </Filtro>
          <Filtro marcado={situacao === "faltas"} aoClicar={() => setSituacao("faltas")}
            titulo="Faltas em 30 dias" valor={resumo.faltas_30_dias}>
            pedidos que a loja não tinha
          </Filtro>
        </div>
      )}

      {resumo && resumo.mais_pedidos.length > 0 && (
        <div className="cartao mais-pedidos">
          <h2>O que mais faltou nos últimos 30 dias</h2>
          <ol>
            {resumo.mais_pedidos.map((m) => (
              <li key={`${m.produto_id}-${m.descricao}`}>
                <strong>{m.descricao}</strong>
                <small>
                  {m.vezes} pedido(s) · {quantidade(m.quantidade)} un.{!m.produto_id && " · não cadastrado"}
                </small>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="cartao">
        <div className="barra">
          <select value={situacao} onChange={(e) => setSituacao(e.target.value as SituacaoFalta)}>
            {SITUACOES.map((s) => (
              <option key={s.valor} value={s.valor}>
                {s.nome}
              </option>
            ))}
          </select>
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar produto ou cliente" />
          <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Todas as lojas" />
        </div>
        {erro && <p className="erro">{erro}</p>}
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>O que pediram</th>
                <th>Para quem</th>
                <th>Situação</th>
                <th className="num">Tem na loja</th>
                <th>Anotado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(lista?.itens ?? []).map((f) => {
                const whatsapp = f.chegou || f.status === "avisado" ? linkWhatsApp(f, lojas.find((l) => l.id === f.loja_id)) : null;
                const pendente = f.status === "aberta" || f.status === "avisado";
                return (
                  <tr key={f.id} className={f.chegou ? "linha-chegou" : ""}>
                    <td>
                      <strong>{f.descricao}</strong>
                      <small className="linha-detalhe">
                        {quantidade(f.quantidade)} un.{!f.produto_id && " · não cadastrado"}
                        {f.observacao && ` · ${f.observacao}`}
                      </small>
                    </td>
                    <td>
                      {f.encomenda ? (
                        <>
                          {f.nome ?? "-"}
                          {f.telefone && <small className="linha-detalhe">{f.telefone}</small>}
                        </>
                      ) : (
                        <span className="vazio">Ninguém para avisar</span>
                      )}
                    </td>
                    <td>
                      {f.chegou ? (
                        <span className="etiqueta ok">Chegou</span>
                      ) : (
                        <span className={STATUS[f.status].classe}>{STATUS[f.status].nome}</span>
                      )}
                    </td>
                    <td className="num">{f.saldo === null ? "-" : quantidade(f.saldo)}</td>
                    <td>
                      {quando(f.criado_em)}
                      <small className="linha-detalhe">
                        {f.usuario_nome}
                        {f.origem === "pdv" && " · no caixa"}
                        {variasLojas && ` · ${f.loja_nome}`}
                      </small>
                    </td>
                    <td className="num acoes-linha">
                      {whatsapp && (
                        <a className="botao-pequeno botao-whatsapp" href={whatsapp} target="_blank" rel="noreferrer"
                          onClick={() => f.status === "aberta" && acao(f, "avisar")}>
                          Avisar no WhatsApp
                        </a>
                      )}
                      {f.chegou && !whatsapp && (
                        <button type="button" className="botao-pequeno" onClick={() => acao(f, "avisar")}>
                          Já avisei
                        </button>
                      )}
                      {pendente && (
                        <button type="button" className="botao-pequeno" onClick={() => acao(f, "entregar")}>
                          Entregue
                        </button>
                      )}
                      {f.status !== "entregue" && f.status !== "cancelada" && (
                        <button type="button" className="botao-pequeno" onClick={() => acao(f, "cancelar")}>
                          {f.encomenda ? "Desistiu" : "Tirar"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {lista && lista.itens.length === 0 && (
          <p className="lista-vazia">
            {situacao === "chegaram" ? "Nenhuma encomenda chegou ainda." : "Nada por aqui."}
          </p>
        )}
      </div>

      {anotando && (
        <FormularioFalta
          lojas={lojas}
          aoFechar={() => setAnotando(false)}
          aoSalvar={(falta) => {
            setAnotando(false);
            setSituacao(falta.encomenda ? "encomendas" : "faltas");
            carregar();
          }}
        />
      )}
    </div>
  );
}

function Filtro({ titulo, valor, marcado, destaque, aoClicar, children }: {
  titulo: string;
  valor: number;
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

function FormularioFalta({ lojas, aoFechar, aoSalvar }: {
  lojas: Loja[];
  aoFechar: () => void;
  aoSalvar: (falta: Falta) => void;
}) {
  const [busca, setBusca] = useState("");
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [produto, setProduto] = useState<Produto | null>(null);
  const [qtd, setQtd] = useState("1");
  const [buscaCliente, setBuscaCliente] = useState("");
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [nome, setNome] = useState("");
  const [telefone, setTelefone] = useState("");
  const [observacao, setObservacao] = useState("");
  const [loja, setLoja] = useState(lojas.find((l) => l.matriz)?.id ?? "");
  const [erro, setErro] = useState("");

  useEffect(() => {
    const termo = busca.trim();
    if (produto || termo.length < 2) return setProdutos([]);
    const espera = setTimeout(() => {
      api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(termo)}&por_pagina=6`)
        .then((pagina) => setProdutos(pagina.itens))
        .catch(() => setProdutos([]));
    }, 250);
    return () => clearTimeout(espera);
  }, [busca, produto]);

  useEffect(() => {
    const termo = buscaCliente.trim();
    if (cliente || termo.length < 2) return setClientes([]);
    const espera = setTimeout(() => {
      api<{ itens: Cliente[] }>(`/clientes?busca=${encodeURIComponent(termo)}&por_pagina=6`)
        .then((pagina) => setClientes(pagina.itens))
        .catch(() => setClientes([]));
    }, 250);
    return () => clearTimeout(espera);
  }, [buscaCliente, cliente]);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      const falta = await api<Falta>("/faltas", {
        corpo: {
          produto_id: produto?.id ?? null,
          descricao: produto ? null : busca.trim(),
          quantidade: qtd.replace(",", "."),
          cliente_id: cliente?.id ?? null,
          contato_nome: cliente ? null : nome.trim() || null,
          contato_telefone: telefone.trim() || null,
          observacao: observacao.trim() || null,
          loja_id: loja || null,
        },
      });
      aoSalvar(falta);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Anotar falta" aoFechar={aoFechar}>
      <form className="campos" onSubmit={salvar}>
        <div className="largo">
          <label>
            O que o cliente pediu *
            {produto ? (
              <span className="escolhido-unico">
                {produto.nome} {produto.apresentacao}
                <button type="button" className="botao-icone" title="Trocar" onClick={() => setProduto(null)}>
                  <Icone nome="x" />
                </button>
              </span>
            ) : (
              <input value={busca} onChange={(e) => setBusca(e.target.value)} required
                placeholder="Nome do produto. Se não tiver cadastro, escreva como o cliente falou" />
            )}
          </label>
          {produtos.length > 0 && (
            <ul className="sugestoes">
              {produtos.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => setProduto(p)}>
                    {p.nome} {p.apresentacao}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <label>
          Quantidade
          <input value={qtd} onChange={(e) => setQtd(e.target.value)} inputMode="decimal" required />
        </label>
        {lojas.length > 1 && (
          <SeletorLoja lojas={lojas} valor={loja} aoMudar={setLoja} />
        )}

        <div className="largo">
          <label>
            Cliente (opcional, para avisar quando chegar)
            {cliente ? (
              <span className="escolhido-unico">
                {cliente.nome} {cliente.telefone && <small>{cliente.telefone}</small>}
                <button type="button" className="botao-icone" title="Trocar" onClick={() => setCliente(null)}>
                  <Icone nome="x" />
                </button>
              </span>
            ) : (
              <input value={buscaCliente} onChange={(e) => setBuscaCliente(e.target.value)}
                placeholder="Buscar cliente cadastrado por nome, CPF ou telefone" />
            )}
          </label>
          {clientes.length > 0 && (
            <ul className="sugestoes">
              {clientes.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => setCliente(c)}>
                    {c.nome} <span>{c.telefone ?? ""}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {!cliente && (
          <label>
            Ou só o nome
            <input value={nome} onChange={(e) => setNome(e.target.value)} />
          </label>
        )}
        <label>
          Telefone / WhatsApp
          <input value={telefone} onChange={(e) => setTelefone(e.target.value)} inputMode="tel"
            placeholder={cliente?.telefone ? `Usa o do cadastro: ${cliente.telefone}` : "(11) 98888-7777"} />
        </label>
        <label className="largo">
          Observação
          <input value={observacao} onChange={(e) => setObservacao(e.target.value)} placeholder="ex.: precisa da genérica" />
        </label>

        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit">Anotar</button>
        </div>
      </form>
    </Janela>
  );
}

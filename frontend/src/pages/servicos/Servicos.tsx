import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { AtendimentoServico, Cliente, FormaServico, ListaAtendimentos, Servico, TipoServico } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { reais } from "../../formato";
import { useLojas } from "../../lojas";
import { ehGerente, useSessao } from "../../sessao";
import { CAMPOS_RESULTADO, montarResultados, NOMES_FORMA, NOMES_TIPO } from "./campos";

type Aba = "novo" | "atendimentos" | "catalogo";

function abrirDeclaracao(id: string) {
  window.open(`/servicos/declaracao/${id}`, "_blank");
}

/** Serviços farmacêuticos: registrar o atendimento, ver o histórico e ajustar os preços. */
export default function Servicos() {
  const { sessao } = useSessao();
  const [aba, setAba] = useState<Aba>("novo");
  const [servicos, setServicos] = useState<Servico[]>([]);

  function carregarServicos() {
    api<Servico[]>(`/servicos?todos=true`)
      .then(setServicos)
      .catch(() => setServicos([]));
  }
  useEffect(carregarServicos, []);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Atendimento</p>
          <h1>Serviços farmacêuticos</h1>
          <p className="vazio">
            Aferição de pressão, glicemia, temperatura e aplicação de injetáveis, com a declaração impressa para o paciente,
            como pede a RDC 44/2009 da Anvisa.
          </p>
        </div>
      </div>
      <nav className="abas abas-botoes">
        <button type="button" className={aba === "novo" ? "active" : ""} onClick={() => setAba("novo")}>
          Novo atendimento
        </button>
        <button type="button" className={aba === "atendimentos" ? "active" : ""} onClick={() => setAba("atendimentos")}>
          Atendimentos
        </button>
        {ehGerente(sessao) && (
          <button type="button" className={aba === "catalogo" ? "active" : ""} onClick={() => setAba("catalogo")}>
            Serviços e preços
          </button>
        )}
      </nav>
      {aba === "novo" && <NovoAtendimento servicos={servicos.filter((s) => s.ativo)} />}
      {aba === "atendimentos" && <Atendimentos />}
      {aba === "catalogo" && <Catalogo servicos={servicos} aoMudar={carregarServicos} />}
    </div>
  );
}

function NovoAtendimento({ servicos }: { servicos: Servico[] }) {
  const lojas = useLojas();
  const [servico, setServico] = useState<Servico | null>(null);
  const [loja, setLoja] = useState("");
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [buscaCliente, setBuscaCliente] = useState("");
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [nome, setNome] = useState("");
  const [cpf, setCpf] = useState("");
  const [nascimento, setNascimento] = useState("");
  const [valores, setValores] = useState<Record<string, string | boolean>>({});
  const [orientacao, setOrientacao] = useState("");
  const [forma, setForma] = useState<FormaServico>("dinheiro");
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState("");
  const [feito, setFeito] = useState<AtendimentoServico | null>(null);

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

  function escolher(s: Servico) {
    setServico(s);
    setValores({});
    setValor(Number(s.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 }));
    setForma(Number(s.preco) > 0 ? "dinheiro" : "cortesia");
    setErro("");
  }

  function recomecar() {
    setFeito(null);
    setServico(null);
    setCliente(null);
    setBuscaCliente("");
    setNome("");
    setCpf("");
    setNascimento("");
    setValores({});
    setOrientacao("");
  }

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (!servico) return;
    setErro("");
    try {
      const atendimento = await api<AtendimentoServico>("/servicos/atendimentos", {
        corpo: {
          servico_id: servico.id,
          loja_id: loja || null,
          cliente_id: cliente?.id ?? null,
          paciente_nome: cliente ? null : nome.trim() || null,
          paciente_cpf: cliente ? null : cpf.trim() || null,
          paciente_nascimento: cliente ? null : nascimento || null,
          resultados: montarResultados(servico.tipo, valores),
          orientacao: orientacao.trim() || null,
          forma_pagamento: forma,
          valor: forma === "cortesia" ? null : valor.replace(/\./g, "").replace(",", ".") || null,
        },
      });
      setFeito(atendimento);
      window.scrollTo({ top: 0 });
    } catch (falha) {
      setErro(mensagem(falha));
    }
  }

  if (feito) {
    return (
      <div className="cartao cartao-separado servico-feito">
        <p className="sobretitulo">Atendimento nº {feito.numero} registrado</p>
        <h2>
          {feito.servico_nome}: {feito.resultado_texto}
        </h2>
        <p>{feito.paciente_nome}</p>
        {feito.aviso ? (
          <p className={feito.aviso.nivel === "alerta" ? "erro" : "aviso-atencao"}>{feito.aviso.texto}</p>
        ) : (
          feito.tipo !== "injetavel" && feito.tipo !== "outro" && <p className="ok">Dentro da faixa de referência.</p>
        )}
        <div className="acoes-linha">
          <button type="button" className="botao" onClick={() => abrirDeclaracao(feito.id)}>
            <Icone nome="recibo" /> Imprimir declaração
          </button>
          <button type="button" className="botao-pequeno" onClick={recomecar}>
            Novo atendimento
          </button>
        </div>
      </div>
    );
  }

  return (
    <form className="servico-form" onSubmit={salvar}>
      <div className="cartao cartao-separado">
        <h2>1. Qual serviço?</h2>
        <div className="servico-opcoes">
          {servicos.map((s) => (
            <button
              type="button"
              key={s.id}
              className={`servico-opcao ${servico?.id === s.id ? "escolhido" : ""}`}
              onClick={() => escolher(s)}
            >
              <strong>{s.nome}</strong>
              <small>{Number(s.preco) > 0 ? reais(s.preco) : "Sem cobrança"}</small>
            </button>
          ))}
        </div>
      </div>

      {servico && (
        <>
          <div className="cartao cartao-separado"><div className="campos">
            <h2 className="largo">2. Paciente</h2>
            <div className="largo">
              <label>
                Cliente cadastrado
                {cliente ? (
                  <span className="escolhido-unico">
                    {cliente.nome} {cliente.cpf && <small>CPF {cliente.cpf}</small>}
                    <Link to={`/clientes/${cliente.id}`} target="_blank">
                      ver ficha
                    </Link>
                    <button type="button" className="botao-icone" title="Trocar" onClick={() => setCliente(null)}>
                      <Icone nome="x" />
                    </button>
                  </span>
                ) : (
                  <input value={buscaCliente} onChange={(e) => setBuscaCliente(e.target.value)} placeholder="Buscar por nome, CPF ou telefone" />
                )}
              </label>
              {clientes.length > 0 && (
                <ul className="sugestoes">
                  {clientes.map((c) => (
                    <li key={c.id}>
                      <button type="button" onClick={() => setCliente(c)}>
                        {c.nome} <small>{c.cpf ?? c.telefone ?? ""}</small>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {!cliente && (
              <>
                <label>
                  Ou o nome do paciente
                  <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Sem cadastro" />
                </label>
                <label>
                  CPF (opcional)
                  <input value={cpf} onChange={(e) => setCpf(e.target.value)} inputMode="numeric" />
                </label>
                <label>
                  Nascimento (opcional)
                  <input type="date" value={nascimento} onChange={(e) => setNascimento(e.target.value)} />
                </label>
              </>
            )}
            {lojas.length > 1 && <SeletorLoja lojas={lojas} valor={loja} aoMudar={setLoja} />}
          </div>
          </div>

          <div className="cartao cartao-separado"><div className="campos">
            <h2 className="largo">3. Resultado: {NOMES_TIPO[servico.tipo]}</h2>
            {CAMPOS_RESULTADO[servico.tipo].map((campo) =>
              campo.tipo === "check" ? (
                <label key={campo.nome} className="checkbox largo">
                  <input
                    type="checkbox"
                    checked={Boolean(valores[campo.nome])}
                    onChange={(e) => setValores({ ...valores, [campo.nome]: e.target.checked })}
                  />
                  {campo.rotulo}
                </label>
              ) : (
                <label key={campo.nome}>
                  {campo.rotulo}
                  {campo.obrigatorio && " *"}
                  {campo.tipo === "select" ? (
                    <select
                      value={String(valores[campo.nome] ?? campo.opcoes?.[0]?.valor ?? "")}
                      onChange={(e) => setValores({ ...valores, [campo.nome]: e.target.value })}
                    >
                      {campo.opcoes?.map((o) => (
                        <option key={o.valor} value={o.valor}>
                          {o.rotulo}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={campo.tipo === "data" ? "date" : "text"}
                      inputMode={campo.tipo === "numero" ? "decimal" : undefined}
                      required={campo.obrigatorio}
                      value={String(valores[campo.nome] ?? "")}
                      onChange={(e) => setValores({ ...valores, [campo.nome]: e.target.value })}
                    />
                  )}
                  {campo.dica && <small>{campo.dica}</small>}
                </label>
              ),
            )}
            <label className="largo">
              Orientação ao paciente
              <textarea
                rows={3}
                value={orientacao}
                onChange={(e) => setOrientacao(e.target.value)}
                placeholder="Ex.: medir de novo em 7 dias e levar os valores ao médico."
              />
            </label>
          </div>
          </div>

          <div className="cartao cartao-separado"><div className="campos">
            <h2 className="largo">4. Pagamento</h2>
            <label>
              Forma
              <select value={forma} onChange={(e) => setForma(e.target.value as FormaServico)}>
                {(Object.keys(NOMES_FORMA) as FormaServico[]).map((f) => (
                  <option key={f} value={f}>
                    {NOMES_FORMA[f]}
                  </option>
                ))}
              </select>
            </label>
            {forma !== "cortesia" && (
              <label>
                Valor (R$)
                <input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" />
              </label>
            )}
            {forma === "dinheiro" && <p className="nota largo">O dinheiro entra no seu caixa aberto e aparece no fechamento.</p>}
          </div>
          </div>

          {erro && <p className="erro">{erro}</p>}
          <div>
            <button type="submit" className="botao">
              Registrar atendimento
            </button>
          </div>
        </>
      )}
    </form>
  );
}

type Periodo = "este-mes" | "mes-passado" | "30";

function datas(p: Periodo): string {
  const hoje = new Date();
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (p === "mes-passado")
    return `inicio=${iso(new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1))}&fim=${iso(new Date(hoje.getFullYear(), hoje.getMonth(), 0))}`;
  if (p === "30") {
    const inicio = new Date(hoje);
    inicio.setDate(inicio.getDate() - 29);
    return `inicio=${iso(inicio)}&fim=${iso(hoje)}`;
  }
  return `inicio=${iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1))}&fim=${iso(hoje)}`;
}

function Atendimentos() {
  const [periodo, setPeriodo] = useState<Periodo>("este-mes");
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState<ListaAtendimentos | null>(null);
  const [cancelando, setCancelando] = useState<{ id: string; motivo: string } | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  function carregar() {
    api<ListaAtendimentos>(`/servicos/atendimentos?${datas(periodo)}${busca.trim() ? `&busca=${encodeURIComponent(busca.trim())}` : ""}`)
      .then(setLista)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(carregar, [periodo]);

  async function cancelar() {
    if (!cancelando) return;
    try {
      await api(`/servicos/atendimentos/${cancelando.id}/cancelar`, { corpo: { motivo: cancelando.motivo } });
      setCancelando(null);
      setAviso({ tipo: "ok", texto: "Atendimento cancelado." });
      carregar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  return (
    <>
      <form
        className="barra filtros-relatorio"
        onSubmit={(e) => {
          e.preventDefault();
          carregar();
        }}
      >
        <select value={periodo} onChange={(e) => setPeriodo(e.target.value as Periodo)} aria-label="Período">
          <option value="este-mes">Este mês</option>
          <option value="mes-passado">Mês passado</option>
          <option value="30">Últimos 30 dias</option>
        </select>
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Paciente ou CPF" />
        <button type="submit" className="botao-pequeno">
          Buscar
        </button>
      </form>
      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
      {lista && (
        <div className="indicadores indicadores-financeiro">
          <div className="cartao indicador">
            <small>Atendimentos</small>
            <strong>{lista.itens.filter((a) => a.status === "registrado").length}</strong>
            <span>
              {Object.entries(lista.por_servico)
                .map(([n, q]) => `${q} ${n.toLowerCase()}`)
                .join(" · ") || "nenhum no período"}
            </span>
          </div>
          <div className="cartao indicador">
            <small>Recebido</small>
            <strong>{reais(lista.total_recebido)}</strong>
            <span>sem os cancelados</span>
          </div>
          <div className="cartao indicador">
            <small>Fora da faixa</small>
            <strong>{lista.itens.filter((a) => a.status === "registrado" && a.aviso).length}</strong>
            <span>pacientes orientados a procurar o médico</span>
          </div>
        </div>
      )}
      <div className="cartao cartao-separado">
        <table className="tabela">
          <thead>
            <tr>
              <th>Nº</th>
              <th>Quando</th>
              <th>Paciente</th>
              <th>Serviço e resultado</th>
              <th className="num">Valor</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lista?.itens.map((a) => (
              <tr key={a.id} className={a.status === "cancelado" ? "inativo" : ""}>
                <td>{a.numero}</td>
                <td>
                  {new Date(a.criado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                  <span className="livro-detalhe">{a.farmaceutico}</span>
                </td>
                <td>
                  {a.cliente_id ? <Link to={`/clientes/${a.cliente_id}`}>{a.paciente_nome}</Link> : a.paciente_nome}
                </td>
                <td>
                  {a.servico_nome}: <strong>{a.resultado_texto}</strong>
                  {a.aviso && (
                    <span className={`etiqueta ${a.aviso.nivel === "alerta" ? "erro-etiqueta" : "etiqueta-promocao"}`} title={a.aviso.texto}>
                      {a.aviso.nivel === "alerta" ? "Urgente" : "Fora da faixa"}
                    </span>
                  )}
                  {a.status === "cancelado" && <span className="livro-detalhe">Cancelado: {a.motivo_cancelamento}</span>}
                </td>
                <td className="num">
                  {Number(a.valor) > 0 ? reais(a.valor) : "-"}
                  <span className="livro-detalhe">{NOMES_FORMA[a.forma_pagamento].split(" (")[0]}</span>
                </td>
                <td className="acoes-tabela">
                  {cancelando?.id === a.id ? (
                    <span className="cancelar-inline">
                      <input
                        autoFocus
                        placeholder="Motivo"
                        value={cancelando.motivo}
                        onChange={(e) => setCancelando({ ...cancelando, motivo: e.target.value })}
                      />
                      <button type="button" className="botao-pequeno" disabled={cancelando.motivo.trim().length < 3} onClick={cancelar}>
                        Cancelar
                      </button>
                      <button type="button" className="botao-icone" title="Voltar" onClick={() => setCancelando(null)}>
                        <Icone nome="x" />
                      </button>
                    </span>
                  ) : (
                    a.status === "registrado" && (
                      <>
                        <button type="button" className="botao-pequeno" onClick={() => abrirDeclaracao(a.id)}>
                          Declaração
                        </button>
                        <button type="button" className="botao-icone" title="Cancelar atendimento" onClick={() => setCancelando({ id: a.id, motivo: "" })}>
                          <Icone nome="lixo" />
                        </button>
                      </>
                    )
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {lista?.itens.length === 0 && <p className="lista-vazia">Nenhum atendimento no período.</p>}
      </div>
    </>
  );
}

function Catalogo({ servicos, aoMudar }: { servicos: Servico[]; aoMudar: () => void }) {
  const [precos, setPrecos] = useState<Record<string, string>>({});
  const [novo, setNovo] = useState({ nome: "", tipo: "outro" as TipoServico, preco: "" });
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  async function salvar(s: Servico, mudanca: Partial<{ preco: string; ativo: boolean }>) {
    try {
      await api(`/servicos/${s.id}`, { metodo: "PATCH", corpo: mudanca });
      setAviso({ tipo: "ok", texto: `${s.nome} atualizado.` });
      aoMudar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  async function criar(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/servicos", { corpo: { ...novo, preco: novo.preco.replace(",", ".") || "0" } });
      setNovo({ nome: "", tipo: "outro", preco: "" });
      setAviso({ tipo: "ok", texto: "Serviço criado." });
      aoMudar();
    } catch (falha) {
      setAviso({ tipo: "erro", texto: mensagem(falha) });
    }
  }

  return (
    <>
      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
      <div className="cartao cartao-separado">
        <table className="tabela">
          <thead>
            <tr>
              <th>Serviço</th>
              <th>Tipo</th>
              <th className="num">Preço (R$)</th>
              <th>Situação</th>
            </tr>
          </thead>
          <tbody>
            {servicos.map((s) => {
              const preco = precos[s.id] ?? Number(s.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
              return (
                <tr key={s.id} className={s.ativo ? "" : "inativo"}>
                  <td>
                    <strong>{s.nome}</strong>
                  </td>
                  <td>{NOMES_TIPO[s.tipo]}</td>
                  <td className="num">
                    <input
                      className="campo-meta"
                      inputMode="decimal"
                      value={preco}
                      aria-label={`Preço de ${s.nome}`}
                      onChange={(e) => setPrecos({ ...precos, [s.id]: e.target.value })}
                      onBlur={() => {
                        const valor = preco.replace(/\./g, "").replace(",", ".");
                        if (Number(valor) !== Number(s.preco)) void salvar(s, { preco: valor });
                      }}
                    />
                  </td>
                  <td>
                    <button type="button" className="botao-pequeno" onClick={() => salvar(s, { ativo: !s.ativo })}>
                      {s.ativo ? "Desativar" : "Ativar"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="nota">O preço muda quando você sai do campo. Serviço desativado some da tela de atendimento.</p>
      </div>
      <form className="cartao cartao-separado barra filtros-relatorio" onSubmit={criar}>
        <input value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} placeholder="Novo serviço, ex.: Curativo" required minLength={3} />
        <select value={novo.tipo} onChange={(e) => setNovo({ ...novo, tipo: e.target.value as TipoServico })} aria-label="Tipo">
          {(Object.keys(NOMES_TIPO) as TipoServico[]).map((t) => (
            <option key={t} value={t}>
              {NOMES_TIPO[t]}
            </option>
          ))}
        </select>
        <input className="campo-meta" value={novo.preco} onChange={(e) => setNovo({ ...novo, preco: e.target.value })} placeholder="Preço" inputMode="decimal" />
        <button type="submit" className="botao-pequeno">
          Adicionar
        </button>
      </form>
    </>
  );
}

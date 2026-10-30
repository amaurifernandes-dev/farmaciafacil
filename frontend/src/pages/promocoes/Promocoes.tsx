import { useEffect, useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { PaginaProdutos, Produto, Promocao, TipoPromocao } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import { data, quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { ehGerente, useSessao } from "../../sessao";

const SITUACOES: Record<Promocao["situacao"], { nome: string; classe: string }> = {
  vigente: { nome: "Valendo", classe: "etiqueta ok" },
  agendada: { nome: "Agendada", classe: "etiqueta" },
  encerrada: { nome: "Encerrada", classe: "etiqueta etiqueta-neutra" },
  pausada: { nome: "Pausada", classe: "etiqueta etiqueta-neutra" },
};

const TIPOS: { valor: TipoPromocao; nome: string; dica: string }[] = [
  { valor: "percentual", nome: "% de desconto", dica: "Ex.: 20% em toda a linha de protetores" },
  { valor: "preco_fixo", nome: "Preço especial", dica: "Ex.: de R$ 8,90 por R$ 6,99" },
  { valor: "leve_pague", nome: "Leve e pague", dica: "Ex.: leve 3, pague 2" },
];

function hojeIso(): string {
  const agora = new Date();
  return new Date(agora.getTime() - agora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function periodo(p: Promocao): string {
  if (!p.fim) return `Desde ${data(p.inicio)}`;
  return `${data(p.inicio)} a ${data(p.fim)}`;
}

export default function Promocoes() {
  const { sessao } = useSessao();
  const podeEditar = ehGerente(sessao);
  const [situacao, setSituacao] = useState("vigente");
  const [promocoes, setPromocoes] = useState<Promocao[] | null>(null);
  const [editando, setEditando] = useState<Promocao | "nova" | null>(null);
  const [erro, setErro] = useState("");

  function carregar() {
    api<Promocao[]>(`/promocoes${situacao ? `?situacao=${situacao}` : ""}`)
      .then((lista) => {
        setPromocoes(lista);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(carregar, [situacao]);

  async function encerrar(promocao: Promocao) {
    try {
      await api(`/promocoes/${promocao.id}/encerrar`, { corpo: {} });
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Vendas</p>
          <h1>Promoções</h1>
          <p className="vazio">
            O caixa aplica sozinho: é só bipar o produto. Se um produto estiver em mais de uma, vale a que der mais
            desconto.
          </p>
        </div>
        {podeEditar && (
          <button type="button" className="botao" onClick={() => setEditando("nova")}>
            <Icone nome="mais" /> Nova promoção
          </button>
        )}
      </div>

      <div className="cartao">
        <div className="barra">
          <select value={situacao} onChange={(e) => setSituacao(e.target.value)}>
            <option value="vigente">Valendo hoje</option>
            <option value="agendada">Agendadas</option>
            <option value="encerrada">Encerradas</option>
            <option value="">Todas</option>
          </select>
        </div>
        {erro && <p className="erro">{erro}</p>}
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Promoção</th>
                <th>Regra</th>
                <th>Produtos</th>
                <th>Período</th>
                <th>Situação</th>
                <th className="num">Resultado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(promocoes ?? []).map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.nome}</strong>
                    {p.so_clientes && <small className="linha-detalhe">Só para cliente identificado</small>}
                  </td>
                  <td>
                    <span className="etiqueta etiqueta-promocao">{p.resumo}</span>
                  </td>
                  <td>
                    {p.produtos.slice(0, 2).map((produto) => (
                      <small key={produto.id} className="linha-produto">
                        {produto.nome}
                        {produto.preco_promocional && (
                          <>
                            {" "}
                            <s>{reais(produto.preco_venda)}</s> {reais(produto.preco_promocional)}
                          </>
                        )}
                      </small>
                    ))}
                    {p.produtos.length > 2 && <small className="linha-detalhe">e mais {p.produtos.length - 2}</small>}
                  </td>
                  <td>{periodo(p)}</td>
                  <td>
                    <span className={SITUACOES[p.situacao].classe}>{SITUACOES[p.situacao].nome}</span>
                  </td>
                  <td className="num">
                    {p.resultado.vendas > 0 ? (
                      <>
                        {reais(p.resultado.faturado)}
                        <small className="linha-detalhe">
                          {p.resultado.vendas} venda(s) · {quantidade(p.resultado.unidades)} un. · −
                          {reais(p.resultado.desconto)}
                        </small>
                      </>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="num acoes-linha">
                    {podeEditar && (
                      <>
                        <button type="button" className="botao-pequeno" onClick={() => setEditando(p)}>
                          Editar
                        </button>
                        {(p.situacao === "vigente" || p.situacao === "agendada") && (
                          <button type="button" className="botao-pequeno" onClick={() => encerrar(p)}>
                            Encerrar
                          </button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {promocoes && promocoes.length === 0 && (
          <p className="lista-vazia">
            {situacao === "vigente" ? "Nenhuma promoção valendo hoje." : "Nenhuma promoção aqui."}
          </p>
        )}
      </div>

      {editando && (
        <FormularioPromocao
          promocao={editando === "nova" ? null : editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}

interface ProdutoEscolhido {
  id: string;
  nome: string;
  preco_venda: string;
}

function FormularioPromocao({
  promocao,
  aoFechar,
  aoSalvar,
}: {
  promocao: Promocao | null;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const lojas = useLojas();
  const [nome, setNome] = useState(promocao?.nome ?? "");
  const [tipo, setTipo] = useState<TipoPromocao>(promocao?.tipo ?? "percentual");
  const [percentual, setPercentual] = useState(promocao?.percentual ? String(Number(promocao.percentual)) : "10");
  const [preco, setPreco] = useState(promocao?.preco?.replace(".", ",") ?? "");
  const [leve, setLeve] = useState(String(promocao?.leve ?? 3));
  const [pague, setPague] = useState(String(promocao?.pague ?? 2));
  const [inicio, setInicio] = useState(promocao?.inicio ?? hojeIso());
  const [fim, setFim] = useState(promocao?.fim ?? "");
  const [loja, setLoja] = useState(promocao?.loja_id ?? "");
  const [soClientes, setSoClientes] = useState(promocao?.so_clientes ?? false);
  const [ativa, setAtiva] = useState(promocao?.ativa ?? true);
  const [produtos, setProdutos] = useState<ProdutoEscolhido[]>(promocao?.produtos ?? []);
  const [busca, setBusca] = useState("");
  const [encontrados, setEncontrados] = useState<Produto[]>([]);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const termo = busca.trim();
    if (termo.length < 2) return setEncontrados([]);
    const espera = setTimeout(() => {
      api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(termo)}&por_pagina=8`)
        .then((pagina) => setEncontrados(pagina.itens))
        .catch(() => setEncontrados([]));
    }, 250);
    return () => clearTimeout(espera);
  }, [busca]);

  function incluir(produto: Produto) {
    if (!produtos.some((p) => p.id === produto.id)) {
      const nomeCompleto = produto.apresentacao ? `${produto.nome} ${produto.apresentacao}` : produto.nome;
      setProdutos([...produtos, { id: produto.id, nome: nomeCompleto, preco_venda: produto.preco_venda }]);
    }
    setBusca("");
    setEncontrados([]);
  }

  /** Preço de uma unidade na promoção, para conferir antes de salvar. */
  function precoNaPromocao(produto: ProdutoEscolhido): string | null {
    const normal = Number(produto.preco_venda);
    if (tipo === "percentual") {
      const pct = Number(percentual.replace(",", "."));
      return pct > 0 && pct < 100 ? reais(normal - Math.round(normal * pct) / 100, false) : null;
    }
    if (tipo === "preco_fixo") {
      const valor = Number(preco.replace(".", "").replace(",", "."));
      return valor > 0 ? reais(valor, false) : null;
    }
    return null;
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (produtos.length === 0) return setErro("Escolha pelo menos um produto");
    const corpo = {
      nome: nome.trim(),
      tipo,
      percentual: tipo === "percentual" ? percentual.replace(",", ".") : null,
      preco: tipo === "preco_fixo" ? preco.replace(".", "").replace(",", ".") : null,
      leve: tipo === "leve_pague" ? Number(leve) : null,
      pague: tipo === "leve_pague" ? Number(pague) : null,
      inicio,
      fim: fim || null,
      loja_id: loja || null,
      so_clientes: soClientes,
      produto_ids: produtos.map((p) => p.id),
      ...(promocao ? { ativa } : {}),
    };
    try {
      if (promocao) await api(`/promocoes/${promocao.id}`, { metodo: "PUT", corpo });
      else await api("/promocoes", { corpo });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo={promocao ? "Editar promoção" : "Nova promoção"} aoFechar={aoFechar}>
      <form className="campos" onSubmit={salvar}>
        <label className="largo">
          Nome da promoção *
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Semana do protetor" required />
        </label>

        <div className="largo opcoes-tipo">
          {TIPOS.map((t) => (
            <label key={t.valor} className={`opcao ${tipo === t.valor ? "marcada" : ""}`}>
              <input type="radio" name="tipo" checked={tipo === t.valor} onChange={() => setTipo(t.valor)} />
              <span>
                <strong>{t.nome}</strong>
                <small>{t.dica}</small>
              </span>
            </label>
          ))}
        </div>

        {tipo === "percentual" && (
          <label>
            Desconto (%)
            <input value={percentual} onChange={(e) => setPercentual(e.target.value)} inputMode="decimal" required />
          </label>
        )}
        {tipo === "preco_fixo" && (
          <label>
            Preço na promoção (R$)
            <input value={preco} onChange={(e) => setPreco(e.target.value)} inputMode="decimal" required />
            <small>O mesmo preço para todos os produtos escolhidos.</small>
          </label>
        )}
        {tipo === "leve_pague" && (
          <div className="leve-pague">
            <label>
              Leve
              <input type="number" min={2} value={leve} onChange={(e) => setLeve(e.target.value)} required />
            </label>
            <label>
              Pague
              <input type="number" min={1} value={pague} onChange={(e) => setPague(e.target.value)} required />
            </label>
          </div>
        )}
        <label>
          Loja
          <select value={loja} onChange={(e) => setLoja(e.target.value)}>
            <option value="">Todas as lojas</option>
            {lojas.map((l) => (
              <option key={l.id} value={l.id}>
                {l.nome}
              </option>
            ))}
          </select>
        </label>
        <label>
          Começa em
          <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} required />
        </label>
        <label>
          Termina em
          <input type="date" value={fim} onChange={(e) => setFim(e.target.value)} />
          <small>Vazio: vale até você encerrar.</small>
        </label>

        <div className="largo">
          <label>
            Produtos *
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Digite o nome do produto para incluir"
            />
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
          {produtos.length > 0 && (
            <ul className="escolhidos">
              {produtos.map((p) => (
                <li key={p.id}>
                  <span>
                    {p.nome}
                    <small>
                      {reais(p.preco_venda)}
                      {precoNaPromocao(p) && <> → {precoNaPromocao(p)}</>}
                    </small>
                  </span>
                  <button
                    type="button"
                    className="botao-icone"
                    title="Tirar da promoção"
                    onClick={() => setProdutos(produtos.filter((x) => x.id !== p.id))}
                  >
                    <Icone nome="x" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="checkbox caixa-marcacao largo">
          <input type="checkbox" checked={soClientes} onChange={(e) => setSoClientes(e.target.checked)} />
          <span>
            Só para cliente identificado no caixa
            <small>Bom para incentivar o cadastro: o desconto só sai quando o caixa identifica o cliente (F8).</small>
          </span>
        </label>
        {promocao && (
          <label className="checkbox caixa-marcacao largo">
            <input type="checkbox" checked={ativa} onChange={(e) => setAtiva(e.target.checked)} />
            <span>
              Promoção ativa
              <small>Desmarque para pausar sem apagar.</small>
            </span>
          </label>
        )}

        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit">Salvar</button>
        </div>
      </form>
    </Janela>
  );
}

import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Andamento, MetasDoMes } from "../../api/tipos";
import { reais } from "../../formato";
import { BarraMeta, pct, Recado, SITUACOES } from "./BarraMeta";

function mesDeHoje(): string {
  const hoje = new Date();
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
}

function nomeDoMes(mes: string): string {
  const [ano, m] = mes.split("-").map(Number);
  return new Date(ano, m - 1, 1).toLocaleString("pt-BR", { month: "long", year: "numeric" });
}

/** Valor digitado ("12.000,50" ou "12000") como texto da API ("12000.50"); vazio vira null. */
export function lerValor(texto: string): string | null {
  const limpo = texto.trim().replace(/\s|R\$/g, "").replace(/\./g, "").replace(",", ".");
  if (!limpo) return null;
  const numero = Number(limpo);
  return Number.isFinite(numero) && numero > 0 ? numero.toFixed(2) : "invalido";
}

function paraCampo(valor: string | null): string {
  return valor ? Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : "";
}

/** Sugestão: o vendido no mês passado com um aumento, arredondado para a centena. */
export function sugerir(vendidoMesPassado: string, aumento: number): string | null {
  const valor = Math.ceil((Number(vendidoMesPassado) * (1 + aumento / 100)) / 100) * 100;
  return valor > 0 ? String(valor) : null;
}

type Campos = Record<string, string>;

/** Metas de vendas do mês: de cada loja e de cada vendedor, e como cada um está indo. */
export default function Metas() {
  const [mes, setMes] = useState(mesDeHoje());
  const [dados, setDados] = useState<MetasDoMes | null>(null);
  const [campos, setCampos] = useState<Campos>({});
  const [aumento, setAumento] = useState("10");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [salvando, setSalvando] = useState(false);

  function preencher(d: MetasDoMes) {
    setDados(d);
    setCampos(Object.fromEntries([...d.lojas, ...d.vendedores].map((a) => [a.id ?? "", paraCampo(a.meta)])));
  }

  useEffect(() => {
    setAviso(null);
    api<MetasDoMes>(`/metas?mes=${mes}-01`)
      .then(preencher)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }, [mes]);

  if (!dados) return aviso ? <p className="erro">{aviso.texto}</p> : <p>Carregando...</p>;

  const passado = mes < mesDeHoje();
  const todos = [...dados.lojas, ...dados.vendedores];
  const mudou = todos.some((a) => (lerValor(campos[a.id ?? ""] ?? "") ?? null) !== (a.meta ? Number(a.meta).toFixed(2) : null));

  function sugerirTodas() {
    const n = Number(aumento.replace(",", ".")) || 0;
    setCampos((atual) => {
      const novo = { ...atual };
      for (const a of todos) {
        const sugestao = sugerir(a.vendido_mes_passado, n);
        if (!novo[a.id ?? ""] && sugestao) novo[a.id ?? ""] = paraCampo(sugestao);
      }
      return novo;
    });
  }

  async function salvar() {
    if (!dados) return;
    const itens = (lista: Andamento[]) => lista.map((a) => ({ id: a.id, valor: lerValor(campos[a.id ?? ""] ?? "") }));
    const lojas = itens(dados.lojas);
    const vendedores = itens(dados.vendedores);
    if ([...lojas, ...vendedores].some((i) => i.valor === "invalido")) {
      setAviso({ tipo: "erro", texto: "Confira os valores: use só números, como 15.000 ou 15000,00." });
      return;
    }
    setSalvando(true);
    try {
      preencher(await api<MetasDoMes>("/metas", { metodo: "PUT", corpo: { mes: `${mes}-01`, lojas, vendedores } }));
      setAviso({ tipo: "ok", texto: "Metas salvas. A equipe já vê a meta na tela inicial." });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    } finally {
      setSalvando(false);
    }
  }

  const total = dados.total;
  const atual = mes === mesDeHoje();

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Equipe</p>
          <h1>Metas de vendas</h1>
          <p className="vazio">
            Defina quanto cada loja e cada vendedor deve vender no mês. Todo mundo acompanha o andamento na tela inicial,
            com quanto falta vender por dia para bater.
          </p>
        </div>
        <label className="seletor-loja">
          Mês
          <input type="month" value={mes} onChange={(e) => e.target.value && setMes(e.target.value)} />
        </label>
      </div>

      <div className="indicadores indicadores-financeiro">
        <div className="cartao indicador">
          <small>Meta da farmácia em {nomeDoMes(mes)}</small>
          <strong>{total.meta ? reais(total.meta) : "Sem meta"}</strong>
          <span>{total.meta ? "soma das metas das lojas" : "defina a meta de cada loja abaixo"}</span>
        </div>
        <div className="cartao indicador">
          <small>Vendido</small>
          <strong>{reais(total.vendido)}</strong>
          <span>
            {total.meta ? `${pct(total.percentual)} da meta` : `${total.vendas} venda(s)`}
            {atual && ` · hoje ${reais(total.vendido_hoje)}`}
          </span>
        </div>
        <div className="cartao indicador">
          <small>{atual ? "Dias que faltam" : passado ? "Mês encerrado" : "Mês que vem"}</small>
          <strong>{atual ? dados.dias_restantes : dados.dias_no_mes}</strong>
          <span>{atual ? "contando hoje" : "dias no mês"}</span>
        </div>
      </div>

      {total.meta && (
        <div className="cartao cartao-separado meta-resumo">
          <div className="meta-resumo-topo">
            <strong>Farmácia toda</strong>
            <span className={`etiqueta ${SITUACOES[total.situacao].classe}`}>{SITUACOES[total.situacao].texto}</span>
          </div>
          <BarraMeta andamento={total} grande />
          <p className="vazio">
            <Recado andamento={total} dias={dados.dias_restantes} />
          </p>
        </div>
      )}

      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}

      {!passado && (
        <div className="cartao cartao-separado etiquetas-acoes metas-acoes">
          <label className="meta-sugestao">
            Sem ideia de valor? Use o que vendeu no mês anterior, mais
            <input className="campo-copias" value={aumento} onChange={(e) => setAumento(e.target.value)} inputMode="decimal" />
            %
          </label>
          <button type="button" className="botao-pequeno" onClick={sugerirTodas}>
            Preencher as vazias
          </button>
          <span className="espaco" />
          <button type="button" className="botao" disabled={!mudou || salvando} onClick={salvar}>
            {salvando ? "Salvando..." : "Salvar metas"}
          </button>
        </div>
      )}

      <Tabela
        titulo="Lojas"
        lista={dados.lojas}
        campos={campos}
        setCampos={setCampos}
        editavel={!passado}
        dias={dados.dias_restantes}
      />
      <Tabela
        titulo="Vendedores"
        nota="A venda que veio de pré-venda conta para quem atendeu no balcão. O vendedor vende em qualquer loja."
        lista={dados.vendedores}
        campos={campos}
        setCampos={setCampos}
        editavel={!passado}
        dias={dados.dias_restantes}
      />
    </div>
  );
}

function Tabela(props: {
  titulo: string;
  nota?: string;
  lista: Andamento[];
  campos: Campos;
  setCampos: (f: (c: Campos) => Campos) => void;
  editavel: boolean;
  dias: number;
}) {
  return (
    <div className="cartao cartao-separado">
      <div className="cartao-cabecalho">
        <h2>{props.titulo}</h2>
      </div>
      <table className="tabela tabela-metas">
        <thead>
          <tr>
            <th>{props.titulo === "Lojas" ? "Loja" : "Vendedor"}</th>
            <th className="num">Meta (R$)</th>
            <th className="num">Vendido</th>
            <th>Andamento</th>
            <th className="num">Por dia para bater</th>
            <th className="num">Mês anterior</th>
          </tr>
        </thead>
        <tbody>
          {props.lista.map((a) => {
            const id = a.id ?? "";
            return (
              <tr key={id}>
                <td>
                  <strong>{a.nome}</strong>
                  {a.detalhe && <span className="livro-detalhe">{a.detalhe}</span>}
                </td>
                <td className="num">
                  {props.editavel ? (
                    <input
                      className="campo-meta"
                      inputMode="decimal"
                      placeholder="sem meta"
                      aria-label={`Meta de ${a.nome}`}
                      value={props.campos[id] ?? ""}
                      onChange={(e) => props.setCampos((c) => ({ ...c, [id]: e.target.value }))}
                    />
                  ) : a.meta ? (
                    reais(a.meta)
                  ) : (
                    "-"
                  )}
                </td>
                <td className="num">
                  {reais(a.vendido)}
                  <span className="livro-detalhe">{a.vendas} venda(s)</span>
                </td>
                <td className="celula-andamento">
                  {a.meta ? (
                    <>
                      <BarraMeta andamento={a} />
                      <span className="livro-detalhe">
                        {pct(a.percentual)} · <span className={`etiqueta ${SITUACOES[a.situacao].classe}`}>{SITUACOES[a.situacao].texto}</span>
                      </span>
                    </>
                  ) : (
                    <span className="vazio">Sem meta</span>
                  )}
                </td>
                <td className="num">{a.por_dia ? reais(a.por_dia) : "-"}</td>
                <td className="num vazio">{reais(a.vendido_mes_passado)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {props.lista.length === 0 && <p className="lista-vazia">Ninguém por aqui ainda.</p>}
      {props.nota && <p className="nota">{props.nota}</p>}
    </div>
  );
}

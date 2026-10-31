import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, baixar, mensagem } from "../../api/cliente";
import type { DetalheVendedor, RelatorioComissoes } from "../../api/tipos";
import { data, quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { ehGerente, NOMES_PAPEIS, useSessao } from "../../sessao";

type Opcao = "este-mes" | "mes-passado" | "30";

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function periodo(opcao: Opcao): { inicio: string; fim: string; nome: string } {
  const hoje = new Date();
  if (opcao === "mes-passado") {
    const inicio = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
    const fim = new Date(hoje.getFullYear(), hoje.getMonth(), 0);
    return { inicio: iso(inicio), fim: iso(fim), nome: inicio.toLocaleString("pt-BR", { month: "long" }) };
  }
  if (opcao === "30") {
    const inicio = new Date(hoje);
    inicio.setDate(inicio.getDate() - 29);
    return { inicio: iso(inicio), fim: iso(hoje), nome: "últimos 30 dias" };
  }
  return { inicio: iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), fim: iso(hoje), nome: "este mês" };
}

function pct(valor: string): string {
  return `${Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
}

/** Comissão dos vendedores. O gerente vê todos; cada balconista vê as próprias vendas. */
export default function Comissoes() {
  const { sessao } = useSessao();
  const gerente = ehGerente(sessao);
  const lojas = useLojas();
  const [opcao, setOpcao] = useState<Opcao>("este-mes");
  const [lojaId, setLojaId] = useState("");
  const [relatorio, setRelatorio] = useState<RelatorioComissoes | null>(null);
  const [aberto, setAberto] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<DetalheVendedor | null>(null);
  const [erro, setErro] = useState("");
  const { inicio, fim, nome } = periodo(opcao);

  function filtros(comLoja = true) {
    const params = new URLSearchParams({ inicio, fim });
    if (comLoja && lojaId) params.set("loja_id", lojaId);
    return params.toString();
  }

  useEffect(() => {
    setErro("");
    if (gerente) {
      api<RelatorioComissoes>(`/comissoes?${filtros()}`)
        .then(setRelatorio)
        .catch((e) => setErro(mensagem(e)));
    } else {
      api<DetalheVendedor>(`/comissoes/minhas?${filtros(false)}`)
        .then(setDetalhe)
        .catch((e) => setErro(mensagem(e)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opcao, lojaId, gerente]);

  useEffect(() => {
    if (!gerente) return;
    if (!aberto) return setDetalhe(null);
    api<DetalheVendedor>(`/comissoes/vendedor/${aberto}?${filtros()}`)
      .then(setDetalhe)
      .catch((e) => setErro(mensagem(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberto, opcao, lojaId]);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Equipe</p>
          <h1>{gerente ? "Comissões" : "Minhas vendas"}</h1>
          <p className="vazio">
            {gerente
              ? "Quanto cada vendedor vendeu e quanto ganha de comissão. A venda que veio de pré-venda conta para quem atendeu no balcão."
              : "O que você vendeu e a sua comissão. A pré-venda que você faz conta para você, mesmo que outra pessoa passe no caixa."}
          </p>
        </div>
      </div>

      <div className="barra filtros-relatorio">
        <label className="seletor-loja">
          Período
          <select value={opcao} onChange={(e) => setOpcao(e.target.value as Opcao)}>
            <option value="este-mes">Este mês</option>
            <option value="mes-passado">Mês passado</option>
            <option value="30">Últimos 30 dias</option>
          </select>
        </label>
        {gerente && lojas.length > 1 && (
          <label className="seletor-loja">
            Loja
            <select value={lojaId} onChange={(e) => setLojaId(e.target.value)}>
              <option value="">Todas</option>
              {lojas.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="vazio">
          {data(inicio)} a {data(fim)}
        </span>
        {gerente && (
          <button type="button" className="botao-pequeno" onClick={() => baixar(`/comissoes/planilha?${filtros()}`).catch((e) => setErro(mensagem(e)))}>
            Planilha
          </button>
        )}
      </div>

      {erro && <p className="erro">{erro}</p>}

      {gerente && relatorio && (
        <>
          <div className="indicadores indicadores-financeiro">
            <div className="cartao indicador">
              <small>Vendido pela equipe</small>
              <strong>{reais(relatorio.total_vendido)}</strong>
              <span>{nome}</span>
            </div>
            <div className="cartao indicador">
              <small>Comissão a pagar</small>
              <strong>{reais(relatorio.total_comissao)}</strong>
              <span>{relatorio.vendedores.filter((v) => Number(v.comissao) > 0).length} vendedor(es)</span>
            </div>
            <div className="cartao indicador">
              <small>Comissão padrão</small>
              <strong>{pct(relatorio.comissao_padrao)}</strong>
              <span>
                <Link to="/configuracoes/gerais">mudar</Link> · produto pode ter outra
              </span>
            </div>
          </div>

          <div className="cartao cartao-separado">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Vendedor</th>
                  <th className="num">Vendas</th>
                  <th className="num">Vendido</th>
                  <th className="num">Ticket médio</th>
                  <th className="num">% médio</th>
                  <th className="num">Comissão</th>
                </tr>
              </thead>
              <tbody>
                {relatorio.vendedores.map((v) => (
                  <tr
                    key={v.usuario_id}
                    className={`linha-clicavel ${aberto === v.usuario_id ? "selecionado" : ""}`}
                    onClick={() => setAberto(aberto === v.usuario_id ? null : v.usuario_id)}
                  >
                    <td>
                      <strong>{v.nome}</strong>
                      <span className="livro-detalhe">
                        {NOMES_PAPEIS[v.papel]}
                        {!v.recebe_comissao && " · não recebe comissão"}
                      </span>
                    </td>
                    <td className="num">{v.vendas}</td>
                    <td className="num">{reais(v.vendido)}</td>
                    <td className="num">{reais(v.ticket_medio)}</td>
                    <td className="num">{pct(v.percentual)}</td>
                    <td className="num">
                      <strong>{reais(v.comissao)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {relatorio.vendedores.length === 0 && <p className="lista-vazia">Nenhuma venda no período.</p>}
            <p className="nota">Clique num vendedor para ver as vendas e os produtos. Vendas canceladas não entram.</p>
          </div>
        </>
      )}

      {detalhe && <Detalhe detalhe={detalhe} gerente={gerente} />}
    </div>
  );
}

function Detalhe({ detalhe, gerente }: { detalhe: DetalheVendedor; gerente: boolean }) {
  const v = detalhe.vendedor;
  return (
    <>
      {!gerente && (
        <div className="indicadores indicadores-financeiro">
          <div className="cartao indicador">
            <small>Você vendeu</small>
            <strong>{reais(v.vendido)}</strong>
            <span>{v.vendas} venda(s)</span>
          </div>
          <div className="cartao indicador">
            <small>Sua comissão</small>
            <strong>{reais(v.comissao)}</strong>
            <span>{v.recebe_comissao ? `${pct(v.percentual)} em média` : "seu usuário não recebe comissão"}</span>
          </div>
          <div className="cartao indicador">
            <small>Ticket médio</small>
            <strong>{reais(v.ticket_medio)}</strong>
            <span>por venda</span>
          </div>
        </div>
      )}
      <div className="ficha-colunas">
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>{gerente ? `Produtos de ${v.nome}` : "O que mais deu comissão"}</h2>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Produto</th>
                <th className="num">Qtd</th>
                <th className="num">Vendido</th>
                <th className="num">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {detalhe.produtos.slice(0, 15).map((p) => (
                <tr key={p.produto_id}>
                  <td>
                    {p.descricao}
                    <span className="livro-detalhe">{pct(p.percentual)}</span>
                  </td>
                  <td className="num">{quantidade(p.quantidade)}</td>
                  <td className="num">{reais(p.vendido)}</td>
                  <td className="num">{reais(p.comissao)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detalhe.produtos.length === 0 && <p className="lista-vazia">Nenhuma venda no período.</p>}
        </div>
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Vendas</h2>
            <small>{detalhe.vendas.length} no período</small>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Venda</th>
                <th>Data</th>
                <th className="num">Vendido</th>
                <th className="num">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {detalhe.vendas.slice(0, 50).map((venda) => (
                <tr key={venda.venda_id}>
                  <td>
                    nº {venda.numero}
                    {venda.pre_venda && <span className="livro-detalhe">pré-venda</span>}
                  </td>
                  <td>{new Date(venda.finalizada_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td className="num">{reais(venda.vendido)}</td>
                  <td className="num">{reais(venda.comissao)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detalhe.vendas.length > 50 && <p className="nota">Mostrando as 50 mais recentes.</p>}
        </div>
      </div>
    </>
  );
}

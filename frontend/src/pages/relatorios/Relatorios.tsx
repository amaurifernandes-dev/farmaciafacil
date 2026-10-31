import { useEffect, useState, type ReactNode } from "react";

import { api, mensagem } from "../../api/cliente";
import type { RelatorioParados, RelatorioProdutos, RelatorioVendas, ResumoVendas } from "../../api/tipos";
import SeletorLoja from "../../components/SeletorLoja";
import { data, quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";

type Aba = "vendas" | "produtos" | "parados";

const NOMES_FORMA: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo",
  convenio: "Convênio",
  popular: "Farmácia Popular",
};

function iso(dia: Date): string {
  return new Date(dia.getTime() - dia.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function periodo(opcao: string): [string, string] {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();
  const dia = hoje.getDate();
  switch (opcao) {
    case "7":
      return [iso(new Date(ano, mes, dia - 6)), iso(hoje)];
    case "90":
      return [iso(new Date(ano, mes, dia - 89)), iso(hoje)];
    case "este-mes":
      return [iso(new Date(ano, mes, 1)), iso(hoje)];
    case "mes-passado":
      return [iso(new Date(ano, mes - 1, 1)), iso(new Date(ano, mes, 0))];
    default:
      return [iso(new Date(ano, mes, dia - 29)), iso(hoje)];
  }
}

/** Baixa uma tabela como CSV que abre direto no Excel (separador ; e vírgula decimal). */
function baixarCsv(nome: string, cabecalho: string[], linhas: (string | number | null)[][]) {
  const celula = (v: string | number | null) => {
    const texto = v == null ? "" : typeof v === "number" ? String(v).replace(".", ",") : v;
    return /[;"\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
  };
  const conteudo = [cabecalho, ...linhas].map((l) => l.map(celula).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + conteudo], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.click();
  URL.revokeObjectURL(url);
}

/** "R$ 1.234,56" de um decimal da API, sem centavos implícitos. */
function r(valor: string | number): string {
  return reais(valor, false);
}

function variacao(atual: string, anterior: string): ReactNode {
  const a = Number(atual);
  const b = Number(anterior);
  if (!b) return null;
  const pct = ((a - b) / b) * 100;
  const texto = `${pct >= 0 ? "+" : ""}${pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  return <span className={pct >= 0 ? "texto-ok" : "texto-erro"}>{texto} vs. período anterior</span>;
}

export default function Relatorios() {
  const lojas = useLojas();
  const [aba, setAba] = useState<Aba>("vendas");
  const [opcao, setOpcao] = useState("30");
  const [lojaId, setLojaId] = useState("");
  const [dias, setDias] = useState("60");

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Gestão</p>
          <h1>Relatórios</h1>
          <p className="vazio">Quanto vendeu, quanto lucrou e o que está parado na prateleira.</p>
        </div>
      </div>

      <nav className="abas abas-botoes">
        {(
          [
            ["vendas", "Vendas"],
            ["produtos", "Lucro por produto"],
            ["parados", "Produtos parados"],
          ] as [Aba, string][]
        ).map(([valor, nome]) => (
          <button key={valor} type="button" className={aba === valor ? "active" : ""} onClick={() => setAba(valor)}>
            {nome}
          </button>
        ))}
      </nav>

      <div className="barra filtros-relatorio">
        {aba === "parados" ? (
          <label className="seletor-loja">
            Sem vender há mais de
            <select value={dias} onChange={(e) => setDias(e.target.value)}>
              <option value="30">30 dias</option>
              <option value="60">60 dias</option>
              <option value="90">90 dias</option>
              <option value="180">180 dias</option>
            </select>
          </label>
        ) : (
          <label className="seletor-loja">
            Período
            <select value={opcao} onChange={(e) => setOpcao(e.target.value)}>
              <option value="7">Últimos 7 dias</option>
              <option value="30">Últimos 30 dias</option>
              <option value="90">Últimos 90 dias</option>
              <option value="este-mes">Este mês</option>
              <option value="mes-passado">Mês passado</option>
            </select>
          </label>
        )}
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Todas as lojas" />
      </div>

      {aba === "vendas" && <Vendas opcao={opcao} lojaId={lojaId} />}
      {aba === "produtos" && <Produtos opcao={opcao} lojaId={lojaId} />}
      {aba === "parados" && <Parados dias={dias} lojaId={lojaId} />}
    </div>
  );
}

function useRelatorio<T>(caminho: string): [T | null, string] {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    setDados(null);
    api<T>(caminho)
      .then((resposta) => {
        setDados(resposta);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }, [caminho]);
  return [dados, erro];
}

function filtro(opcao: string, lojaId: string): string {
  const [inicio, fim] = periodo(opcao);
  return `inicio=${inicio}&fim=${fim}${lojaId ? `&loja_id=${lojaId}` : ""}`;
}

function Vendas({ opcao, lojaId }: { opcao: string; lojaId: string }) {
  const [relatorio, erro] = useRelatorio<RelatorioVendas>(`/relatorios/vendas?${filtro(opcao, lojaId)}`);
  if (erro) return <p className="erro">{erro}</p>;
  if (!relatorio) return <p className="vazio">Carregando...</p>;
  const { resumo, anterior } = relatorio;
  const maior = Math.max(1, ...relatorio.por_dia.map((d) => Number(d.total)));
  const totalFormas = relatorio.por_forma.reduce((s, f) => s + Number(f.valor), 0);

  return (
    <>
      <div className="indicadores indicadores-financeiro">
        <Indicador titulo="Faturamento" valor={r(resumo.faturamento)}>
          {variacao(resumo.faturamento, anterior.faturamento) ?? `${resumo.quantidade} venda(s)`}
        </Indicador>
        <Indicador titulo="Vendas" valor={String(resumo.quantidade)}>
          Ticket médio {r(resumo.ticket_medio)}
        </Indicador>
        <Indicador titulo="Lucro bruto" valor={r(resumo.lucro_bruto)}>
          Margem de {Number(resumo.margem).toLocaleString("pt-BR")}% · custo {r(resumo.custo)}
        </Indicador>
        <Indicador titulo="Descontos dados" valor={r(resumo.descontos)}>
          {Number(resumo.descontos_promocao) > 0 ? `${r(resumo.descontos_promocao)} em promoções` : "Nenhum em promoções"}
        </Indicador>
      </div>
      <AvisoCusto resumo={resumo} />

      <div className="cartao">
        <div className="cartao-cabecalho">
          <h2>Vendas por dia</h2>
          <small>
            {data(relatorio.inicio)} a {data(relatorio.fim)}
          </small>
        </div>
        <div className="grafico grafico-relatorio">
          {relatorio.por_dia.map((dia) => (
            <div
              key={dia.data}
              className="grafico-coluna"
              title={`${data(dia.data)}: ${r(dia.total)} em ${dia.quantidade} venda(s)`}
            >
              <div className="grafico-area">
                <div className="barra-dia" style={{ height: `${(Number(dia.total) / maior) * 100}%` }} />
              </div>
              {relatorio.por_dia.length <= 31 && <span>{dia.data.slice(8, 10)}</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="ficha-colunas">
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Como os clientes pagaram</h2>
          </div>
          <table className="tabela">
            <tbody>
              {relatorio.por_forma.map((f) => (
                <tr key={f.forma}>
                  <td>{NOMES_FORMA[f.forma] ?? f.forma}</td>
                  <td className="grafico-saldo">
                    <span className="barra-entrada" style={{ width: `${(Number(f.valor) / (totalFormas || 1)) * 100}%` }} />
                  </td>
                  <td className="num">{r(f.valor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {relatorio.por_forma.length === 0 && <p className="lista-vazia">Nenhuma venda no período.</p>}
        </div>
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Por operador</h2>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Operador</th>
                <th className="num">Vendas</th>
                <th className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {relatorio.por_operador.map((o) => (
                <tr key={o.nome}>
                  <td>{o.nome}</td>
                  <td className="num">{o.quantidade}</td>
                  <td className="num">{r(o.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {resumo.canceladas > 0 && (
            <p className="nota">
              {resumo.canceladas} venda(s) cancelada(s) no período, somando {r(resumo.valor_cancelado)}.
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function Indicador({ titulo, valor, children }: { titulo: string; valor: string; children: ReactNode }) {
  return (
    <div className="cartao indicador">
      <small>{titulo}</small>
      <strong>{valor}</strong>
      <small>{children}</small>
    </div>
  );
}

function AvisoCusto({ resumo }: { resumo: ResumoVendas }) {
  if (!resumo.itens_sem_custo) return null;
  return (
    <p className="nota aviso-custo">
      {resumo.itens_sem_custo} item(ns) vendido(s) sem preço de custo no cadastro ficaram fora do lucro. Informe o custo
      do produto (ou dê entrada pela nota de compra) para o lucro ficar exato.
    </p>
  );
}

const CURVAS = {
  A: "Os que trazem 80% do faturamento: nunca podem faltar.",
  B: "Os próximos 15%: importantes, mas com menos giro.",
  C: "Os últimos 5%: candidatos a comprar menos.",
};

function Produtos({ opcao, lojaId }: { opcao: string; lojaId: string }) {
  const [relatorio, erro] = useRelatorio<RelatorioProdutos>(`/relatorios/produtos?${filtro(opcao, lojaId)}`);
  const [curva, setCurva] = useState("");
  if (erro) return <p className="erro">{erro}</p>;
  if (!relatorio) return <p className="vazio">Carregando...</p>;
  const linhas = relatorio.produtos.filter((p) => !curva || p.curva === curva);

  return (
    <>
      <div className="indicadores indicadores-financeiro">
        <Indicador titulo="Faturamento dos produtos" valor={r(relatorio.faturamento)}>
          {relatorio.produtos.length} produto(s) vendido(s)
        </Indicador>
        {(["A", "B", "C"] as const).map((c) => (
          <button
            key={c}
            type="button"
            className={`cartao indicador ${curva === c ? "indicador-marcado" : ""}`}
            onClick={() => setCurva(curva === c ? "" : c)}
          >
            <small>Curva {c}</small>
            <strong>{relatorio[`curva_${c.toLowerCase()}` as "curva_a"]} produto(s)</strong>
            <small>{CURVAS[c]}</small>
          </button>
        ))}
      </div>

      <div className="cartao">
        <div className="cartao-cabecalho">
          <h2>{curva ? `Curva ${curva}` : "Todos os produtos vendidos"}</h2>
          <button
            type="button"
            className="botao-pequeno"
            onClick={() =>
              baixarCsv(
                `lucro-por-produto-${relatorio.inicio}-a-${relatorio.fim}.csv`,
                ["Produto", "Curva", "Quantidade", "Faturamento", "Custo", "Lucro", "Margem %", "Participação %"],
                linhas.map((p) => [
                  p.nome, p.curva, Number(p.quantidade), Number(p.faturamento),
                  p.custo == null ? null : Number(p.custo), p.lucro == null ? null : Number(p.lucro),
                  p.margem == null ? null : Number(p.margem), Number(p.participacao),
                ]),
              )
            }
          >
            Baixar planilha
          </button>
        </div>
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Produto</th>
                <th>Curva</th>
                <th className="num">Qtd</th>
                <th className="num">Faturamento</th>
                <th className="num">Lucro</th>
                <th className="num">Margem</th>
                <th className="num">% do total</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((p) => (
                <tr key={p.produto_id}>
                  <td>{p.nome}</td>
                  <td>
                    <span className={`etiqueta curva-${p.curva}`}>{p.curva}</span>
                  </td>
                  <td className="num">{quantidade(p.quantidade)}</td>
                  <td className="num">{r(p.faturamento)}</td>
                  <td className="num">{p.lucro == null ? <span title="Produto sem custo">-</span> : r(p.lucro)}</td>
                  <td className={`num ${p.margem != null && Number(p.margem) < 15 ? "texto-erro" : ""}`}>
                    {p.margem == null ? "-" : `${Number(p.margem).toLocaleString("pt-BR")}%`}
                  </td>
                  <td className="num">{Number(p.participacao).toLocaleString("pt-BR")}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {linhas.length === 0 && <p className="lista-vazia">Nenhuma venda no período.</p>}
        <p className="nota">Margem abaixo de 15% aparece em vermelho. Produto sem custo cadastrado fica sem lucro.</p>
      </div>
    </>
  );
}

function Parados({ dias, lojaId }: { dias: string; lojaId: string }) {
  const [relatorio, erro] = useRelatorio<RelatorioParados>(
    `/relatorios/parados?dias=${dias}${lojaId ? `&loja_id=${lojaId}` : ""}`,
  );

  return (
    <>
      {erro && <p className="erro">{erro}</p>}
      {!relatorio ? (
        !erro && <p className="vazio">Carregando...</p>
      ) : (
        <>
          <div className="indicadores indicadores-financeiro">
            <Indicador titulo="Dinheiro parado no estoque" valor={r(relatorio.valor_total)}>
              Pelo preço de custo
            </Indicador>
            <Indicador titulo="Produtos parados" valor={String(relatorio.produtos.length)}>
              {relatorio.produtos.filter((p) => p.dias_parado === null).length} nunca venderam
            </Indicador>
          </div>
          <div className="cartao">
            <div className="cartao-cabecalho">
              <h2>Produtos com estoque e sem venda há mais de {relatorio.dias} dias</h2>
              <button
                type="button"
                className="botao-pequeno"
                onClick={() =>
                  baixarCsv(
                    `produtos-parados-${relatorio.dias}-dias.csv`,
                    ["Produto", "Estoque", "Custo unitário", "Valor parado", "Última venda", "Dias parado", "Validade"],
                    relatorio.produtos.map((p) => [
                      p.nome, Number(p.saldo), p.custo_unitario == null ? null : Number(p.custo_unitario),
                      p.valor_parado == null ? null : Number(p.valor_parado),
                      p.ultima_venda ? data(p.ultima_venda) : "Nunca vendeu", p.dias_parado,
                      p.validade_mais_proxima ? data(p.validade_mais_proxima) : null,
                    ]),
                  )
                }
              >
                Baixar planilha
              </button>
            </div>
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th className="num">Estoque</th>
                    <th className="num">Valor parado</th>
                    <th>Última venda</th>
                    <th>Validade mais próxima</th>
                  </tr>
                </thead>
                <tbody>
                  {relatorio.produtos.map((p) => (
                    <tr key={p.produto_id}>
                      <td>{p.nome}</td>
                      <td className="num">{quantidade(p.saldo)}</td>
                      <td className="num">{p.valor_parado == null ? "-" : r(p.valor_parado)}</td>
                      <td>
                        {p.ultima_venda ? (
                          <>
                            {data(p.ultima_venda)}
                            <small className="linha-detalhe">há {p.dias_parado} dias</small>
                          </>
                        ) : (
                          <span className="etiqueta etiqueta-neutra">Nunca vendeu</span>
                        )}
                      </td>
                      <td>{p.validade_mais_proxima ? data(p.validade_mais_proxima) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {relatorio.produtos.length === 0 && (
              <p className="lista-vazia">Nenhum produto parado. Tudo o que está em estoque vendeu no período.</p>
            )}
            <p className="nota">
              Ideias: colocar em promoção, devolver ao fornecedor ou comprar menos na próxima vez.
            </p>
          </div>
        </>
      )}
    </>
  );
}

import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Devolucao, ListaDevolucoes, VendaParaDevolver } from "../../api/tipos";
import Icone from "../../components/Icone";
import { data, quantidade as fmtQtd, reais } from "../../formato";
import { MOTIVOS, devolvidoPorItem, lerQuantidade, textoPontos, valorDoItem } from "./calculo";

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

type Aba = "nova" | "lista";

function dataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function abrirComprovante(id: string) {
  window.open(`/devolucoes/${id}/comprovante`, "_blank");
}

/** Troca e devolução: o cliente traz parte da compra e recebe em dinheiro ou em vale-troca. */
export default function Devolucoes() {
  const [parametros] = useSearchParams();
  const [aba, setAba] = useState<Aba>("nova");

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Trocas e devoluções</h1>
          <p className="vazio">Devolva um ou mais itens de uma venda. O valor volta em dinheiro ou vira vale-troca.</p>
        </div>
      </div>
      <nav className="abas abas-botoes">
        <button type="button" className={aba === "nova" ? "active" : ""} onClick={() => setAba("nova")}>
          Nova devolução
        </button>
        <button type="button" className={aba === "lista" ? "active" : ""} onClick={() => setAba("lista")}>
          Devoluções feitas
        </button>
      </nav>
      {aba === "nova" ? <NovaDevolucao numeroInicial={parametros.get("venda") ?? ""} /> : <Lista />}
    </div>
  );
}

function NovaDevolucao({ numeroInicial }: { numeroInicial: string }) {
  const [numero, setNumero] = useState(numeroInicial);
  const [venda, setVenda] = useState<VendaParaDevolver | null>(null);
  const [quantidades, setQuantidades] = useState<Record<string, string>>({});
  const [voltam, setVoltam] = useState<Record<string, boolean>>({});
  const [destino, setDestino] = useState<"vale" | "dinheiro">("vale");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [feita, setFeita] = useState<Devolucao | null>(null);

  async function buscar(alvo = numero) {
    const n = Number(alvo.trim().replace("#", ""));
    if (!Number.isInteger(n) || n <= 0) return setErro("Digite o número da venda (está no cupom)");
    setErro("");
    try {
      const encontrada = await api<VendaParaDevolver>(`/devolucoes/venda?numero=${n}`);
      setVenda(encontrada);
      // Venda de um item só: já deixa tudo marcado para devolver.
      const unico = encontrada.itens.length === 1 && !encontrada.itens[0].bloqueio ? encontrada.itens[0] : null;
      setQuantidades(unico ? { [unico.venda_item_id]: String(Number(unico.disponivel)) } : {});
      setVoltam(Object.fromEntries(encontrada.itens.map((i) => [i.venda_item_id, i.volta_estoque_sugerido])));
      setDestino("vale");
    } catch (e) {
      setVenda(null);
      setErro(mensagem(e));
    }
  }

  useEffect(() => {
    if (numeroInicial) buscar(numeroInicial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numeroInicial]);

  function recomecar() {
    setFeita(null);
    setVenda(null);
    setNumero("");
    setMotivo("");
    setQuantidades({});
  }

  const jaDevolvido = venda ? devolvidoPorItem(venda.devolucoes) : {};
  const escolhidos = (venda?.itens ?? [])
    .map((item) => ({ item, qtd: lerQuantidade(quantidades[item.venda_item_id] ?? "") }))
    .filter(({ qtd }) => qtd > 0);
  const totalCentavos = escolhidos.reduce(
    (soma, { item, qtd }) => soma + valorDoItem(item, qtd, jaDevolvido[item.venda_item_id] ?? 0),
    0,
  );
  const pagaComVale = venda?.formas.includes("vale") ?? false;

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    if (!venda) return;
    if (escolhidos.length === 0) return setErro("Escolha a quantidade de pelo menos um item");
    const demais = escolhidos.find(({ item, qtd }) => qtd > Number(item.disponivel));
    if (demais) return setErro(`De ${demais.item.descricao} só dá para devolver ${fmtQtd(demais.item.disponivel)}`);
    setErro("");
    setEnviando(true);
    try {
      const devolucao = await api<Devolucao>("/devolucoes", {
        corpo: {
          venda_id: venda.venda_id,
          destino,
          motivo: motivo.trim(),
          itens: escolhidos.map(({ item, qtd }) => ({
            venda_item_id: item.venda_item_id,
            quantidade: String(qtd),
            volta_estoque: voltam[item.venda_item_id] ?? item.volta_estoque_sugerido,
          })),
        },
      });
      setFeita(devolucao);
      window.scrollTo({ top: 0 });
    } catch (falha) {
      setErro(mensagem(falha));
    } finally {
      setEnviando(false);
    }
  }

  if (feita) {
    return (
      <div className="cartao cartao-separado devolucao-feita">
        <p className="sobretitulo">
          Devolução nº {feita.numero} · venda nº {feita.venda_numero}
        </p>
        {feita.vale ? (
          <>
            <h2>Vale-troca de {reais(feita.vale.valor)}</h2>
            <p className="codigo-vale" aria-label="Código do vale-troca">
              {feita.vale.codigo.slice(0, 4)} {feita.vale.codigo.slice(4)}
            </p>
            <p>
              Vale até {data(feita.vale.validade)}. No caixa, escolha <strong>Vale-troca (Alt+8)</strong> e digite o
              código.
            </p>
          </>
        ) : (
          <>
            <h2>Entregue {reais(feita.valor_total)} em dinheiro ao cliente</h2>
            <p>O valor já saiu do dinheiro esperado no fechamento do caixa.</p>
          </>
        )}
        {(feita.pontos ?? 0) !== 0 && <p className="vazio">{textoPontos(feita.pontos ?? 0)}</p>}
        <ul className="lista-simples">
          {feita.itens.map((i) => (
            <li key={i.venda_item_id}>
              {fmtQtd(i.quantidade)}x {i.descricao} · {reais(i.valor)}{" "}
              <small className="vazio">{i.volta_estoque ? "voltou para o estoque" : "descarte (não volta à venda)"}</small>
            </li>
          ))}
        </ul>
        <div className="acoes-linha">
          <button type="button" className="botao" onClick={() => abrirComprovante(feita.id)}>
            <Icone nome="recibo" /> Imprimir comprovante
          </button>
          <button type="button" className="botao-pequeno" onClick={recomecar}>
            Nova devolução
          </button>
        </div>
      </div>
    );
  }

  return (
    <form className="devolucao-form" onSubmit={confirmar}>
      <div className="cartao cartao-separado">
        <h2>1. Qual venda?</h2>
        <div className="barra">
          <input
            value={numero}
            onChange={(e) => setNumero(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                buscar();
              }
            }}
            inputMode="numeric"
            placeholder="Número da venda (está no cupom)"
            aria-label="Número da venda"
            autoFocus
          />
          <button type="button" className="botao-pequeno" onClick={() => buscar()}>
            Buscar
          </button>
        </div>
        {venda && (
          <p className="devolucao-venda">
            <strong>Venda nº {venda.numero}</strong> · {dataHora(venda.finalizada_em)} · {reais(venda.total)} ·{" "}
            {venda.formas.map((f) => FORMAS[f] ?? f).join(" + ")}
            {venda.cliente_nome && <> · {venda.cliente_nome}</>}
          </p>
        )}
        {venda?.bloqueio && <p className="erro">{venda.bloqueio}</p>}
        {!venda && erro && <p className="erro">{erro}</p>}
      </div>

      {venda && !venda.bloqueio && (
        <>
          <div className="cartao cartao-separado">
            <h2>2. O que o cliente trouxe de volta?</h2>
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th className="num">Comprou</th>
                    <th className="num">Pagou</th>
                    <th className="num">Devolver</th>
                    <th className="num">Valor</th>
                    <th>Volta para o estoque?</th>
                  </tr>
                </thead>
                <tbody>
                  {venda.itens.map((item) => {
                    const id = item.venda_item_id;
                    const qtd = lerQuantidade(quantidades[id] ?? "");
                    const esgotado = Number(item.disponivel) <= 0;
                    return (
                      <tr key={id} className={item.bloqueio || esgotado ? "inativo" : ""}>
                        <td>
                          {item.descricao}
                          {Number(item.devolvida) > 0 && (
                            <small className="vazio"> · já devolveu {fmtQtd(item.devolvida)}</small>
                          )}
                          {item.bloqueio && <small className="erro bloco">{item.bloqueio}</small>}
                        </td>
                        <td className="num">{fmtQtd(item.quantidade)}</td>
                        <td className="num">{reais(item.valor_pago)}</td>
                        <td className="num">
                          {item.bloqueio || esgotado ? (
                            <span className="vazio">{esgotado ? "devolvido" : "—"}</span>
                          ) : (
                            <input
                              className="campo-quantidade"
                              value={quantidades[id] ?? ""}
                              onChange={(e) => setQuantidades({ ...quantidades, [id]: e.target.value })}
                              inputMode="decimal"
                              placeholder="0"
                              aria-label={`Quantidade de ${item.descricao} a devolver`}
                            />
                          )}
                        </td>
                        <td className="num">
                          {qtd > 0 ? reais(valorDoItem(item, qtd, jaDevolvido[id] ?? 0)) : <span className="vazio">—</span>}
                        </td>
                        <td>
                          {!item.bloqueio && !esgotado && (
                            <label className="checkbox">
                              <input
                                type="checkbox"
                                checked={voltam[id] ?? item.volta_estoque_sugerido}
                                onChange={(e) => setVoltam({ ...voltam, [id]: e.target.checked })}
                              />
                              {(voltam[id] ?? item.volta_estoque_sugerido) ? "Sim, volta à venda" : "Não, vai para descarte"}
                            </label>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="nota">
              Remédio que saiu da farmácia não volta para a prateleira, porque não dá para garantir como foi guardado.
              Por isso ele vem marcado como descarte.
            </p>
          </div>

          <div className="cartao cartao-separado">
            <h2>3. Como o cliente recebe?</h2>
            <div className="servico-opcoes">
              <button
                type="button"
                className={`servico-opcao ${destino === "vale" ? "escolhido" : ""}`}
                onClick={() => setDestino("vale")}
              >
                <strong>Vale-troca</strong>
                <small>Crédito para usar em outra compra, por 90 dias</small>
              </button>
              <button
                type="button"
                className={`servico-opcao ${destino === "dinheiro" ? "escolhido" : ""}`}
                onClick={() => setDestino("dinheiro")}
                disabled={pagaComVale}
                title={pagaComVale ? "A venda foi paga com vale-troca" : undefined}
              >
                <strong>Dinheiro</strong>
                <small>{pagaComVale ? "Venda paga com vale: só em vale" : "Sai do caixa aberto neste computador"}</small>
              </button>
            </div>
            <label className="campo-motivo">
              Motivo
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} required minLength={3} maxLength={200} />
            </label>
            <div className="motivos-rapidos">
              {MOTIVOS.map((m) => (
                <button key={m} type="button" className="botao-pequeno" onClick={() => setMotivo(m)}>
                  {m}
                </button>
              ))}
            </div>
            <div className="devolucao-total">
              <span>{destino === "vale" ? "Valor do vale-troca" : "Entregar ao cliente"}</span>
              <strong>{reais(totalCentavos)}</strong>
            </div>
            {erro && <p className="erro">{erro}</p>}
            <div className="acoes-linha">
              <button type="submit" className="botao" disabled={enviando || totalCentavos <= 0}>
                Confirmar devolução
              </button>
            </div>
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

function Lista() {
  const [periodo, setPeriodo] = useState<Periodo>("este-mes");
  const [lista, setLista] = useState<ListaDevolucoes | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<ListaDevolucoes>(`/devolucoes?${datas(periodo)}`)
      .then(setLista)
      .catch((e) => setErro(mensagem(e)));
  }, [periodo]);

  return (
    <>
      <div className="barra filtros-relatorio">
        <select value={periodo} onChange={(e) => setPeriodo(e.target.value as Periodo)} aria-label="Período">
          <option value="este-mes">Este mês</option>
          <option value="mes-passado">Mês passado</option>
          <option value="30">Últimos 30 dias</option>
        </select>
      </div>
      {erro && <p className="erro">{erro}</p>}
      {lista && (
        <div className="indicadores indicadores-financeiro">
          <div className="cartao indicador">
            <small>Devoluções</small>
            <strong>{lista.quantidade}</strong>
            <span>{reais(lista.total)} no total</span>
          </div>
          <div className="cartao indicador">
            <small>Em dinheiro</small>
            <strong>{reais(lista.em_dinheiro)}</strong>
            <span>saiu dos caixas</span>
          </div>
          <div className="cartao indicador">
            <small>Em vale-troca</small>
            <strong>{reais(lista.em_vale)}</strong>
            <span>ficou de crédito na loja</span>
          </div>
        </div>
      )}
      <div className="cartao cartao-separado">
        {lista && lista.itens.length === 0 ? (
          <p className="lista-vazia">Nenhuma devolução no período.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nº</th>
                  <th>Quando</th>
                  <th>Venda</th>
                  <th>Itens</th>
                  <th>Motivo</th>
                  <th>Como recebeu</th>
                  <th className="num">Valor</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lista?.itens.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <strong>{d.numero}</strong>
                    </td>
                    <td>
                      {dataHora(d.criado_em)}
                      <small className="vazio bloco">{d.usuario}</small>
                    </td>
                    <td>nº {d.venda_numero}</td>
                    <td>{d.itens.map((i) => `${fmtQtd(i.quantidade)}x ${i.descricao}`).join(", ")}</td>
                    <td>{d.motivo}</td>
                    <td>
                      {d.vale ? (
                        <span className={`etiqueta ${d.vale.status === "ativo" ? "" : "etiqueta-neutra"}`}>
                          Vale {d.vale.codigo} · {d.vale.status === "ativo" ? `saldo ${reais(d.vale.saldo)}` : d.vale.status}
                        </span>
                      ) : (
                        <span className="etiqueta etiqueta-neutra">Dinheiro</span>
                      )}
                    </td>
                    <td className="num">
                      {reais(d.valor_total)}
                      {(d.pontos ?? 0) !== 0 && (
                        <small className="vazio bloco">
                          {(d.pontos ?? 0) > 0 ? "+" : ""}
                          {d.pontos} pontos
                        </small>
                      )}
                    </td>
                    <td className="num">
                      <button type="button" className="botao-pequeno" onClick={() => abrirComprovante(d.id)}>
                        Comprovante
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="nota">
        Para fazer uma devolução a partir da venda, use o botão Trocar em <Link to="/vendas">Vendas / PDV</Link>.
      </p>
    </>
  );
}

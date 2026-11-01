import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { RelatorioCaixas, ResumoCaixa } from "../../api/tipos";
import Icone from "../../components/Icone";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { DetalheCaixa } from "./Caixas";
import { NOMES_FORMA } from "./conferencia";
import { TabelaConferencia } from "./Fechamento";

function hojeLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const hora = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "-";

/** Fechamento do dia: todos os caixas da data, por forma de pagamento, com sangrias e diferenças. */
export default function FechamentoDoDia() {
  const lojas = useLojas();
  const [dia, setDia] = useState(hojeLocal);
  const [lojaId, setLojaId] = useState("");
  const [relatorio, setRelatorio] = useState<RelatorioCaixas | null>(null);
  const [vendo, setVendo] = useState<ResumoCaixa | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setRelatorio(null);
    setErro("");
    api<RelatorioCaixas>(`/caixas/relatorio?dia=${dia}${lojaId ? `&loja_id=${lojaId}` : ""}`)
      .then(setRelatorio)
      .catch((e) => setErro(mensagem(e)));
  }, [dia, lojaId]);

  const diferenca = Number(relatorio?.diferenca_total ?? 0);
  const nomeLoja = lojas.find((l) => l.id === lojaId)?.nome;

  return (
    <div className="pagina fechamento-dia">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo nao-imprimir">
            <Link to="/caixas">Caixas</Link>
          </p>
          <h1>Fechamento do dia</h1>
          <p className="vazio">
            {data(dia)}
            {nomeLoja ? ` · ${nomeLoja}` : lojas.length > 1 ? " · todas as lojas" : ""}
          </p>
        </div>
        <div className="acoes nao-imprimir">
          <label className="campo-inline">
            Dia
            <input type="date" value={dia} max={hojeLocal()} onChange={(e) => e.target.value && setDia(e.target.value)} />
          </label>
          {lojas.length > 1 && (
            <label className="campo-inline">
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
          <button type="button" className="botao-contorno" onClick={() => window.print()}>
            <Icone nome="recibo" /> Imprimir
          </button>
        </div>
      </div>
      {erro && <p className="erro">{erro}</p>}
      {!relatorio && !erro && <p className="vazio">Carregando...</p>}

      {relatorio && relatorio.caixas.length === 0 && (
        <section className="cartao espaco-acima">
          <p className="lista-vazia">Nenhum caixa foi aberto neste dia.</p>
        </section>
      )}

      {relatorio && relatorio.caixas.length > 0 && (
        <>
          {relatorio.abertos > 0 && (
            <p className="aviso-caixas-abertos">
              <Icone nome="alerta" tamanho={16} />
              {relatorio.abertos === 1 ? "1 caixa ainda está aberto" : `${relatorio.abertos} caixas ainda estão abertos`}. A
              conferência abaixo soma só os caixas já fechados.
            </p>
          )}
          <div className="indicadores espaco-acima">
            <div className="cartao indicador">
              <small>Vendido</small>
              <strong>{reais(relatorio.total_vendido)}</strong>
              <span>{relatorio.quantidade_vendas} venda(s)</span>
            </div>
            <div className="cartao indicador">
              <small>Caixas</small>
              <strong>{relatorio.caixas.length}</strong>
              <span>{relatorio.abertos ? `${relatorio.abertos} aberto(s)` : "todos fechados"}</span>
            </div>
            <div className="cartao indicador">
              <small>Sangrias</small>
              <strong>{reais(relatorio.sangrias)}</strong>
              <span>suprimentos {reais(relatorio.suprimentos)}</span>
            </div>
            <div className={`cartao indicador${diferenca !== 0 ? " indicador-alerta" : ""}`}>
              <small>Diferença</small>
              <strong className={diferenca < 0 ? "negativo" : diferenca > 0 ? "positivo" : ""}>{reais(diferenca, false)}</strong>
              <span>{diferenca === 0 ? "tudo bateu" : diferenca < 0 ? "faltou" : "sobrou"}</span>
            </div>
          </div>

          <div className="grade-dupla espaco-acima">
            <section className="cartao">
              <h2>Vendas por forma de pagamento</h2>
              <dl className="resumo">
                {Object.entries(relatorio.por_forma)
                  .sort((a, b) => Number(b[1]) - Number(a[1]))
                  .map(([forma, valor]) => (
                    <div key={forma}>
                      <dt>{NOMES_FORMA[forma] ?? forma}</dt>
                      <dd>{reais(valor)}</dd>
                    </div>
                  ))}
                <div className="resumo-total">
                  <dt>Total</dt>
                  <dd>{reais(relatorio.total_vendido)}</dd>
                </div>
              </dl>
              {(Number(relatorio.recebimentos_dinheiro) > 0 ||
                Number(relatorio.servicos_dinheiro) > 0 ||
                Number(relatorio.devolucoes_dinheiro) > 0) && (
                <dl className="resumo espaco-acima">
                  {Number(relatorio.recebimentos_dinheiro) > 0 && (
                    <div>
                      <dt>Fiado recebido em dinheiro</dt>
                      <dd>{reais(relatorio.recebimentos_dinheiro)}</dd>
                    </div>
                  )}
                  {Number(relatorio.servicos_dinheiro) > 0 && (
                    <div>
                      <dt>Serviços em dinheiro</dt>
                      <dd>{reais(relatorio.servicos_dinheiro)}</dd>
                    </div>
                  )}
                  {Number(relatorio.devolucoes_dinheiro) > 0 && (
                    <div>
                      <dt>Devolvido a clientes</dt>
                      <dd>-{reais(relatorio.devolucoes_dinheiro)}</dd>
                    </div>
                  )}
                </dl>
              )}
            </section>
            <section className="cartao">
              <h2>Conferência dos caixas fechados</h2>
              {relatorio.conferencia.length ? (
                <TabelaConferencia linhas={relatorio.conferencia} />
              ) : (
                <p className="lista-vazia">Nenhum caixa fechado ainda.</p>
              )}
            </section>
          </div>

          <section className="cartao espaco-acima">
            <h2>Caixas do dia</h2>
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>PDV</th>
                    {lojas.length > 1 && !lojaId && <th>Loja</th>}
                    <th>Operador</th>
                    <th>Horário</th>
                    <th className="num">Vendido</th>
                    <th className="num">Sangrias</th>
                    <th className="num">Diferença</th>
                    <th>Motivo</th>
                    <th className="nao-imprimir"></th>
                  </tr>
                </thead>
                <tbody>
                  {relatorio.caixas.map((c) => {
                    const dif = c.diferenca_total === null || c.diferenca_total === undefined ? null : Number(c.diferenca_total);
                    return (
                      <tr key={c.caixa.id}>
                        <td>
                          <strong>{c.terminal ?? "Sem PDV"}</strong>
                        </td>
                        {lojas.length > 1 && !lojaId && <td>{c.loja ?? "-"}</td>}
                        <td>{c.operador}</td>
                        <td>
                          {hora(c.caixa.aberto_em)} às {c.caixa.status === "aberto" ? <span className="etiqueta">aberto</span> : hora(c.caixa.fechado_em)}
                        </td>
                        <td className="num">{reais(c.total_vendido)}</td>
                        <td className="num">{Number(c.sangrias ?? 0) > 0 ? reais(c.sangrias ?? "0") : "-"}</td>
                        <td className="num">
                          {dif === null ? "-" : <span className={dif < 0 ? "negativo" : dif > 0 ? "positivo" : ""}>{reais(dif, false)}</span>}
                        </td>
                        <td className="motivo-diferenca">{c.caixa.observacao_fechamento ?? ""}</td>
                        <td className="num nao-imprimir">
                          <button type="button" className="botao-pequeno" onClick={() => setVendo(c)}>
                            Ver
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {vendo && <DetalheCaixa resumo={vendo} aoFechar={() => setVendo(null)} />}
    </div>
  );
}

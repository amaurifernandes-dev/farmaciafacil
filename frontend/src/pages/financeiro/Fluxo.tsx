import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { FluxoCaixa } from "../../api/tipos";
import SeletorLoja from "../../components/SeletorLoja";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";

function iso(dia: Date): string {
  return new Date(dia.getTime() - dia.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function periodo(opcao: string): [string, string] {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();
  switch (opcao) {
    case "este-mes":
      return [iso(new Date(ano, mes, 1)), iso(new Date(ano, mes + 1, 0))];
    case "mes-passado":
      return [iso(new Date(ano, mes - 1, 1)), iso(new Date(ano, mes, 0))];
    case "ultimos-30":
      return [iso(new Date(ano, mes, hoje.getDate() - 29)), iso(hoje)];
    default:
      return [iso(hoje), iso(new Date(ano, mes, hoje.getDate() + 29))];
  }
}

/** Entradas e saídas dia a dia: o que já aconteceu e o que vence. */
export default function Fluxo() {
  const lojas = useLojas();
  const [opcao, setOpcao] = useState("proximos-30");
  const [lojaId, setLojaId] = useState("");
  const [todosOsDias, setTodosOsDias] = useState(false);
  const [fluxo, setFluxo] = useState<FluxoCaixa | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const [inicio, fim] = periodo(opcao);
    const loja = lojaId ? `&loja_id=${lojaId}` : "";
    api<FluxoCaixa>(`/financeiro/fluxo?inicio=${inicio}&fim=${fim}${loja}`)
      .then((resposta) => {
        setFluxo(resposta);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }, [opcao, lojaId]);

  const hoje = iso(new Date());
  const dias = (fluxo?.dias ?? []).filter(
    (d) =>
      todosOsDias ||
      d.data === hoje ||
      [d.vendas, d.recebimentos, d.pagamentos, d.previsto_receber, d.previsto_pagar].some((v) => Number(v) !== 0),
  );
  const maior = Math.max(1, ...(fluxo?.dias ?? []).map((d) => Math.abs(Number(d.saldo))));

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Fluxo de caixa</h1>
          <p className="vazio">O que entrou e saiu, e o que ainda vai vencer, dia a dia.</p>
        </div>
      </div>

      <section className="cartao filtros-sugestao espaco-acima">
        <label className="seletor-loja">
          Período
          <select value={opcao} onChange={(e) => setOpcao(e.target.value)}>
            <option value="proximos-30">Próximos 30 dias</option>
            <option value="este-mes">Este mês</option>
            <option value="ultimos-30">Últimos 30 dias</option>
            <option value="mes-passado">Mês passado</option>
          </select>
        </label>
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Todas as lojas" />
        <label className="checkbox">
          <input type="checkbox" checked={todosOsDias} onChange={(e) => setTodosOsDias(e.target.checked)} />
          Mostrar dias sem movimento
        </label>
      </section>
      {erro && <p className="erro">{erro}</p>}

      {fluxo && (
        <>
          <div className="indicadores indicadores-financeiro espaco-acima">
            <div className="cartao indicador">
              <small>Entradas</small>
              <strong className="positivo">{reais(fluxo.entradas)}</strong>
            </div>
            <div className="cartao indicador">
              <small>Saídas</small>
              <strong className="negativo">{reais(fluxo.saidas)}</strong>
            </div>
            <div className="cartao indicador">
              <small>Resultado do período</small>
              <strong className={Number(fluxo.resultado) < 0 ? "negativo" : "positivo"}>{reais(fluxo.resultado)}</strong>
            </div>
            <div className="cartao indicador">
              <small>Atrasado antes do período</small>
              <strong>{reais(fluxo.vencido_pagar)}</strong>
              <small>a pagar · {reais(fluxo.vencido_receber)} a receber</small>
            </div>
          </div>

          <section className="cartao">
            {dias.length === 0 ? (
              <p className="lista-vazia">Nenhum movimento no período.</p>
            ) : (
              <div className="tabela-rolagem">
                <table className="tabela tabela-fluxo">
                  <thead>
                    <tr>
                      <th>Dia</th>
                      <th className="num">Vendas</th>
                      <th className="num">Recebido</th>
                      <th className="num">A receber</th>
                      <th className="num">Pago</th>
                      <th className="num">A pagar</th>
                      <th className="num">Saldo do dia</th>
                      <th className="grafico-saldo"></th>
                      <th className="num">Acumulado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dias.map((d) => {
                      const saldo = Number(d.saldo);
                      return (
                        <tr key={d.data} className={d.data === hoje ? "hoje" : ""}>
                          <td>
                            {data(d.data)}
                            {d.data === hoje && <span className="etiqueta">hoje</span>}
                          </td>
                          <Valor valor={d.vendas} />
                          <Valor valor={d.recebimentos} />
                          <Valor valor={d.previsto_receber} previsto />
                          <Valor valor={d.pagamentos} />
                          <Valor valor={d.previsto_pagar} previsto />
                          <td className={`num ${saldo < 0 ? "abaixo" : ""}`}>{reais(d.saldo)}</td>
                          <td className="grafico-saldo">
                            <span
                              className={saldo < 0 ? "barra-saida" : "barra-entrada"}
                              style={{ width: `${(Math.abs(saldo) / maior) * 100}%` }}
                            />
                          </td>
                          <td className={`num ${Number(d.acumulado) < 0 ? "abaixo" : ""}`}>{reais(d.acumulado)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="nota">
              “A receber” e “A pagar” são contas em aberto que vencem no dia. Vendas são o que entrou no caixa, sem a parte
              a prazo.
            </p>
          </section>
        </>
      )}
    </div>
  );
}

function Valor({ valor, previsto }: { valor: string; previsto?: boolean }) {
  if (Number(valor) === 0) return <td className="num vazio">-</td>;
  return <td className={`num ${previsto ? "previsto" : ""}`}>{reais(valor)}</td>;
}

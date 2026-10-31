import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, baixar, mensagem } from "../../api/cliente";
import type { Conta, MesPopular } from "../../api/tipos";
import Icone from "../../components/Icone";
import { data, quantidade, reais } from "../../formato";

function mesAtual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nomeDoMes(mes: string): string {
  const [ano, numero] = mes.split("-").map(Number);
  const nome = new Date(ano, numero - 1, 1).toLocaleString("pt-BR", { month: "long" });
  return `${nome} de ${ano}`;
}

function cpf(valor: string): string {
  return valor.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
}

/** Farmácia Popular: as vendas do mês e o que o governo tem a pagar para a farmácia. */
export default function Popular() {
  const [mes, setMes] = useState(mesAtual);
  const [resumo, setResumo] = useState<MesPopular | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  function carregar() {
    api<MesPopular>(`/popular?mes=${mes}`)
      .then(setResumo)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }
  useEffect(carregar, [mes]);

  async function acao(fazer: () => Promise<string | void>) {
    setOcupado(true);
    setAviso(null);
    try {
      const texto = await fazer();
      if (texto) setAviso({ tipo: "ok", texto });
      carregar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    } finally {
      setOcupado(false);
    }
  }

  const recebido = resumo?.lancamentos.filter((c) => c.status === "paga").reduce((s, c) => s + Number(c.valor_pago ?? c.valor), 0) ?? 0;

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Programa do governo</p>
          <h1>Farmácia Popular</h1>
          <p className="vazio">
            O governo paga parte dos remédios do programa e repassa para a farmácia no mês seguinte. No caixa, use
            Alt+7 no pagamento.
          </p>
        </div>
        <label className="seletor-loja">
          Mês
          <input type="month" value={mes} max={mesAtual()} onChange={(e) => e.target.value && setMes(e.target.value)} />
        </label>
      </div>

      {resumo && (
        <div className="indicadores indicadores-financeiro">
          <div className="cartao indicador">
            <small>O governo deve pagar</small>
            <strong>{reais(resumo.total_governo)}</strong>
            <span>em {nomeDoMes(resumo.mes)}</span>
          </div>
          <div className="cartao indicador">
            <small>Ainda não lançado no Financeiro</small>
            <strong>{reais(resumo.em_aberto)}</strong>
            <span>{resumo.vendas.filter((v) => v.status === "aberta").length} venda(s)</span>
          </div>
          <div className="cartao indicador">
            <small>Vendas pelo programa</small>
            <strong>{resumo.quantidade}</strong>
            <span>{resumo.pacientes} paciente(s)</span>
          </div>
          <div className="cartao indicador">
            <small>Os pacientes pagaram</small>
            <strong>{reais(resumo.total_paciente)}</strong>
            <span>{recebido ? `governo já pagou ${reais(recebido, false)}` : "a diferença do preço"}</span>
          </div>
        </div>
      )}

      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}

      {resumo && (
        <div className="cartao cartao-separado">
          <div className="cartao-cabecalho">
            <h2>Cobrar o governo</h2>
            <small>vira uma conta a receber</small>
          </div>
          <div className="barra filtros-relatorio">
            <button
              type="button"
              className="botao"
              disabled={ocupado || !resumo.pode_lancar}
              onClick={() =>
                acao(async () => {
                  const conta = await api<Conta>("/popular/lancar", { corpo: { mes } });
                  return `Lançado ${reais(conta.valor)} a receber do Ministério da Saúde, para ${data(conta.vencimento)}. Está em Financeiro > A receber.`;
                })
              }
            >
              <Icone nome="recibo" />
              Lançar {reais(resumo.em_aberto)} no Financeiro
            </button>
            <button
              type="button"
              className="botao-pequeno"
              disabled={resumo.quantidade === 0}
              onClick={() => acao(() => baixar(`/popular/planilha?mes=${mes}`))}
            >
              Planilha do mês
            </button>
          </div>
          <p className="nota">
            Confira a planilha com o extrato do Ministério. Guarde a receita e o comprovante assinado de cada venda por 5
            anos: a auditoria do programa pede.
          </p>

          {resumo.lancamentos.length > 0 && (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Lançamento</th>
                  <th className="num">Valor</th>
                  <th>Previsão</th>
                  <th>Situação</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {resumo.lancamentos.map((c) => (
                  <tr key={c.id}>
                    <td>{c.descricao}</td>
                    <td className="num">{reais(c.valor)}</td>
                    <td>{data(c.vencimento)}</td>
                    <td>
                      {c.status === "paga" ? (
                        <span className="etiqueta ok">Recebido em {data(c.pago_em)}</span>
                      ) : c.status === "cancelada" ? (
                        <span className="etiqueta">Desfeito</span>
                      ) : c.vencida ? (
                        <span className="etiqueta erro-etiqueta">Atrasado</span>
                      ) : (
                        <span className="etiqueta">A receber</span>
                      )}
                    </td>
                    <td className="num acoes-linha">
                      {c.status === "aberta" && (
                        <button
                          type="button"
                          className="botao-pequeno"
                          disabled={ocupado}
                          onClick={() =>
                            acao(async () => {
                              await api(`/popular/lancamentos/${c.id}/desfazer`, { metodo: "POST" });
                              return "Lançamento desfeito. As vendas voltaram a ficar em aberto.";
                            })
                          }
                        >
                          Desfazer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {resumo && (
        <div className="cartao cartao-separado">
          <div className="cartao-cabecalho">
            <h2>Vendas de {nomeDoMes(resumo.mes)}</h2>
            <small>
              <Link to="/configuracoes/produtos">quais remédios estão no programa</Link>
            </small>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Data</th>
                <th>Paciente</th>
                <th>Remédios</th>
                <th>Autorização</th>
                <th className="num">Governo</th>
                <th className="num">Paciente</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {resumo.vendas.map((v) => (
                <tr key={v.id}>
                  <td>
                    {data(v.data)}
                    <span className="livro-detalhe">venda nº {v.numero}</span>
                  </td>
                  <td>
                    {v.paciente_nome}
                    <span className="livro-detalhe">CPF {cpf(v.paciente_cpf)}</span>
                  </td>
                  <td>
                    {v.itens.map((i) => (
                      <div key={i.produto_id}>
                        {quantidade(i.quantidade)} × {i.descricao}
                      </div>
                    ))}
                    <span className="livro-detalhe">
                      CRM {v.prescritor_crm}/{v.prescritor_uf} · receita de {data(v.receita_data)}
                    </span>
                  </td>
                  <td>
                    {v.autorizacao}
                    {v.status === "lancada" && <span className="livro-detalhe">lançada</span>}
                  </td>
                  <td className="num">{reais(v.valor_governo)}</td>
                  <td className="num">{reais(v.valor_paciente)}</td>
                  <td className="num">
                    <a className="botao-pequeno" href={`/popular/comprovante/${v.venda_id}`} target="_blank" rel="noreferrer">
                      Comprovante
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {resumo.vendas.length === 0 && (
            <p className="lista-vazia">
              Nenhuma venda pela Farmácia Popular neste mês. Marque os remédios do programa no cadastro do produto e use
              Alt+7 no pagamento do caixa.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

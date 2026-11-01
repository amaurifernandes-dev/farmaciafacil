import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { EnvioRecusado, PainelOffline } from "../../api/tipos";
import { quantidade as fmtQtd, reais } from "../../formato";

const TIPOS: Record<EnvioRecusado["tipo"], string> = {
  venda: "Venda",
  abrir: "Abertura do caixa",
  fechar: "Fechamento do caixa",
};

function dataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Quanto tempo depois de feita a venda chegou ao sistema. */
export function atraso(feita: string, chegou: string): string {
  const minutos = Math.max(
    0,
    Math.round(
      (new Date(chegou).getTime() - new Date(feita).getTime()) / 60000,
    ),
  );
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 48)
    return `${horas} h ${minutos % 60 ? `${minutos % 60} min` : ""}`.trim();
  return `${Math.floor(horas / 24)} dias`;
}

function isoDe(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return d.toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso do computador
}

/** Painel do gerente: o que os caixas fizeram sem internet e o que precisa de atenção. */
export default function SemInternet() {
  const [dias, setDias] = useState("30");
  const [painel, setPainel] = useState<PainelOffline | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    try {
      setPainel(
        await api<PainelOffline>(`/vendas-offline?de=${isoDe(Number(dias))}`),
      );
      setErro("");
    } catch (e) {
      setErro(mensagem(e));
    }
  }, [dias]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function resolver(id: string) {
    try {
      await api(`/vendas-offline/recusas/${id}/resolver`, { corpo: {} });
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Caixas</p>
          <h1>Vendas sem internet</h1>
          <p className="vazio">
            O que os caixas fizeram enquanto a internet estava fora, e o que
            precisa da sua atenção.
          </p>
        </div>
      </div>
      <div className="barra filtros-relatorio">
        <label className="seletor-loja">
          Período
          <select value={dias} onChange={(e) => setDias(e.target.value)}>
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
        </label>
      </div>
      {erro && <p className="erro">{erro}</p>}
      {!painel ? (
        !erro && <p className="vazio">Carregando...</p>
      ) : (
        <Conteudo painel={painel} aoResolver={resolver} />
      )}
    </div>
  );
}

function Conteudo({
  painel,
  aoResolver,
}: {
  painel: PainelOffline;
  aoResolver: (id: string) => void;
}) {
  const { resumo } = painel;
  const pendentes = painel.recusas.filter((r) => !r.resolvido_em);
  const resolvidas = painel.recusas.filter((r) => r.resolvido_em);
  return (
    <>
      <div className="indicadores indicadores-financeiro">
        <Indicador titulo="Vendas sem internet" valor={String(resumo.vendas)}>
          {reais(resumo.total)} no período
        </Indicador>
        <Indicador
          titulo="Recusadas para resolver"
          valor={String(resumo.recusas_pendentes)}
          alerta={resumo.recusas_pendentes > 0}
        >
          {resumo.recusas_pendentes
            ? "Não entraram no sistema"
            : "Nenhuma pendente"}
        </Indicador>
        <Indicador
          titulo="Vendidos sem estoque"
          valor={String(resumo.itens_sem_estoque)}
          alerta={resumo.itens_sem_estoque > 0}
        >
          {resumo.itens_sem_estoque
            ? "Confira o estoque desses produtos"
            : "Estoque bateu"}
        </Indicador>
        <Indicador titulo="Caixas sem internet" valor={String(resumo.caixas)}>
          Abertos ou fechados sem internet
        </Indicador>
      </div>

      <div className="cartao">
        <div className="cartao-cabecalho">
          <h2>Recusadas para resolver</h2>
          <small>
            Feitas sem internet que o sistema não aceitou quando chegaram
          </small>
        </div>
        {pendentes.length === 0 ? (
          <p className="vazio">
            Nenhum envio recusado. Tudo o que foi feito sem internet entrou no
            sistema.
          </p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>O quê</th>
                  <th>Feito em</th>
                  <th>PDV</th>
                  <th>Operador</th>
                  <th className="num">Valor</th>
                  <th>Motivo</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pendentes.map((r) => (
                  <tr key={r.id}>
                    <td>{TIPOS[r.tipo]}</td>
                    <td>{dataHora(r.feito_em)}</td>
                    <td>{r.terminal ?? "-"}</td>
                    <td>{r.operador}</td>
                    <td className="num">
                      {r.tipo === "venda" ? reais(r.total) : "-"}
                    </td>
                    <td className="texto-erro">{r.motivo}</td>
                    <td>
                      <button
                        type="button"
                        className="botao-pequeno"
                        onClick={() => aoResolver(r.id)}
                      >
                        Já resolvi
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="nota">
          Depois de acertar o motivo (por exemplo, abrir o caixa certo), o
          operador aperta "Tentar de novo" no PDV e o envio sai daqui sozinho.
          Se você lançou a venda à mão, marque "Já resolvi".
        </p>
        {resolvidas.length > 0 && (
          <details>
            <summary>{resolvidas.length} resolvida(s) no período</summary>
            <ul className="lista-simples">
              {resolvidas.map((r) => (
                <li key={r.id}>
                  {TIPOS[r.tipo]} de {dataHora(r.feito_em)} ({r.operador}):{" "}
                  {r.resolucao === "enviada"
                    ? "entrou depois"
                    : "resolvida à mão"}{" "}
                  em {dataHora(r.resolvido_em!)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      <div className="cartao">
        <div className="cartao-cabecalho">
          <h2>Vendidos sem estoque no sistema</h2>
          <small>
            O caixa vendeu sem internet e o sistema não tinha saldo: o estoque
            real estava maior
          </small>
        </div>
        {painel.sem_estoque.length === 0 ? (
          <p className="vazio">
            Nenhum produto vendido além do saldo do sistema.
          </p>
        ) : (
          <>
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th className="num">Qtd. sem saldo</th>
                    <th>Venda</th>
                    <th>Feita em</th>
                  </tr>
                </thead>
                <tbody>
                  {painel.sem_estoque.map((i) => (
                    <tr key={`${i.venda_id}-${i.produto}`}>
                      <td>{i.produto}</td>
                      <td className="num">{fmtQtd(i.quantidade)}</td>
                      <td>nº {i.numero}</td>
                      <td>{dataHora(i.feita_em)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="nota">
              Conte esses produtos na prateleira e acerte o saldo no{" "}
              <Link to="/estoque/inventario">inventário</Link>.
            </p>
          </>
        )}
      </div>

      <div className="cartao">
        <div className="cartao-cabecalho">
          <h2>Vendas feitas sem internet</h2>
          <small>
            {painel.vendas.length} venda(s)
            {painel.vendas.length >= 200
              ? " (mostrando as 200 mais recentes)"
              : ""}
          </small>
        </div>
        {painel.vendas.length === 0 ? (
          <p className="vazio">Nenhuma venda sem internet no período.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nº</th>
                  <th>Feita em</th>
                  <th>Chegou</th>
                  <th>PDV</th>
                  <th>Operador</th>
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {painel.vendas.map((v) => (
                  <tr key={v.id}>
                    <td>
                      {v.numero}
                      {v.status === "cancelada" && (
                        <small className="texto-erro"> cancelada</small>
                      )}
                    </td>
                    <td>{dataHora(v.feita_em)}</td>
                    <td>{atraso(v.feita_em, v.chegou_em)} depois</td>
                    <td>{v.terminal ?? "-"}</td>
                    <td>{v.operador}</td>
                    <td className="num">{reais(v.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function Indicador({
  titulo,
  valor,
  alerta,
  children,
}: {
  titulo: string;
  valor: string;
  alerta?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={`cartao indicador${alerta ? " indicador-alerta" : ""}`}>
      <small>{titulo}</small>
      <strong>{valor}</strong>
      <small>{children}</small>
    </div>
  );
}

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ErroApi, lerChaveTerminal, mensagem, salvarChaveTerminal } from "../../api/cliente";
import type { EsteTerminal, Loja, ResumoCaixa, Terminal } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import { reais } from "../../formato";
import { ehGerente, useSessao } from "../../sessao";
import { paraCentavos } from "../pdv/carrinho";

function dataHora(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Lê qual PDV é este computador. null = não registrado. */
export async function lerEsteTerminal(): Promise<EsteTerminal | null> {
  if (!lerChaveTerminal()) return null;
  try {
    return await api<EsteTerminal>("/terminais/este");
  } catch (e) {
    if (e instanceof ErroApi && e.status === 404) {
      // A chave foi revogada (outro computador assumiu este PDV).
      salvarChaveTerminal(null);
      return null;
    }
    throw e;
  }
}

export default function Caixas() {
  const { sessao } = useSessao();
  const gerente = ehGerente(sessao);
  const [este, setEste] = useState<EsteTerminal | null | undefined>(undefined);
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [terminais, setTerminais] = useState<Terminal[]>([]);
  const [abertos, setAbertos] = useState<ResumoCaixa[]>([]);
  const [fechados, setFechados] = useState<ResumoCaixa[]>([]);
  const [fechando, setFechando] = useState<ResumoCaixa | null>(null);
  const [novoPdv, setNovoPdv] = useState(false);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    try {
      setEste(await lerEsteTerminal());
      setLojas(await api<Loja[]>("/lojas"));
      if (gerente) {
        const [t, a, f] = await Promise.all([
          api<Terminal[]>("/terminais"),
          api<ResumoCaixa[]>("/caixas?situacao=aberto"),
          api<ResumoCaixa[]>("/caixas?situacao=fechado&por_pagina=10"),
        ]);
        setTerminais(t);
        setAbertos(a);
        setFechados(f);
      } else {
        const meu = await api<ResumoCaixa>("/caixas/atual").catch(() => null);
        setAbertos(meu ? [meu] : []);
      }
    } catch (e) {
      setErro(mensagem(e));
    }
  }, [gerente]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function registrarEste(terminalId: string) {
    try {
      const { chave } = await api<{ chave: string }>(`/terminais/${terminalId}/vincular`, { corpo: {} });
      salvarChaveTerminal(chave);
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  async function acaoTerminal(terminal: Terminal, acao: "desvincular" | "ativar" | "desativar") {
    try {
      if (acao === "desvincular") await api(`/terminais/${terminal.id}/desvincular`, { corpo: {} });
      else await api(`/terminais/${terminal.id}`, { metodo: "PATCH", corpo: { ativo: acao === "ativar" } });
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  const nomeLoja = (id: string | null) => lojas.find((l) => l.id === id)?.nome ?? "-";

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Gestão de caixas</h1>
          <p className="vazio">Os computadores que recebem pagamentos, quem está com o caixa aberto e os fechamentos.</p>
        </div>
        {este?.pode_receber && (
          <Link to="/pdv" className="botao">
            <Icone nome="caixa" /> Abrir frente de caixa
          </Link>
        )}
      </div>
      {erro && <p className="erro">{erro}</p>}

      <EsteComputador
        este={este}
        gerente={gerente}
        terminais={terminais}
        nomeLoja={nomeLoja}
        aoRegistrar={registrarEste}
        aoCriar={() => setNovoPdv(true)}
      />

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>{gerente ? "Caixas abertos agora" : "Meu caixa"}</h2>
          <small>{abertos.length} aberto(s)</small>
        </div>
        {abertos.length === 0 ? (
          <p className="lista-vazia">Nenhum caixa aberto.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>PDV</th>
                  <th>Loja</th>
                  <th>Operador</th>
                  <th>Aberto em</th>
                  <th className="num">Vendas</th>
                  <th className="num">Total</th>
                  <th className="num">Dinheiro na gaveta</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {abertos.map((c) => (
                  <tr key={c.caixa.id}>
                    <td>
                      <strong>{c.terminal ?? "Sem PDV"}</strong>
                    </td>
                    <td>{c.loja ?? "-"}</td>
                    <td>{c.operador}</td>
                    <td>
                      {dataHora(c.caixa.aberto_em)}
                      {c.caixa.aberto_offline && <small className="selo-offline">sem internet</small>}
                    </td>
                    <td className="num">{c.quantidade_vendas}</td>
                    <td className="num">{reais(c.total_vendido)}</td>
                    <td className="num">{reais(c.dinheiro_esperado)}</td>
                    <td className="num">
                      <button type="button" className="botao-pequeno" onClick={() => setFechando(c)}>
                        Fechar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {gerente && (
        <section className="cartao espaco-acima">
          <div className="cartao-cabecalho">
            <h2>PDVs cadastrados</h2>
            <button type="button" className="botao-pequeno" onClick={() => setNovoPdv(true)}>
              <Icone nome="mais" tamanho={14} /> Novo PDV
            </button>
          </div>
          {terminais.length === 0 ? (
            <p className="lista-vazia">Nenhum PDV ainda. Cadastre o primeiro e registre o computador do caixa.</p>
          ) : (
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>PDV</th>
                    <th>Loja</th>
                    <th>Recebe pagamentos</th>
                    <th>Computador</th>
                    <th>Último uso</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {terminais.map((t) => (
                    <tr key={t.id} className={t.ativo ? "" : "inativo"}>
                      <td>
                        <strong>{t.nome}</strong> {t.central && <span className="etiqueta">Central</span>}
                        {este?.terminal.id === t.id && <span className="etiqueta ok">Este computador</span>}
                      </td>
                      <td>{nomeLoja(t.loja_id)}</td>
                      <td>{!t.ativo ? "Desativado" : t.pode_receber ? "Sim" : "Não (monocaixa)"}</td>
                      <td>{t.vinculado ? `Registrado em ${dataHora(t.vinculado_em)}` : "Nenhum computador"}</td>
                      <td>{dataHora(t.ultimo_uso_em)}</td>
                      <td className="num acoes-tabela">
                        {t.vinculado && (
                          <button type="button" className="botao-pequeno" onClick={() => acaoTerminal(t, "desvincular")}>
                            Desvincular
                          </button>
                        )}
                        <button
                          type="button"
                          className="botao-pequeno"
                          onClick={() => acaoTerminal(t, t.ativo ? "desativar" : "ativar")}
                        >
                          {t.ativo ? "Desativar" : "Ativar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="nota">
            Monocaixa ou multicaixa e o PDV central de cada loja ficam em{" "}
            <Link to="/configuracoes/gerais">Configurações gerais</Link>.
          </p>
        </section>
      )}

      {gerente && fechados.length > 0 && (
        <section className="cartao espaco-acima">
          <h2>Últimos fechamentos</h2>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>PDV</th>
                  <th>Operador</th>
                  <th>Fechado em</th>
                  <th className="num">Total vendido</th>
                  <th className="num">Diferença</th>
                </tr>
              </thead>
              <tbody>
                {fechados.map((c) => {
                  const diferenca = Number(c.diferenca ?? 0);
                  return (
                    <tr key={c.caixa.id}>
                      <td>{c.terminal ?? "-"}</td>
                      <td>{c.operador}</td>
                      <td>
                        {dataHora(c.caixa.fechado_em)}
                        {(c.caixa.aberto_offline || c.caixa.fechado_offline) && <small className="selo-offline">sem internet</small>}
                      </td>
                      <td className="num">{reais(c.total_vendido)}</td>
                      <td className={`num ${diferenca < 0 ? "negativo" : diferenca > 0 ? "positivo" : ""}`}>
                        {reais(c.diferenca ?? "0")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {fechando && (
        <FecharNaGestao
          caixa={fechando}
          aoFechar={() => {
            setFechando(null);
            carregar();
          }}
        />
      )}
      {novoPdv && (
        <NovoPdv
          lojas={lojas.filter((l) => l.ativo)}
          esteRegistrado={Boolean(este)}
          aoFechar={() => setNovoPdv(false)}
          aoCriar={async (terminal, registrar) => {
            setNovoPdv(false);
            if (registrar) await registrarEste(terminal.id);
            else carregar();
          }}
        />
      )}
    </div>
  );
}

function EsteComputador({
  este,
  gerente,
  terminais,
  nomeLoja,
  aoRegistrar,
  aoCriar,
}: {
  este: EsteTerminal | null | undefined;
  gerente: boolean;
  terminais: Terminal[];
  nomeLoja: (id: string) => string;
  aoRegistrar: (terminalId: string) => void;
  aoCriar: () => void;
}) {
  const [escolhido, setEscolhido] = useState("");
  if (este === undefined) return <section className="cartao">Verificando este computador...</section>;

  if (este) {
    return (
      <section className="cartao este-computador">
        <span className="atalho-icone">
          <Icone nome="monitor" />
        </span>
        <div>
          <p className="sobretitulo">Este computador</p>
          <h2>
            {este.terminal.nome} · {este.loja.nome}
          </h2>
          <p className={este.pode_receber ? "positivo" : "vazio"}>
            {este.pode_receber
              ? `Pode abrir caixa e receber (${este.loja.modo_caixa === "mono" ? "PDV central do monocaixa" : "multicaixa"}).`
              : este.motivo}
          </p>
        </div>
        {!este.pode_receber && (
          <Link to="/vendas/pre-venda" className="botao-contorno">
            Fazer pré-venda
          </Link>
        )}
      </section>
    );
  }

  const livres = terminais.filter((t) => t.ativo);
  return (
    <section className="cartao este-computador">
      <span className="atalho-icone">
        <Icone nome="monitor" />
      </span>
      <div>
        <p className="sobretitulo">Este computador</p>
        <h2>Não está registrado como PDV</h2>
        <p className="vazio">
          {gerente
            ? "Se este é um computador de caixa, registre-o abaixo. Só computadores registrados podem abrir caixa."
            : "Para abrir caixa aqui, peça a um gerente para registrar este computador. Você ainda pode fazer pré-vendas."}
        </p>
        {gerente && (
          <div className="acoes">
            {livres.length > 0 && (
              <>
                <select value={escolhido} onChange={(e) => setEscolhido(e.target.value)}>
                  <option value="">Escolha o PDV</option>
                  {livres.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nome} ({nomeLoja(t.loja_id)}){t.vinculado ? " - já tem computador" : ""}
                    </option>
                  ))}
                </select>
                <button type="button" disabled={!escolhido} onClick={() => aoRegistrar(escolhido)}>
                  Registrar este computador
                </button>
              </>
            )}
            <button type="button" className="botao-secundario" onClick={aoCriar}>
              <Icone nome="mais" tamanho={14} /> Novo PDV
            </button>
          </div>
        )}
        {gerente && livres.find((t) => t.id === escolhido)?.vinculado && (
          <p className="nota">O computador que usava este PDV vai perder o acesso de caixa.</p>
        )}
      </div>
    </section>
  );
}

function NovoPdv({
  lojas,
  esteRegistrado,
  aoFechar,
  aoCriar,
}: {
  lojas: Loja[];
  esteRegistrado: boolean;
  aoFechar: () => void;
  aoCriar: (terminal: Terminal, registrarEste: boolean) => void;
}) {
  const [lojaId, setLojaId] = useState(lojas[0]?.id ?? "");
  const [nome, setNome] = useState("PDV 01");
  const [registrar, setRegistrar] = useState(!esteRegistrado);
  const [erro, setErro] = useState("");

  async function criar(evento: FormEvent) {
    evento.preventDefault();
    try {
      aoCriar(await api<Terminal>("/terminais", { corpo: { loja_id: lojaId, nome } }), registrar);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Novo PDV" aoFechar={aoFechar}>
      <form className="campos" onSubmit={criar}>
        <label>
          Nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} required autoFocus />
        </label>
        <label>
          Loja
          <select value={lojaId} onChange={(e) => setLojaId(e.target.value)}>
            {lojas.map((l) => (
              <option key={l.id} value={l.id}>
                {l.nome}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox caixa-marcacao largo">
          <input type="checkbox" checked={registrar} onChange={(e) => setRegistrar(e.target.checked)} />
          <span>
            Registrar este computador como {nome || "o novo PDV"}
            <small>Deixe desmarcado para registrar depois, abrindo o sistema no computador do caixa.</small>
          </span>
        </label>
        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit">Criar PDV</button>
        </div>
      </form>
    </Janela>
  );
}

function FecharNaGestao({ caixa, aoFechar }: { caixa: ResumoCaixa; aoFechar: () => void }) {
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState("");
  const [resumo, setResumo] = useState<ResumoCaixa | null>(null);

  async function fechar(evento: FormEvent) {
    evento.preventDefault();
    const centavos = paraCentavos(valor);
    if (centavos === null) return setErro("Informe o dinheiro contado na gaveta");
    try {
      setResumo(
        await api<ResumoCaixa>(`/caixas/${caixa.caixa.id}/fechar`, {
          corpo: { valor_fechamento_informado: (centavos / 100).toFixed(2) },
        }),
      );
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo={`Fechar caixa · ${caixa.terminal ?? ""} · ${caixa.operador}`} aoFechar={aoFechar}>
      {resumo ? (
        <>
          <p className={Number(resumo.diferenca) === 0 ? "ok" : "erro"}>
            Caixa fechado. Diferença: {reais(resumo.diferenca ?? "0")}
          </p>
          <div className="acoes direita">
            <button type="button" onClick={aoFechar}>
              OK
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={fechar} className="campos">
          <p className="largo">
            Vendas: {caixa.quantidade_vendas} · {reais(caixa.total_vendido)}. Dinheiro esperado na gaveta:{" "}
            <strong>{reais(caixa.dinheiro_esperado)}</strong>
          </p>
          <label className="largo">
            Dinheiro contado na gaveta (R$)
            <input value={valor} onChange={(e) => setValor(e.target.value)} autoFocus inputMode="decimal" />
          </label>
          {erro && <p className="erro largo">{erro}</p>}
          <div className="acoes largo direita">
            <button type="button" onClick={aoFechar}>
              Cancelar
            </button>
            <button type="submit">Fechar caixa</button>
          </div>
        </form>
      )}
    </Janela>
  );
}

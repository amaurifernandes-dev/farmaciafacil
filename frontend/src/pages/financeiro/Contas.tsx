import { useCallback, useEffect, useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Categorias, Conta, PaginaContas, SituacaoConta, TipoConta } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { CopiarCodigo, LancarBoleto, SemanaPagar } from "./Boleto";

const TEXTOS = {
  pagar: {
    titulo: "Contas a pagar",
    descricao: "Boletos de fornecedores, aluguel, salários e outras despesas. As notas de compra entram aqui sozinhas.",
    pessoa: "Fornecedor",
    baixar: "Pagar",
    pago: "Pago no mês",
  },
  receber: {
    titulo: "Contas a receber",
    descricao: "Vendas a prazo (fiado), convênios e outras receitas.",
    pessoa: "Cliente",
    baixar: "Receber",
    pago: "Recebido no mês",
  },
} as const;

export const FORMAS_BAIXA: Record<string, string> = {
  dinheiro: "Dinheiro",
  pix: "Pix",
  boleto: "Boleto",
  transferencia: "Transferência",
  debito: "Cartão de débito",
  credito: "Cartão de crédito",
  cheque: "Cheque",
};

const SITUACOES: { valor: SituacaoConta; rotulo: string }[] = [
  { valor: "abertas", rotulo: "Em aberto" },
  { valor: "vencidas", rotulo: "Vencidas" },
  { valor: "pagas", rotulo: "Pagas" },
  { valor: "canceladas", rotulo: "Canceladas" },
  { valor: "todas", rotulo: "Todas" },
];

function hojeIso(): string {
  const agora = new Date();
  return new Date(agora.getTime() - agora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function paraApi(valor: string): string {
  return valor.includes(",") ? valor.replace(/\./g, "").replace(",", ".") : valor;
}

export default function Contas({ tipo }: { tipo: TipoConta }) {
  const textos = TEXTOS[tipo];
  const lojas = useLojas();
  const [situacao, setSituacao] = useState<SituacaoConta>("abertas");
  const [busca, setBusca] = useState("");
  const [lojaId, setLojaId] = useState("");
  const [pagina, setPagina] = useState<PaginaContas | null>(null);
  const [categorias, setCategorias] = useState<Categorias | null>(null);
  const [baixando, setBaixando] = useState<Conta | null>(null);
  const [editando, setEditando] = useState<Conta | null>(null);
  const [novaConta, setNovaConta] = useState(false);
  const [lancandoBoleto, setLancandoBoleto] = useState(false);
  const [versao, setVersao] = useState(0);
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    const parametros = new URLSearchParams({ tipo, situacao, busca: busca.trim() });
    if (lojaId) parametros.set("loja_id", lojaId);
    api<PaginaContas>(`/financeiro/contas?${parametros}`)
      .then((resposta) => {
        setPagina(resposta);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }, [tipo, situacao, busca, lojaId]);

  useEffect(() => {
    const espera = setTimeout(carregar, 250);
    return () => clearTimeout(espera);
  }, [carregar]);

  useEffect(() => {
    api<Categorias>("/financeiro/categorias").then(setCategorias).catch(() => setCategorias(null));
  }, []);

  /** Depois de lançar, pagar ou editar: recarrega a lista e a semana. */
  function atualizar(mensagemOk = "") {
    carregar();
    setVersao((v) => v + 1);
    setAviso(mensagemOk);
  }

  const nomeCategoria = (id: string) => categorias?.[tipo].find((c) => c.id === id)?.nome ?? id;

  async function acao(conta: Conta, caminho: "estornar" | "cancelar") {
    try {
      await api(`/financeiro/contas/${conta.id}/${caminho}`, { corpo: {} });
      atualizar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  const totais = pagina?.totais;

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>{textos.titulo}</h1>
          <p className="vazio">{textos.descricao}</p>
        </div>
        <div className="acoes">
          {tipo === "pagar" && (
            <button type="button" className="botao" onClick={() => setLancandoBoleto(true)}>
              <Icone nome="recibo" /> Lançar boleto
            </button>
          )}
          <button type="button" className={tipo === "pagar" ? "botao-contorno" : "botao"} onClick={() => setNovaConta(true)}>
            <Icone nome="mais" /> Nova conta
          </button>
        </div>
      </div>
      {aviso && (
        <p className="ok" role="status">
          {aviso}
        </p>
      )}

      {totais && (
        <div className="indicadores indicadores-financeiro">
          <button
            type="button"
            className={`cartao indicador ${Number(totais.vencidas) > 0 ? "indicador-alerta" : ""}`}
            onClick={() => setSituacao("vencidas")}
          >
            <small>Vencidas</small>
            <strong>{reais(totais.vencidas)}</strong>
            <small>{totais.quantidade_vencidas} conta(s)</small>
          </button>
          <div className="cartao indicador">
            <small>Vence hoje</small>
            <strong>{reais(totais.vence_hoje)}</strong>
          </div>
          <div className="cartao indicador">
            <small>Próximos 7 dias</small>
            <strong>{reais(totais.proximos_7_dias)}</strong>
          </div>
          <div className="cartao indicador">
            <small>{textos.pago}</small>
            <strong>{reais(totais.pago_no_mes)}</strong>
          </div>
        </div>
      )}

      {tipo === "pagar" && <SemanaPagar versao={versao} aoPagar={setBaixando} />}

      <section className="cartao espaco-acima">
        <div className="barra filtros-contas">
          <select value={situacao} onChange={(e) => setSituacao(e.target.value as SituacaoConta)}>
            {SITUACOES.map((s) => (
              <option key={s.valor} value={s.valor}>
                {s.rotulo}
              </option>
            ))}
          </select>
          <input placeholder={`Buscar por descrição, documento ou ${textos.pessoa.toLowerCase()}`} value={busca} onChange={(e) => setBusca(e.target.value)} />
          {lojas.length > 1 && (
            <select value={lojaId} onChange={(e) => setLojaId(e.target.value)}>
              <option value="">Todas as lojas</option>
              {lojas.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          )}
        </div>
        {erro && <p className="erro">{erro}</p>}

        {pagina && pagina.itens.length === 0 ? (
          <p className="lista-vazia">Nenhuma conta nesta situação.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>{situacao === "pagas" ? "Pago em" : "Vencimento"}</th>
                  <th>Descrição</th>
                  <th>{textos.pessoa}</th>
                  <th>Categoria</th>
                  <th className="num">Valor</th>
                  <th>Situação</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pagina?.itens.map((c) => (
                  <tr key={c.id} className={c.status === "cancelada" ? "inativo" : ""}>
                    <td className={c.vencida ? "abaixo" : ""}>{data(situacao === "pagas" ? c.pago_em : c.vencimento)}</td>
                    <td>
                      {c.descricao}
                      <br />
                      <small>
                        {c.parcelas > 1 && `Parcela ${c.parcela}/${c.parcelas}`}
                        {c.parcelas > 1 && c.documento && " · "}
                        {c.documento && `Doc. ${c.documento}`}
                        {c.linha_digitavel && (
                          <span className="etiqueta etiqueta-neutra etiqueta-boleto" title={c.linha_digitavel}>
                            boleto
                          </span>
                        )}
                      </small>
                    </td>
                    <td>{c.pessoa ?? "-"}</td>
                    <td>
                      <small>{nomeCategoria(c.categoria)}</small>
                    </td>
                    <td className="num">
                      {reais(c.status === "paga" && c.valor_pago ? c.valor_pago : c.valor)}
                    </td>
                    <td>
                      <Situacao conta={c} />
                    </td>
                    <td className="acoes-tabela">
                      {c.status === "aberta" && (
                        <>
                          <CopiarCodigo conta={c} />
                          <button type="button" className="botao-pequeno" onClick={() => setBaixando(c)}>
                            {textos.baixar}
                          </button>
                          <button type="button" className="botao-pequeno" onClick={() => setEditando(c)}>
                            Editar
                          </button>
                          {!c.venda_id && (
                            <button type="button" className="botao-pequeno" onClick={() => acao(c, "cancelar")}>
                              Cancelar
                            </button>
                          )}
                        </>
                      )}
                      {c.status === "paga" && (
                        <button type="button" className="botao-pequeno" onClick={() => acao(c, "estornar")}>
                          Estornar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pagina && pagina.total > 0 && (
          <p className="rodape">
            {pagina.total} conta(s) · total {reais(pagina.soma)}
          </p>
        )}
      </section>

      {baixando && (
        <Baixar
          conta={baixando}
          rotulo={textos.baixar}
          aoFechar={() => setBaixando(null)}
          aoSalvar={() => {
            setBaixando(null);
            atualizar(`${baixando.descricao}: ${tipo === "pagar" ? "paga" : "recebida"}.`);
          }}
        />
      )}
      {editando && categorias && (
        <Editar
          conta={editando}
          categorias={categorias[tipo]}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null);
            atualizar();
          }}
        />
      )}
      {novaConta && categorias && (
        <NovaConta
          tipo={tipo}
          categorias={categorias[tipo]}
          aoFechar={() => setNovaConta(false)}
          aoSalvar={() => {
            setNovaConta(false);
            atualizar();
          }}
        />
      )}
      {lancandoBoleto && categorias && (
        <LancarBoleto
          categorias={categorias.pagar}
          aoFechar={() => setLancandoBoleto(false)}
          aoSalvar={(mensagemOk) => {
            setLancandoBoleto(false);
            atualizar(mensagemOk);
          }}
        />
      )}
    </div>
  );
}

function Situacao({ conta }: { conta: Conta }) {
  if (conta.status === "paga") {
    return (
      <span className="etiqueta ok" title={conta.forma_pagamento ? FORMAS_BAIXA[conta.forma_pagamento] : undefined}>
        {conta.tipo === "pagar" ? "Paga" : "Recebida"}
      </span>
    );
  }
  if (conta.status === "cancelada") return <span className="etiqueta erro-etiqueta">Cancelada</span>;
  if (conta.vencida) return <span className="etiqueta erro-etiqueta">Vencida</span>;
  return <span className="etiqueta">Em aberto</span>;
}

function Baixar({
  conta,
  rotulo,
  aoFechar,
  aoSalvar,
}: {
  conta: Conta;
  rotulo: string;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [pagoEm, setPagoEm] = useState(hojeIso());
  const [valor, setValor] = useState(conta.valor.replace(".", ","));
  const [forma, setForma] = useState(conta.tipo === "pagar" ? "boleto" : "dinheiro");
  const [erro, setErro] = useState("");

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await api(`/financeiro/contas/${conta.id}/baixar`, {
        corpo: { pago_em: pagoEm, valor_pago: paraApi(valor), forma_pagamento: forma },
      });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo={`${rotulo}: ${conta.descricao}`} aoFechar={aoFechar}>
      <form onSubmit={salvar}>
        <fieldset className="campos">
          <label>
            Data
            <input type="date" value={pagoEm} max={hojeIso()} onChange={(e) => setPagoEm(e.target.value)} required />
          </label>
          <label>
            Valor (R$)
            <input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" required />
            <small>Valor da conta: {reais(conta.valor)}. Mude se teve juros ou desconto.</small>
          </label>
          <label className="largo">
            Forma
            <select value={forma} onChange={(e) => setForma(e.target.value)}>
              {Object.entries(FORMAS_BAIXA).map(([id, nome]) => (
                <option key={id} value={id}>
                  {nome}
                </option>
              ))}
            </select>
            {conta.tipo === "receber" && forma === "dinheiro" && (
              <small>Feito num caixa aberto, o dinheiro entra na conferência daquele caixa.</small>
            )}
          </label>
        </fieldset>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes direita espaco-acima">
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit" className="botao">
            Confirmar
          </button>
        </div>
      </form>
    </Janela>
  );
}

function Editar({
  conta,
  categorias,
  aoFechar,
  aoSalvar,
}: {
  conta: Conta;
  categorias: { id: string; nome: string }[];
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [descricao, setDescricao] = useState(conta.descricao);
  const [categoria, setCategoria] = useState(conta.categoria);
  const [vencimento, setVencimento] = useState(conta.vencimento);
  const [valor, setValor] = useState(conta.valor.replace(".", ","));
  const [boleto, setBoleto] = useState(conta.linha_digitavel ?? "");
  const [erro, setErro] = useState("");

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      const corpo: Record<string, string> = { descricao, categoria, vencimento };
      if (!conta.venda_id) corpo.valor = paraApi(valor);
      if (boleto.trim() !== (conta.linha_digitavel ?? "")) corpo.codigo_barras = boleto.trim();
      await api(`/financeiro/contas/${conta.id}`, { metodo: "PATCH", corpo });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Editar conta" aoFechar={aoFechar}>
      <form onSubmit={salvar}>
        <fieldset className="campos">
          <label className="largo">
            Descrição
            <input value={descricao} onChange={(e) => setDescricao(e.target.value)} required minLength={2} />
          </label>
          <label>
            Vencimento
            <input type="date" value={vencimento} onChange={(e) => setVencimento(e.target.value)} required />
          </label>
          <label>
            Valor (R$)
            <input value={valor} onChange={(e) => setValor(e.target.value)} disabled={Boolean(conta.venda_id)} required />
          </label>
          {conta.tipo === "pagar" && (
            <label className="largo">
              Boleto (opcional)
              <input value={boleto} onChange={(e) => setBoleto(e.target.value)} placeholder="Bipe ou cole a linha digitável" inputMode="numeric" />
              <small>Deixe vazio para tirar o boleto da conta.</small>
            </label>
          )}
          <label className="largo">
            Categoria
            <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes direita espaco-acima">
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit" className="botao">
            Salvar
          </button>
        </div>
      </form>
    </Janela>
  );
}

function NovaConta({
  tipo,
  categorias,
  aoFechar,
  aoSalvar,
}: {
  tipo: TipoConta;
  categorias: { id: string; nome: string }[];
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const lojas = useLojas();
  const [fornecedores, setFornecedores] = useState<{ id: string; razao_social: string; nome_fantasia: string | null }[]>([]);
  const [form, setForm] = useState({
    descricao: "",
    categoria: categorias[categorias.length - 1]?.id ?? "outras",
    valor_total: "",
    parcelas: "1",
    primeiro_vencimento: hojeIso(),
    documento: "",
    fornecedor_id: "",
    loja_id: "",
  });
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (tipo === "pagar") {
      api<{ itens: typeof fornecedores }>("/fornecedores?por_pagina=100")
        .then((r) => setFornecedores(r.itens))
        .catch(() => setFornecedores([]));
    }
  }, [tipo]);

  const campo = (nome: keyof typeof form, valor: string) => setForm((atual) => ({ ...atual, [nome]: valor }));
  const parcelas = Math.max(Number(form.parcelas) || 1, 1);
  const valorParcela = Number(paraApi(form.valor_total) || 0) / parcelas;

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await api("/financeiro/contas", {
        corpo: {
          tipo,
          descricao: form.descricao.trim(),
          categoria: form.categoria,
          valor_total: paraApi(form.valor_total),
          parcelas,
          primeiro_vencimento: form.primeiro_vencimento,
          documento: form.documento.trim() || null,
          fornecedor_id: form.fornecedor_id || null,
          loja_id: form.loja_id || null,
        },
      });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo={tipo === "pagar" ? "Nova conta a pagar" : "Nova conta a receber"} aoFechar={aoFechar}>
      <form onSubmit={salvar}>
        <fieldset className="campos">
          <label className="largo">
            Descrição
            <input
              value={form.descricao}
              onChange={(e) => campo("descricao", e.target.value)}
              placeholder={tipo === "pagar" ? "ex.: Aluguel de novembro" : "ex.: Convênio Empresa X"}
              required
              minLength={2}
              autoFocus
            />
          </label>
          <label>
            Categoria
            <select value={form.categoria} onChange={(e) => campo("categoria", e.target.value)}>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </label>
          {tipo === "pagar" ? (
            <label>
              Fornecedor (opcional)
              <select value={form.fornecedor_id} onChange={(e) => campo("fornecedor_id", e.target.value)}>
                <option value="">Nenhum</option>
                {fornecedores.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nome_fantasia || f.razao_social}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              Documento (opcional)
              <input value={form.documento} onChange={(e) => campo("documento", e.target.value)} />
            </label>
          )}
          <label>
            Valor total (R$)
            <input value={form.valor_total} onChange={(e) => campo("valor_total", e.target.value)} inputMode="decimal" required />
          </label>
          <label>
            Parcelas
            <input type="number" min={1} max={60} value={form.parcelas} onChange={(e) => campo("parcelas", e.target.value)} />
            {parcelas > 1 && valorParcela > 0 && (
              <small>
                {parcelas}x de {reais(valorParcela, false)}, uma por mês
              </small>
            )}
          </label>
          <label>
            {parcelas > 1 ? "Primeiro vencimento" : "Vencimento"}
            <input type="date" value={form.primeiro_vencimento} onChange={(e) => campo("primeiro_vencimento", e.target.value)} required />
          </label>
          {tipo === "pagar" && (
            <label>
              Documento (opcional)
              <input value={form.documento} onChange={(e) => campo("documento", e.target.value)} placeholder="ex.: nº do boleto" />
            </label>
          )}
          {lojas.length > 1 && (
            <div className="largo">
              <SeletorLoja lojas={lojas} valor={form.loja_id} aoMudar={(v) => campo("loja_id", v)} />
            </div>
          )}
        </fieldset>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes direita espaco-acima">
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit" className="botao">
            Lançar
          </button>
        </div>
      </form>
    </Janela>
  );
}

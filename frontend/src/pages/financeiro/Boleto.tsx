import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { BoletoLido, Conta, SemanaAPagar } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { categoriaDoBoleto, codigoCompleto, descricaoDoBoleto, soNumeros } from "./boleto";

function paraApi(valor: string): string {
  return valor.includes(",") ? valor.replace(/\./g, "").replace(",", ".") : valor;
}

const DIAS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

function nomeDoDia(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dia = new Date(a, m - 1, d);
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const diferenca = Math.round((dia.getTime() - hoje.getTime()) / 86400000);
  if (diferenca === 0) return "Hoje";
  if (diferenca === 1) return "Amanhã";
  return `${DIAS[dia.getDay()][0].toUpperCase()}${DIAS[dia.getDay()].slice(1)}, ${data(iso).slice(0, 5)}`;
}

/** Copia a linha digitável (só os números) para colar no aplicativo do banco. */
export function CopiarCodigo({ conta, pequeno = true }: { conta: Pick<Conta, "linha_digitavel">; pequeno?: boolean }) {
  const [copiado, setCopiado] = useState<"" | "ok" | "erro">("");
  const campo = useRef<HTMLInputElement>(null);
  if (!conta.linha_digitavel) return null;
  const numeros = soNumeros(conta.linha_digitavel);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(numeros);
      setCopiado("ok");
    } catch {
      // Sem permissão de área de transferência: mostra o número selecionado para copiar à mão.
      setCopiado("erro");
      setTimeout(() => campo.current?.select(), 0);
    }
    setTimeout(() => setCopiado((c) => (c === "ok" ? "" : c)), 2000);
  }

  return (
    <>
      <button
        type="button"
        className={pequeno ? "botao-pequeno" : "botao-contorno"}
        onClick={() => void copiar()}
        title={`Copiar a linha digitável: ${conta.linha_digitavel}`}
      >
        {copiado === "ok" ? "Copiado ✓" : "Copiar código"}
      </button>
      {copiado === "erro" && <input ref={campo} className="codigo-copiar" readOnly value={numeros} onFocus={(e) => e.target.select()} />}
    </>
  );
}

/** Lançar uma conta pelo boleto: bipa ou cola o código, o sistema lê banco, valor e vencimento. */
export function LancarBoleto({
  categorias,
  aoFechar,
  aoSalvar,
}: {
  categorias: { id: string; nome: string }[];
  aoFechar: () => void;
  aoSalvar: (mensagemOk: string) => void;
}) {
  const lojas = useLojas();
  const [codigo, setCodigo] = useState("");
  const [lido, setLido] = useState<BoletoLido | null>(null);
  const [lendo, setLendo] = useState(false);
  const [erro, setErro] = useState("");
  const [fornecedores, setFornecedores] = useState<{ id: string; razao_social: string; nome_fantasia: string | null }[]>([]);
  const [form, setForm] = useState({ descricao: "", categoria: "fornecedores", valor: "", vencimento: "", fornecedor_id: "", loja_id: "" });
  const ultimoLido = useRef("");

  useEffect(() => {
    api<{ itens: typeof fornecedores }>("/fornecedores?por_pagina=100")
      .then((r) => setFornecedores(r.itens))
      .catch(() => setFornecedores([]));
  }, []);

  async function ler(texto: string) {
    const numeros = soNumeros(texto);
    if (!numeros || numeros === ultimoLido.current) return;
    ultimoLido.current = numeros;
    setLendo(true);
    setErro("");
    try {
      const resposta = await api<BoletoLido>("/financeiro/boletos/ler", { corpo: { codigo: numeros } });
      setLido(resposta);
      setForm((f) => ({
        ...f,
        descricao: descricaoDoBoleto(resposta),
        categoria: categoriaDoBoleto(resposta),
        valor: resposta.valor ? resposta.valor.replace(".", ",") : "",
        vencimento: resposta.vencimento ?? "",
      }));
    } catch (e) {
      setLido(null);
      setErro(mensagem(e));
    } finally {
      setLendo(false);
    }
  }

  function digitar(texto: string) {
    setCodigo(texto);
    setLido(null);
    if (codigoCompleto(texto)) void ler(texto);
    else ultimoLido.current = "";
  }

  async function ligar(conta: Conta) {
    if (!lido) return;
    try {
      const corpo: Record<string, string> = { codigo_barras: lido.codigo_barras };
      if (lido.vencimento) corpo.vencimento = lido.vencimento;
      await api(`/financeiro/contas/${conta.id}`, { metodo: "PATCH", corpo });
      aoSalvar(`Boleto ligado à conta “${conta.descricao}”.`);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!lido) return void ler(codigo);
    try {
      await api("/financeiro/contas", {
        corpo: {
          tipo: "pagar",
          descricao: form.descricao.trim(),
          categoria: form.categoria,
          valor_total: paraApi(form.valor),
          primeiro_vencimento: form.vencimento,
          fornecedor_id: form.fornecedor_id || null,
          loja_id: form.loja_id || null,
          codigo_barras: lido.codigo_barras,
        },
      });
      aoSalvar(`Boleto lançado: ${form.descricao.trim()}.`);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  const campo = (nome: keyof typeof form, valor: string) => setForm((atual) => ({ ...atual, [nome]: valor }));
  const quantos = soNumeros(codigo).length;

  return (
    <Janela titulo="Lançar boleto" aoFechar={aoFechar}>
      <form onSubmit={salvar} className="lancar-boleto">
        <label className="campo-boleto">
          Código do boleto
          <input
            value={codigo}
            onChange={(e) => digitar(e.target.value)}
            onKeyDown={(e) => {
              // O leitor de código de barras digita os números e aperta Enter.
              if (e.key === "Enter" && !lido) {
                e.preventDefault();
                void ler(codigo);
              }
            }}
            placeholder="Bipe com o leitor ou cole a linha digitável"
            inputMode="numeric"
            autoFocus
            autoComplete="off"
          />
          <small>
            {quantos === 0
              ? "A linha digitável tem 47 números (boleto) ou 48 (água, luz, telefone, impostos)."
              : lendo
                ? "Conferindo..."
                : lido
                  ? "Código conferido ✓"
                  : `${quantos} números`}
          </small>
        </label>
        {erro && <p className="erro">{erro}</p>}

        {lido && (
          <div className="boleto-lido">
            <div>
              <small>{lido.tipo === "bancario" ? "Banco" : "Tipo"}</small>
              <strong>{lido.tipo === "bancario" ? (lido.banco_nome ?? `Banco ${lido.banco}`) : (lido.segmento ?? "Conta de consumo")}</strong>
            </div>
            <div>
              <small>Valor</small>
              <strong>{lido.valor ? reais(lido.valor) : "não informado"}</strong>
            </div>
            <div>
              <small>Vencimento</small>
              <strong>{lido.vencimento ? data(lido.vencimento) : "não informado"}</strong>
            </div>
            <code className="linha-digitavel">{lido.linha_digitavel}</code>
          </div>
        )}

        {lido?.ja_lancada && (
          <p className="aviso-boleto">
            <Icone nome="alerta" tamanho={16} />
            Este boleto já foi lançado: <strong>{lido.ja_lancada.descricao}</strong>, vencimento {data(lido.ja_lancada.vencimento)} (
            {lido.ja_lancada.status === "paga" ? "já pago" : "em aberto"}).
          </p>
        )}

        {lido && !lido.ja_lancada && lido.parecidas.length > 0 && (
          <div className="parecidas">
            <p>
              <strong>Já existe conta com este valor e sem boleto.</strong> Se for a mesma (por exemplo, a parcela de uma nota de compra),
              ligue o boleto a ela em vez de lançar outra:
            </p>
            {lido.parecidas.map((c) => (
              <div key={c.id} className="parecida">
                <span>
                  {c.descricao}
                  <small>
                    {c.pessoa ? `${c.pessoa} · ` : ""}vence {data(c.vencimento)} · {reais(c.valor)}
                  </small>
                </span>
                <button type="button" className="botao-pequeno" onClick={() => void ligar(c)}>
                  Ligar a esta conta
                </button>
              </div>
            ))}
          </div>
        )}

        {lido && !lido.ja_lancada && (
          <fieldset className="campos espaco-acima">
            <label className="largo">
              Descrição
              <input value={form.descricao} onChange={(e) => campo("descricao", e.target.value)} required minLength={2} />
            </label>
            <label>
              Valor (R$)
              <input value={form.valor} onChange={(e) => campo("valor", e.target.value)} inputMode="decimal" required />
            </label>
            <label>
              Vencimento
              <input type="date" value={form.vencimento} onChange={(e) => campo("vencimento", e.target.value)} required />
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
            {lojas.length > 1 && (
              <div className="largo">
                <SeletorLoja lojas={lojas} valor={form.loja_id} aoMudar={(v) => campo("loja_id", v)} />
              </div>
            )}
          </fieldset>
        )}

        <div className="acoes direita espaco-acima">
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            {lido?.ja_lancada ? "Fechar" : "Voltar"}
          </button>
          {!lido?.ja_lancada && (
            <button type="submit" className="botao" disabled={lendo || !quantos}>
              {lido ? "Lançar conta" : "Conferir código"}
            </button>
          )}
        </div>
      </form>
    </Janela>
  );
}

/** O que pagar: as contas atrasadas e as dos próximos 7 dias, dia a dia. */
export function SemanaPagar({ versao, aoPagar }: { versao: number; aoPagar: (conta: Conta) => void }) {
  const [semana, setSemana] = useState<SemanaAPagar | null>(null);

  useEffect(() => {
    api<SemanaAPagar>("/financeiro/semana")
      .then(setSemana)
      .catch(() => setSemana(null));
  }, [versao]);

  if (!semana) return null;
  const grupos = [
    ...(semana.vencidas.length ? [{ titulo: "Atrasadas", total: semana.total_vencidas, contas: semana.vencidas, atraso: true }] : []),
    ...semana.dias.map((d) => ({ titulo: nomeDoDia(d.dia), total: d.total, contas: d.contas, atraso: false })),
  ];

  return (
    <section className="cartao semana-pagar">
      <div className="cartao-cabecalho">
        <h2>O que pagar nesta semana</h2>
        <small>
          {reais(semana.total_semana)} nos próximos 7 dias
          {Number(semana.total_vencidas) > 0 && ` · ${reais(semana.total_vencidas)} atrasado`}
        </small>
      </div>
      {grupos.length === 0 ? (
        <p className="lista-vazia">Nada para pagar nos próximos 7 dias.</p>
      ) : (
        <div className="semana-dias">
          {grupos.map((g) => (
            <div key={g.titulo} className={g.atraso ? "semana-dia atrasado" : "semana-dia"}>
              <div className="semana-dia-topo">
                <strong>{g.titulo}</strong>
                <span>{reais(g.total)}</span>
              </div>
              <ul>
                {g.contas.map((c) => (
                  <li key={c.id}>
                    <span className="semana-conta">
                      {c.descricao}
                      <small>
                        {g.atraso && `venceu ${data(c.vencimento)} · `}
                        {c.pessoa ?? (c.linha_digitavel ? "com boleto" : "sem boleto")}
                      </small>
                    </span>
                    <strong className="num">{reais(c.valor)}</strong>
                    <span className="acoes-tabela">
                      <CopiarCodigo conta={c} />
                      <button type="button" className="botao-pequeno" onClick={() => aoPagar(c)}>
                        Pagar
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

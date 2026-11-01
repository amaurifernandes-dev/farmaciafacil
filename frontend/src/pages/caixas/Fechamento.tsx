import { useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ConferenciaForma, MovimentoCaixa, ResumoCaixa } from "../../api/tipos";
import { Janela } from "../../components/Cadastro";
import { reais } from "../../formato";
import { centavosParaApi, paraCentavos } from "../pdv/carrinho";
import { conferir, type Contagem, NOMES_FORMA } from "./conferencia";

const hora = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

function Diferenca({ centavos }: { centavos: number | null }) {
  if (centavos === null) return <span className="vazio">não conferido</span>;
  if (centavos === 0) return <span className="positivo">bateu</span>;
  return (
    <span className="negativo">
      {centavos > 0 ? "sobra " : "falta "}
      {reais(Math.abs(centavos))}
    </span>
  );
}

/** Os campos do fechamento: dinheiro contado e os comprovantes de cartão e Pix, com a diferença na hora. */
export function CamposFechamento({
  resumo,
  contagem,
  aoMudar,
  autoFocus = true,
}: {
  resumo: ResumoCaixa;
  contagem: Contagem;
  aoMudar: (c: Contagem) => void;
  autoFocus?: boolean;
}) {
  const { linhas, temDiferenca, diferencaTotal } = conferir(resumo, contagem);
  return (
    <div className="conferencia-caixa">
      <table className="tabela tabela-conferencia">
        <thead>
          <tr>
            <th>Forma</th>
            <th className="num">No sistema</th>
            <th className="num">Contado</th>
            <th className="num">Diferença</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l, i) => (
            <tr key={l.forma}>
              <td>
                <strong>{NOMES_FORMA[l.forma]}</strong>
                <small>{l.forma === "dinheiro" ? "conte a gaveta" : "some os comprovantes"}</small>
              </td>
              <td className="num">{reais(l.esperado)}</td>
              <td className="num">
                <input
                  aria-label={`${NOMES_FORMA[l.forma]} contado`}
                  inputMode="decimal"
                  placeholder={l.forma === "dinheiro" ? "0,00" : "não conferir"}
                  autoFocus={autoFocus && i === 0}
                  className={l.invalido ? "campo-erro" : ""}
                  value={l.forma === "dinheiro" ? contagem.dinheiro : (contagem.formas[l.forma] ?? "")}
                  onChange={(e) =>
                    aoMudar(
                      l.forma === "dinheiro"
                        ? { ...contagem, dinheiro: e.target.value }
                        : { ...contagem, formas: { ...contagem.formas, [l.forma]: e.target.value } },
                    )
                  }
                />
              </td>
              <td className="num">
                <Diferenca centavos={l.diferenca} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {temDiferenca && (
        <label className="observacao-fechamento">
          Motivo da diferença ({diferencaTotal > 0 ? "sobra" : "falta"} de {reais(Math.abs(diferencaTotal))})
          <textarea
            rows={2}
            maxLength={500}
            value={contagem.observacao}
            onChange={(e) => aoMudar({ ...contagem, observacao: e.target.value })}
            placeholder="Ex.: troco dado errado, comprovante perdido, cliente volta para pagar"
          />
        </label>
      )}
    </div>
  );
}

/** Conferência de um caixa já fechado (ou do dia): forma por forma. */
export function TabelaConferencia({ linhas }: { linhas: ConferenciaForma[] }) {
  const centavos = (v: string | null) => (v === null ? null : Math.round(Number(v) * 100));
  return (
    <div className="tabela-rolagem">
      <table className="tabela tabela-conferencia">
        <thead>
          <tr>
            <th>Forma</th>
            <th className="num">No sistema</th>
            <th className="num">Contado</th>
            <th className="num">Diferença</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.forma}>
              <td>{NOMES_FORMA[l.forma] ?? l.forma}</td>
              <td className="num">{reais(l.esperado)}</td>
              <td className="num">
                {l.informado === null ? "-" : reais(l.informado)}
                {Number(l.sem_conferir ?? 0) > 0 && l.informado !== null && (
                  <small className="sem-conferir">{reais(l.sem_conferir ?? "0")} sem conferir</small>
                )}
              </td>
              <td className="num">
                <Diferenca centavos={centavos(l.diferenca)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ListaMovimentos({ movimentos }: { movimentos: MovimentoCaixa[] }) {
  if (!movimentos.length) return null;
  return (
    <ul className="lista-movimentos">
      {movimentos.map((m) => (
        <li key={m.id}>
          <span className={m.tipo === "sangria" ? "etiqueta etiqueta-alerta" : "etiqueta ok"}>
            {m.tipo === "sangria" ? "Sangria" : "Suprimento"}
          </span>
          <span>
            {m.motivo}
            <small>
              {hora(m.criado_em)} · {m.usuario}
            </small>
          </span>
          <strong className="num">
            {m.tipo === "sangria" ? "-" : "+"}
            {reais(m.valor)}
          </strong>
        </li>
      ))}
    </ul>
  );
}

const MOTIVOS = {
  sangria: ["Cofre", "Depósito no banco", "Pagamento de fornecedor", "Despesa da loja"],
  suprimento: ["Troco do cofre", "Troco do banco"],
};

/** Sangria (tirar dinheiro da gaveta) ou suprimento (colocar troco). */
export function FormMovimento({
  resumo,
  tipo,
  aoSalvar,
  aoCancelar,
}: {
  resumo: ResumoCaixa;
  tipo: "sangria" | "suprimento";
  aoSalvar: (r: ResumoCaixa) => void;
  aoCancelar: () => void;
}) {
  const [valor, setValor] = useState("");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    evento.stopPropagation();
    const centavos = paraCentavos(valor);
    if (!centavos) return setErro("Informe o valor");
    if (!motivo.trim()) return setErro("Diga para onde vai (ou de onde vem) o dinheiro");
    setSalvando(true);
    try {
      aoSalvar(
        await api<ResumoCaixa>(`/caixas/${resumo.caixa.id}/movimentos`, {
          corpo: { tipo, valor: centavosParaApi(centavos), motivo },
        }),
      );
    } catch (e) {
      setErro(mensagem(e));
      setSalvando(false);
    }
  }

  return (
    <form className="campos form-movimento" onSubmit={salvar}>
      <p className="largo vazio">
        {tipo === "sangria"
          ? `Tirar dinheiro da gaveta. Agora tem ${reais(resumo.dinheiro_esperado)} em dinheiro.`
          : "Colocar dinheiro na gaveta, normalmente para troco."}
      </p>
      <label>
        Valor (R$)
        <input value={valor} onChange={(e) => setValor(e.target.value)} inputMode="decimal" autoFocus />
      </label>
      <label>
        Motivo
        <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={200} list={`motivos-${tipo}`} />
        <datalist id={`motivos-${tipo}`}>
          {MOTIVOS[tipo].map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
      </label>
      <div className="acoes largo chips-motivo">
        {MOTIVOS[tipo].map((m) => (
          <button key={m} type="button" className={motivo === m ? "botao-pequeno ativo" : "botao-pequeno"} onClick={() => setMotivo(m)}>
            {m}
          </button>
        ))}
      </div>
      {erro && <p className="erro largo">{erro}</p>}
      <div className="acoes largo direita">
        <button type="button" onClick={aoCancelar}>
          Cancelar
        </button>
        <button type="submit" disabled={salvando}>
          {tipo === "sangria" ? "Registrar sangria" : "Registrar suprimento"}
        </button>
      </div>
    </form>
  );
}

export function JanelaMovimento(props: {
  resumo: ResumoCaixa;
  tipo: "sangria" | "suprimento";
  aoSalvar: (r: ResumoCaixa) => void;
  aoCancelar: () => void;
}) {
  return (
    <Janela
      titulo={`${props.tipo === "sangria" ? "Sangria" : "Suprimento"} · ${props.resumo.terminal ?? ""} · ${props.resumo.operador}`}
      aoFechar={props.aoCancelar}
    >
      <FormMovimento {...props} />
    </Janela>
  );
}

/** O que o caixa teve em dinheiro: abertura, vendas, troco e movimentos da gaveta. */
export function LinhasDinheiro({ resumo }: { resumo: ResumoCaixa }) {
  const linhas: [string, string, string?][] = [["Abertura", resumo.caixa.valor_abertura]];
  if (Number(resumo.recebimentos_dinheiro) > 0) linhas.push(["Fiado recebido em dinheiro", resumo.recebimentos_dinheiro]);
  if (Number(resumo.servicos_dinheiro ?? 0) > 0) linhas.push(["Serviços farmacêuticos em dinheiro", resumo.servicos_dinheiro]);
  if (Number(resumo.devolucoes_dinheiro ?? 0) > 0) linhas.push(["Devolvido a clientes (trocas)", resumo.devolucoes_dinheiro, "-"]);
  if (Number(resumo.suprimentos ?? 0) > 0) linhas.push(["Suprimentos", resumo.suprimentos ?? "0"]);
  if (Number(resumo.sangrias ?? 0) > 0) linhas.push(["Sangrias", resumo.sangrias ?? "0", "-"]);
  return (
    <dl className="resumo">
      {linhas.map(([rotulo, valor, sinal]) => (
        <div key={rotulo}>
          <dt>{rotulo}</dt>
          <dd>
            {sinal}
            {reais(valor)}
          </dd>
        </div>
      ))}
      <div>
        <dt>Vendas</dt>
        <dd>
          {resumo.quantidade_vendas} · {reais(resumo.total_vendido)}
        </dd>
      </div>
      {Object.entries(resumo.por_forma).map(([forma, valor]) => (
        <div key={forma} className="resumo-sub">
          <dt>{NOMES_FORMA[forma] ?? forma}</dt>
          <dd>{reais(valor)}</dd>
        </div>
      ))}
    </dl>
  );
}

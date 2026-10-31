import { useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ResumoCaixa } from "../../api/tipos";
import { reais } from "../../formato";
import { paraCentavos } from "./carrinho";

const NOMES: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo (fiado)",
  convenio: "Convênio",
  popular: "Farmácia Popular",
};

interface Props {
  caixa: ResumoCaixa;
  aoVoltar: () => void;
  aoFechar: () => void;
}

export default function FecharCaixa({ caixa, aoVoltar, aoFechar }: Props) {
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

  if (resumo) {
    const diferenca = Number(resumo.diferenca);
    return (
      <div className="pdv-centro cartao">
        <h2>Caixa fechado</h2>
        <Linhas resumo={resumo} />
        <p className={diferenca === 0 ? "ok" : "erro"}>
          Diferença: {reais(resumo.diferenca ?? "0")} {diferenca < 0 ? "(falta)" : diferenca > 0 ? "(sobra)" : ""}
        </p>
        <button onClick={aoFechar} autoFocus>
          OK
        </button>
      </div>
    );
  }

  return (
    <form
      className="pdv-centro cartao"
      onSubmit={fechar}
      onKeyDown={(e) => {
        if (e.key === "Escape") aoVoltar();
      }}
    >
      <h2>Fechar caixa</h2>
      <Linhas resumo={caixa} />
      <label>
        Dinheiro contado na gaveta (R$)
        <input value={valor} onChange={(e) => setValor(e.target.value)} autoFocus />
      </label>
      {erro && <p className="erro">{erro}</p>}
      <button type="submit">Fechar (Enter)</button>
      <button type="button" onClick={aoVoltar}>
        Voltar (Esc)
      </button>
    </form>
  );
}

function Linhas({ resumo }: { resumo: ResumoCaixa }) {
  return (
    <dl className="resumo">
      <dt>Abertura</dt>
      <dd>{reais(resumo.caixa.valor_abertura)}</dd>
      <dt>Vendas</dt>
      <dd>
        {resumo.quantidade_vendas} · {reais(resumo.total_vendido)}
      </dd>
      {Object.entries(resumo.por_forma).map(([forma, valor]) => (
        <div key={forma}>
          <dt>{NOMES[forma] ?? forma}</dt>
          <dd>{reais(valor)}</dd>
        </div>
      ))}
      {Number(resumo.recebimentos_dinheiro) > 0 && (
        <div>
          <dt>Fiado recebido em dinheiro</dt>
          <dd>{reais(resumo.recebimentos_dinheiro)}</dd>
        </div>
      )}
      {Number(resumo.servicos_dinheiro ?? 0) > 0 && (
        <div>
          <dt>Serviços farmacêuticos em dinheiro</dt>
          <dd>{reais(resumo.servicos_dinheiro)}</dd>
        </div>
      )}
      <dt>Dinheiro esperado</dt>
      <dd>{reais(resumo.dinheiro_esperado)}</dd>
    </dl>
  );
}

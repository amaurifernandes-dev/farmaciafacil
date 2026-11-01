import { useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ResumoCaixa } from "../../api/tipos";
import { reais } from "../../formato";
import { ehFalhaDeRede } from "../../offline/catalogo";
import { paraCentavos } from "./carrinho";

const NOMES: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo (fiado)",
  convenio: "Convênio",
  popular: "Farmácia Popular",
  vale: "Vale-troca",
};

interface Props {
  caixa: ResumoCaixa;
  /** Fecha aqui e manda depois (sem internet, ou com envios ainda na fila). */
  guardar: boolean;
  aoFecharSemInternet: (centavos: number) => Promise<ResumoCaixa>;
  aoCair: () => void;
  aoVoltar: () => void;
  aoFechar: () => void;
}

export default function FecharCaixa({ caixa, guardar, aoFecharSemInternet, aoCair, aoVoltar, aoFechar }: Props) {
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState("");
  const [resumo, setResumo] = useState<ResumoCaixa | null>(null);
  const [guardado, setGuardado] = useState(false);

  async function semInternet(centavos: number) {
    try {
      setResumo(await aoFecharSemInternet(centavos));
      setGuardado(true);
    } catch (e) {
      setErro(`Não deu para guardar o fechamento neste computador: ${mensagem(e)}`);
    }
  }

  async function fechar(evento: FormEvent) {
    evento.preventDefault();
    const centavos = paraCentavos(valor);
    if (centavos === null) return setErro("Informe o dinheiro contado na gaveta");
    if (guardar) return semInternet(centavos);
    try {
      setResumo(
        await api<ResumoCaixa>(`/caixas/${caixa.caixa.id}/fechar`, {
          corpo: { valor_fechamento_informado: (centavos / 100).toFixed(2) },
        }),
      );
    } catch (e) {
      if (!ehFalhaDeRede(e)) return setErro(mensagem(e));
      aoCair();
      await semInternet(centavos);
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
        {guardado && (
          <p className="pdv-fechado-guardado">
            Fechado sem internet: o fechamento fica guardado neste computador e é enviado sozinho, depois das vendas,
            quando a internet voltar.
          </p>
        )}
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
      {guardar && <p className="pdv-offline">Sem internet · o fechamento é guardado e enviado depois</p>}
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
      {Number(resumo.devolucoes_dinheiro ?? 0) > 0 && (
        <div>
          <dt>Devolvido a clientes (trocas)</dt>
          <dd>-{reais(resumo.devolucoes_dinheiro)}</dd>
        </div>
      )}
      <dt>Dinheiro esperado</dt>
      <dd>{reais(resumo.dinheiro_esperado)}</dd>
    </dl>
  );
}

import { useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ResumoCaixa } from "../../api/tipos";
import { reais } from "../../formato";
import { ehFalhaDeRede } from "../../offline/catalogo";
import { conferir, type Contagem, contagemVazia } from "../caixas/conferencia";
import { CamposFechamento, FormMovimento, LinhasDinheiro, ListaMovimentos, TabelaConferencia } from "../caixas/Fechamento";

export type CorpoFechamento = NonNullable<ReturnType<typeof conferir>["corpo"]>;

interface Props {
  caixa: ResumoCaixa;
  /** Fecha aqui e manda depois (sem internet, ou com envios ainda na fila). */
  guardar: boolean;
  aoFecharSemInternet: (corpo: CorpoFechamento) => Promise<ResumoCaixa>;
  /** Sangria ou suprimento lançado: o caixa com a gaveta atualizada. */
  aoAtualizar: (resumo: ResumoCaixa) => void;
  aoCair: () => void;
  aoVoltar: () => void;
  aoFechar: () => void;
}

export default function FecharCaixa({ caixa, guardar, aoFecharSemInternet, aoAtualizar, aoCair, aoVoltar, aoFechar }: Props) {
  const [contagem, setContagem] = useState<Contagem>(contagemVazia);
  const [erro, setErro] = useState("");
  const [resumo, setResumo] = useState<ResumoCaixa | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [movimento, setMovimento] = useState<"sangria" | "suprimento" | null>(null);

  async function semInternet(corpo: CorpoFechamento) {
    try {
      setResumo(await aoFecharSemInternet(corpo));
      setGuardado(true);
    } catch (e) {
      setErro(`Não deu para guardar o fechamento neste computador: ${mensagem(e)}`);
    }
  }

  async function fechar(evento: FormEvent) {
    evento.preventDefault();
    const { corpo, erro: problema } = conferir(caixa, contagem);
    if (!corpo) return setErro(problema);
    if (guardar) return semInternet(corpo);
    try {
      setResumo(await api<ResumoCaixa>(`/caixas/${caixa.caixa.id}/fechar`, { corpo }));
    } catch (e) {
      if (!ehFalhaDeRede(e)) return setErro(mensagem(e));
      aoCair();
      await semInternet(corpo);
    }
  }

  if (resumo) {
    const diferenca = Number(resumo.diferenca_total ?? resumo.diferenca);
    return (
      <div className="pdv-centro pdv-fechamento cartao">
        <h2>Caixa fechado</h2>
        <LinhasDinheiro resumo={resumo} />
        {resumo.conferencia?.length ? (
          <TabelaConferencia linhas={resumo.conferencia} />
        ) : (
          <p>Dinheiro esperado: {reais(resumo.dinheiro_esperado)}</p>
        )}
        <p className={diferenca === 0 ? "ok" : "erro"}>
          Diferença: {reais(String(diferenca))} {diferenca < 0 ? "(falta)" : diferenca > 0 ? "(sobra)" : ""}
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

  if (movimento) {
    return (
      <div className="pdv-centro pdv-fechamento cartao">
        <h2>{movimento === "sangria" ? "Sangria" : "Suprimento"}</h2>
        <FormMovimento
          resumo={caixa}
          tipo={movimento}
          aoCancelar={() => setMovimento(null)}
          aoSalvar={(atualizado) => {
            aoAtualizar(atualizado);
            setMovimento(null);
          }}
        />
      </div>
    );
  }

  return (
    <form
      className="pdv-centro pdv-fechamento cartao"
      onSubmit={fechar}
      onKeyDown={(e) => {
        if (e.key === "Escape") aoVoltar();
      }}
    >
      <h2>Fechar caixa</h2>
      {guardar && <p className="pdv-offline">Sem internet · o fechamento é guardado e enviado depois</p>}
      <LinhasDinheiro resumo={caixa} />
      <ListaMovimentos movimentos={caixa.movimentos ?? []} />
      <div className="acoes">
        <button type="button" className="botao-pequeno" disabled={guardar} onClick={() => setMovimento("sangria")}>
          Sangria
        </button>
        <button type="button" className="botao-pequeno" disabled={guardar} onClick={() => setMovimento("suprimento")}>
          Suprimento
        </button>
        {guardar && <small className="vazio">Sangria e suprimento precisam de internet</small>}
      </div>
      <CamposFechamento resumo={caixa} contagem={contagem} aoMudar={setContagem} />
      {erro && <p className="erro">{erro}</p>}
      <button type="submit">Fechar (Enter)</button>
      <button type="button" onClick={aoVoltar}>
        Voltar (Esc)
      </button>
    </form>
  );
}

import type { ResumoCaixa } from "../../api/tipos";
import { centavosParaApi, paraCentavos } from "../pdv/carrinho";

export const NOMES_FORMA: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo (fiado)",
  convenio: "Convênio",
  popular: "Farmácia Popular",
  vale: "Vale-troca",
};

/** Além do dinheiro, o operador confere os comprovantes da maquininha e do Pix. */
export const FORMAS_CONFERIDAS = ["debito", "credito", "pix"] as const;

/** O que o operador contou: texto digitado de cada forma ("" = não conferida) e a explicação. */
export interface Contagem {
  dinheiro: string;
  formas: Record<string, string>;
  observacao: string;
}

export interface LinhaContagem {
  forma: string;
  esperado: number; // centavos
  informado: number | null;
  diferenca: number | null;
  invalido: boolean;
}

export const contagemVazia = (): Contagem => ({ dinheiro: "", formas: {}, observacao: "" });

const centavos = (valor: string | undefined) => Math.round(Number(valor ?? 0) * 100);

/** Cartão e Pix só aparecem para conferir quando houve venda nessa forma. */
export function formasParaConferir(resumo: ResumoCaixa): string[] {
  return FORMAS_CONFERIDAS.filter((f) => centavos(resumo.por_forma[f]) > 0);
}

function linha(forma: string, esperado: number, texto: string): LinhaContagem {
  const vazio = texto.trim() === "";
  const informado = vazio ? null : paraCentavos(texto);
  return {
    forma,
    esperado,
    informado,
    diferenca: informado === null ? null : informado - esperado,
    invalido: !vazio && informado === null,
  };
}

/** As linhas da conferência enquanto o operador digita, e o corpo para fechar o caixa (ou o erro). */
export function conferir(resumo: ResumoCaixa, contagem: Contagem) {
  const linhas = [
    linha("dinheiro", centavos(resumo.dinheiro_esperado), contagem.dinheiro),
    ...formasParaConferir(resumo).map((f) => linha(f, centavos(resumo.por_forma[f]), contagem.formas[f] ?? "")),
  ];
  const conferidas = linhas.filter((l) => l.diferenca !== null);
  const diferencaTotal = conferidas.reduce((soma, l) => soma + (l.diferenca ?? 0), 0);
  const temDiferenca = conferidas.some((l) => l.diferenca !== 0);

  let erro = "";
  const dinheiro = linhas[0];
  if (dinheiro.informado === null) erro = "Informe o dinheiro contado na gaveta";
  else if (linhas.some((l) => l.invalido)) erro = "Algum valor está escrito errado. Use o formato 120,50";
  else if (temDiferenca && !contagem.observacao.trim()) erro = "Escreva o motivo da diferença antes de fechar";

  const corpo = erro
    ? null
    : {
        valor_fechamento_informado: centavosParaApi(dinheiro.informado ?? 0),
        conferencia: Object.fromEntries(
          linhas.slice(1).flatMap((l) => (l.informado === null ? [] : [[l.forma, centavosParaApi(l.informado)]])),
        ),
        observacao: contagem.observacao.trim() || null,
      };
  return { linhas, diferencaTotal, temDiferenca, erro, corpo };
}

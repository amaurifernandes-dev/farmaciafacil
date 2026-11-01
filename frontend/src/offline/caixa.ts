// O caixa sem internet: abre e fecha neste computador e mostra os números somando as vendas
// guardadas. Abertura e fechamento vão para a fila e chegam ao servidor na ordem em que aconteceram.

import type { EsteTerminal, ResumoCaixa, Sessao } from "../api/tipos";
import type { VendaGuardada } from "./banco";

const centavos = (valor: string | number | null | undefined) => Math.round(Number(valor ?? 0) * 100);
const texto = (c: number) => (c / 100).toFixed(2);

/** O resumo do servidor mais as vendas guardadas deste caixa que ainda não foram enviadas. */
export function somarGuardadas(resumo: ResumoCaixa, guardadas: VendaGuardada[]): ResumoCaixa {
  const deste = guardadas.filter(
    (g) => (g.tipo ?? "venda") === "venda" && !g.problema && g.corpo.caixa_id === resumo.caixa.id,
  );
  if (deste.length === 0) return resumo;
  const porForma: Record<string, number> = {};
  for (const [forma, valor] of Object.entries(resumo.por_forma)) porForma[forma] = centavos(valor);
  let total = centavos(resumo.total_vendido);
  let esperado = centavos(resumo.dinheiro_esperado);
  for (const venda of deste) {
    const pagamentos = (venda.corpo.pagamentos ?? []) as { forma: string; valor: string }[];
    let pago = 0;
    for (const p of pagamentos) {
      porForma[p.forma] = (porForma[p.forma] ?? 0) + centavos(p.valor);
      pago += centavos(p.valor);
      if (p.forma === "dinheiro") esperado += centavos(p.valor);
    }
    esperado -= Math.max(pago - venda.total_centavos, 0); // o troco sai da gaveta
    total += venda.total_centavos;
  }
  return {
    ...resumo,
    quantidade_vendas: resumo.quantidade_vendas + deste.length,
    total_vendido: texto(total),
    por_forma: Object.fromEntries(Object.entries(porForma).map(([f, c]) => [f, texto(c)])),
    dinheiro_esperado: texto(esperado),
  };
}

/** Caixa aberto sem internet: o id nasce aqui, e as vendas offline já usam ele. */
export function abrirSemInternet(
  terminal: EsteTerminal,
  sessao: Sessao,
  aberturaCentavos: number,
  agora: Date,
  id: string = crypto.randomUUID(),
): { resumo: ResumoCaixa; guardada: VendaGuardada } {
  const quando = agora.toISOString();
  const resumo: ResumoCaixa = {
    caixa: {
      id,
      usuario_id: sessao.usuario_id,
      terminal_id: terminal.terminal.id,
      loja_id: terminal.loja.id,
      status: "aberto",
      valor_abertura: texto(aberturaCentavos),
      aberto_em: quando,
      fechado_em: null,
      valor_fechamento_informado: null,
      aberto_offline: true,
    },
    operador: sessao.nome,
    terminal: terminal.terminal.nome,
    loja: terminal.loja.nome,
    quantidade_vendas: 0,
    total_vendido: "0.00",
    por_forma: {},
    recebimentos_dinheiro: "0.00",
    servicos_dinheiro: "0.00",
    devolucoes_dinheiro: "0.00",
    dinheiro_esperado: texto(aberturaCentavos),
    diferenca: null,
  };
  const guardada: VendaGuardada = {
    chave: `abrir-${id}`,
    tipo: "abrir",
    caminho: "/caixas/abrir",
    corpo: { id, valor_abertura: texto(aberturaCentavos), offline_em: quando },
    total_centavos: 0,
    itens: 0,
    guardada_em: quando,
  };
  return { resumo, guardada };
}

/** Caixa fechado sem internet: a conta da diferença é feita aqui com o que se sabe. */
export function fecharSemInternet(
  resumo: ResumoCaixa,
  informadoCentavos: number,
  agora: Date,
): { resumo: ResumoCaixa; guardada: VendaGuardada } {
  const quando = agora.toISOString();
  return {
    resumo: {
      ...resumo,
      caixa: {
        ...resumo.caixa,
        status: "fechado",
        fechado_em: quando,
        valor_fechamento_informado: texto(informadoCentavos),
        fechado_offline: true,
      },
      diferenca: texto(informadoCentavos - centavos(resumo.dinheiro_esperado)),
    },
    guardada: {
      chave: `fechar-${resumo.caixa.id}`,
      tipo: "fechar",
      caminho: `/caixas/${resumo.caixa.id}/fechar`,
      corpo: { valor_fechamento_informado: texto(informadoCentavos), offline_em: quando },
      total_centavos: 0,
      itens: 0,
      guardada_em: quando,
    },
  };
}

// Regras do carrinho do PDV, sem React, para poder testar isoladamente.
// Valores em dinheiro ficam em centavos (inteiros) para não ter erro de arredondamento.

import type { DadosPopular, FormaPagamento, ProdutoPDV, PromocaoPDV, Receita } from "../../api/tipos";

export interface ItemCarrinho {
  produtoId: string;
  descricao: string;
  precoCentavos: number;
  quantidade: number;
  saldo: number;
  /** Promoções do produto hoje; vale a que der mais desconto. */
  promocoes?: PromocaoPDV[];
  /** Lista da Portaria 344 ou ATB: a venda pede a receita. */
  controle?: string | null;
  /** Farmácia Popular: quanto o governo paga por unidade, em centavos. Vazio: fora do programa. */
  popularCentavos?: number | null;
}

export interface Pagamento {
  forma: FormaPagamento;
  centavos: number;
}

export interface Carrinho {
  /** Identifica a venda no servidor; reenviar a mesma chave não duplica. */
  chave: string;
  itens: ItemCarrinho[];
  descontoCentavos: number;
  pagamentos: Pagamento[];
  /** Pré-venda que está sendo recebida neste carrinho, se houver. */
  preVenda?: { id: string; numero: number };
  /** Cliente identificado: ganha pontos e pode comprar a prazo. */
  cliente?: ClienteVenda;
  /** Pontos do cliente trocados por desconto nesta venda. */
  pontosResgatados?: number;
  /** Taxa de entrega do pedido que virou a pré-venda (o servidor cobra a mesma). */
  taxaEntregaCentavos?: number;
  /** Dados da receita, quando a venda tem remédio controlado. */
  receita?: Receita;
  /** Venda pela Farmácia Popular: paciente, receita e número da autorização do governo. */
  popular?: DadosPopular;
}

export interface ClienteVenda {
  id: string;
  nome: string;
  /** Quanto ainda pode comprar a prazo (0 = não compra fiado). */
  disponivelCentavos: number;
  pontos?: PontosCliente;
  /** Funcionário de empresa conveniada: desconto e quanto ainda pode comprar no convênio. */
  convenio?: ConvenioCliente;
}

export interface ConvenioCliente {
  nome: string;
  /** Percentual, como vem da API (ex.: "10.00"). */
  desconto: string;
  disponivelCentavos: number;
}

export interface PontosCliente {
  saldo: number;
  /** Quanto vale um ponto, em reais (ex.: "0.05"). */
  valorPonto: string;
  minimo: number;
}

export function novoCarrinho(): Carrinho {
  return { chave: crypto.randomUUID(), itens: [], descontoCentavos: 0, pagamentos: [] };
}

/** "8.90" (API) ou "8,90" (digitado) -> 890. Devolve null se não for um valor válido. */
export function paraCentavos(texto: string): number | null {
  let limpo = texto.trim();
  // Com vírgula, o ponto é separador de milhar ("1.234,56"); sem vírgula, é o decimal ("8.90").
  if (limpo.includes(",")) limpo = limpo.replace(/\./g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(limpo)) return null;
  return Math.round(Number(limpo) * 100);
}

/** Centavos -> "8.90", o formato que a API espera. */
export function centavosParaApi(centavos: number): string {
  return (centavos / 100).toFixed(2);
}

export function lerQuantidade(texto: string): number | null {
  const limpo = texto.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,3})?$/.test(limpo)) return null;
  const valor = Number(limpo);
  return valor > 0 ? valor : null;
}

/**
 * Interpreta o que foi digitado ou bipado no campo do PDV.
 * "7891234567890" -> 1 unidade; "3*7891234567890" -> 3 unidades.
 */
export function interpretarEntrada(texto: string): { quantidade: number; codigo: string } | null {
  const partes = texto.trim().split("*");
  if (partes.length > 2) return null;
  const codigo = partes[partes.length - 1].trim();
  if (!/^\d{8,14}$/.test(codigo)) return null;
  const quantidade = partes.length === 2 ? lerQuantidade(partes[0]) : 1;
  return quantidade === null ? null : { quantidade, codigo };
}

export function adicionarProduto(carrinho: Carrinho, produto: ProdutoPDV, quantidade: number): Carrinho {
  const existente = carrinho.itens.findIndex((item) => item.produtoId === produto.id);
  if (existente >= 0) {
    const item = carrinho.itens[existente];
    return alterarQuantidade(carrinho, existente, item.quantidade + quantidade);
  }
  const descricao = produto.apresentacao ? `${produto.nome} ${produto.apresentacao}` : produto.nome;
  const novo: ItemCarrinho = {
    produtoId: produto.id,
    descricao,
    precoCentavos: paraCentavos(produto.preco_venda) ?? 0,
    quantidade,
    saldo: Number(produto.saldo),
    promocoes: produto.promocoes ?? [],
    controle: produto.controle ?? null,
    popularCentavos: produto.popular_valor ? paraCentavos(produto.popular_valor) : null,
  };
  return { ...carrinho, itens: [...carrinho.itens, novo] };
}

export function alterarQuantidade(carrinho: Carrinho, indice: number, quantidade: number): Carrinho {
  const itens = carrinho.itens.map((item, i) => (i === indice ? { ...item, quantidade } : item));
  return { ...carrinho, itens };
}

export function removerItem(carrinho: Carrinho, indice: number): Carrinho {
  return { ...carrinho, itens: carrinho.itens.filter((_, i) => i !== indice) };
}

export function totalItem(item: ItemCarrinho): number {
  return Math.round(item.precoCentavos * item.quantidade);
}

/** Desconto de uma promoção no item, em centavos. Mesma conta do servidor (promocoes/service.py). */
export function descontoDaPromocao(promocao: PromocaoPDV, item: ItemCarrinho): number {
  const bruto = totalItem(item);
  let valor = 0;
  if (promocao.tipo === "percentual") {
    valor = Math.round((bruto * Number(promocao.percentual)) / 100);
  } else if (promocao.tipo === "preco_fixo") {
    const promocional = paraCentavos(promocao.preco ?? "") ?? item.precoCentavos;
    valor = Math.round(Math.max(item.precoCentavos - promocional, 0) * item.quantidade);
  } else if (promocao.leve && promocao.pague) {
    // Leve 3, pague 2: a cada 3 unidades inteiras, uma sai de graça.
    const gratis = Math.floor(item.quantidade / promocao.leve) * (promocao.leve - promocao.pague);
    valor = item.precoCentavos * gratis;
  }
  return Math.min(valor, bruto);
}

/** A promoção que vale no item (a de maior desconto), ou null. */
export function promocaoDoItem(
  item: ItemCarrinho,
  comCliente: boolean,
): { promocao: PromocaoPDV; centavos: number } | null {
  let melhor: { promocao: PromocaoPDV; centavos: number } | null = null;
  for (const promocao of item.promocoes ?? []) {
    if (promocao.so_clientes && !comCliente) continue;
    const centavos = descontoDaPromocao(promocao, item);
    if (centavos > (melhor?.centavos ?? 0)) melhor = { promocao, centavos };
  }
  return melhor;
}

export function descontoPromocoes(carrinho: Carrinho): number {
  return carrinho.itens.reduce((soma, item) => soma + (promocaoDoItem(item, !!carrinho.cliente)?.centavos ?? 0), 0);
}

export function subtotal(carrinho: Carrinho): number {
  return carrinho.itens.reduce((soma, item) => soma + totalItem(item), 0);
}

/** Desconto que os pontos dão, arredondado para baixo como no servidor. */
export function valorDosPontos(pontos: number, valorPonto: string): number {
  return Math.floor(Math.round(pontos * Number(valorPonto) * 1_000_000) / 10_000);
}

/** Desconto da empresa conveniada, sobre o que sobra depois das promoções. Mesma conta do servidor. */
export function descontoConvenio(carrinho: Carrinho): number {
  const percentual = Number(carrinho.cliente?.convenio?.desconto ?? 0);
  if (!percentual) return 0;
  const base = Math.max(subtotal(carrinho) - descontoPromocoes(carrinho), 0);
  return Math.round((base * percentual) / 100 + 1e-9);
}

export function descontoPontos(carrinho: Carrinho): number {
  const pontos = carrinho.pontosResgatados ?? 0;
  if (!pontos || !carrinho.cliente?.pontos) return 0;
  return valorDosPontos(pontos, carrinho.cliente.pontos.valorPonto);
}

/** Quantos pontos dá para usar sem passar do valor da compra. */
export function maximoDePontos(carrinho: Carrinho): number {
  const pontos = carrinho.cliente?.pontos;
  if (!pontos) return 0;
  const restante = Math.max(
    subtotal(carrinho) - descontoPromocoes(carrinho) - descontoConvenio(carrinho) - carrinho.descontoCentavos,
    0,
  );
  const porValor = Math.floor((restante / 100 + 1e-9) / Number(pontos.valorPonto));
  return Math.max(Math.min(pontos.saldo, porValor), 0);
}

export function total(carrinho: Carrinho): number {
  return (
    Math.max(
      subtotal(carrinho) -
        descontoPromocoes(carrinho) -
        descontoConvenio(carrinho) -
        carrinho.descontoCentavos -
        descontoPontos(carrinho),
      0,
    ) + (carrinho.taxaEntregaCentavos ?? 0)
  );
}

/** Quanto o governo paga em um item: o valor do programa por unidade, nunca mais que o preço. Igual ao servidor. */
export function governoNoItem(item: ItemCarrinho, comCliente: boolean): number {
  if (!item.popularCentavos) return 0;
  const cobrado = totalItem(item) - (promocaoDoItem(item, comCliente)?.centavos ?? 0);
  return Math.min(cobrado, Math.round(item.popularCentavos * item.quantidade));
}

/** Itens do carrinho que estão na Farmácia Popular. */
export function itensDoPopular(carrinho: Carrinho): ItemCarrinho[] {
  return carrinho.itens.filter((item) => governoNoItem(item, !!carrinho.cliente) > 0);
}

/** A parte do governo, quando a venda é pela Farmácia Popular. Entra como um pagamento. */
export function parteDoGoverno(carrinho: Carrinho): number {
  if (!carrinho.popular) return 0;
  return carrinho.itens.reduce((soma, item) => soma + governoNoItem(item, !!carrinho.cliente), 0);
}

export function pago(carrinho: Carrinho): number {
  return carrinho.pagamentos.reduce((soma, p) => soma + p.centavos, 0) + parteDoGoverno(carrinho);
}

export function falta(carrinho: Carrinho): number {
  return Math.max(total(carrinho) - pago(carrinho), 0);
}

export function troco(carrinho: Carrinho): number {
  return Math.max(pago(carrinho) - total(carrinho), 0);
}

/** Itens pedidos acima do saldo disponível (o servidor recusaria a venda). */
export function itensSemSaldo(carrinho: Carrinho): ItemCarrinho[] {
  return carrinho.itens.filter((item) => item.quantidade > item.saldo);
}

/** O que impede de finalizar, ou null se está tudo certo. */
/** Receita que cada lista pede, com os códigos do SNGPC (o servidor confere de novo). */
export const RECEITUARIO: Record<string, number> = {
  A1: 4, A2: 4, A3: 4, B1: 2, B2: 2, C2: 3, C1: 1, C4: 1, C5: 1, ATB: 5,
};

export const NOMES_RECEITUARIO: Record<number, string> = {
  1: "Receita de controle especial (2 vias)",
  2: "Notificação B (azul)",
  3: "Notificação de receita especial",
  4: "Notificação A (amarela)",
  5: "Receita de antibiótico (2 vias)",
};

/** O tipo de receita que a venda pede, ou null se não tem remédio controlado. */
export function receituarioDoCarrinho(carrinho: Carrinho): number | null {
  const item = carrinho.itens.find((i) => i.controle && RECEITUARIO[i.controle]);
  return item ? RECEITUARIO[item.controle as string] : null;
}

export function problemaParaFinalizar(carrinho: Carrinho): string | null {
  if (carrinho.itens.length === 0) return "Nenhum item na venda";
  const tipo = receituarioDoCarrinho(carrinho);
  if (tipo && carrinho.receita?.tipo_receituario !== tipo) return "Venda com remédio controlado: preencha a receita (F5)";
  if (carrinho.popular) {
    if (parteDoGoverno(carrinho) === 0) return "Nenhum remédio desta venda está na Farmácia Popular. Tire os dados (Alt+7).";
    if (parteDoGoverno(carrinho) > total(carrinho)) return "Com os descontos, a venda ficou menor que a parte do governo";
  }
  if (falta(carrinho) > 0) return "Pagamento não cobre o total";
  const emDinheiro = carrinho.pagamentos
    .filter((p) => p.forma === "dinheiro")
    .reduce((soma, p) => soma + p.centavos, 0);
  if (troco(carrinho) > emDinheiro) return "Troco só pode sair de pagamento em dinheiro";
  const aPrazo = carrinho.pagamentos.filter((p) => p.forma === "prazo").reduce((soma, p) => soma + p.centavos, 0);
  if (aPrazo > 0 && !carrinho.cliente) return "Escolha o cliente da venda a prazo (Alt+5)";
  const noConvenio = carrinho.pagamentos.filter((p) => p.forma === "convenio").reduce((soma, p) => soma + p.centavos, 0);
  if (noConvenio > 0) {
    const convenio = carrinho.cliente?.convenio;
    if (!convenio) return "Escolha o funcionário da empresa conveniada (F8)";
    if (noConvenio > convenio.disponivelCentavos) {
      return `${carrinho.cliente?.nome} só pode comprar mais ${(convenio.disponivelCentavos / 100).toFixed(2).replace(".", ",")} no convênio`;
    }
  }
  const pontos = carrinho.pontosResgatados ?? 0;
  if (pontos > 0) {
    if (!carrinho.cliente?.pontos) return "Escolha o cliente para usar os pontos (F8)";
    if (pontos > carrinho.cliente.pontos.saldo) return `${carrinho.cliente.nome} tem só ${carrinho.cliente.pontos.saldo} pontos`;
    if (pontos < carrinho.cliente.pontos.minimo) return `O mínimo para trocar é ${carrinho.cliente.pontos.minimo} pontos`;
    const restante =
      subtotal(carrinho) -
      descontoPromocoes(carrinho) -
      descontoConvenio(carrinho) -
      carrinho.descontoCentavos -
      descontoPontos(carrinho);
    if (restante < 0) {
      return "Os pontos valem mais que a compra. Use menos pontos (F9).";
    }
  }
  if (carrinho.cliente && aPrazo > carrinho.cliente.disponivelCentavos) {
    return `${carrinho.cliente.nome} só pode comprar mais ${(carrinho.cliente.disponivelCentavos / 100).toFixed(2).replace(".", ",")} a prazo`;
  }
  return null;
}

export function montarVenda(carrinho: Carrinho, cpf?: string) {
  return {
    chave_idempotencia: carrinho.chave,
    itens: carrinho.itens.map((item) => ({ produto_id: item.produtoId, quantidade: String(item.quantidade) })),
    pagamentos: [
      ...(parteDoGoverno(carrinho) > 0 ? [{ forma: "popular", valor: centavosParaApi(parteDoGoverno(carrinho)) }] : []),
      ...carrinho.pagamentos.map((p) => ({ forma: p.forma, valor: centavosParaApi(p.centavos) })),
    ],
    desconto: centavosParaApi(carrinho.descontoCentavos),
    cliente_cpf: cpf || null,
    cliente_id: carrinho.cliente?.id ?? null,
    pontos_resgatados: carrinho.pontosResgatados ?? 0,
    pre_venda_id: carrinho.preVenda?.id ?? null,
    receita: receituarioDoCarrinho(carrinho) ? (carrinho.receita ?? null) : null,
    popular: carrinho.popular ?? null,
  };
}

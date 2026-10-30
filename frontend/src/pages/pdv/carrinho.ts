// Regras do carrinho do PDV, sem React, para poder testar isoladamente.
// Valores em dinheiro ficam em centavos (inteiros) para não ter erro de arredondamento.

import type { FormaPagamento, ProdutoPDV } from "../../api/tipos";

export interface ItemCarrinho {
  produtoId: string;
  descricao: string;
  precoCentavos: number;
  quantidade: number;
  saldo: number;
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
  /** Cliente da venda a prazo, com quanto ainda pode comprar. */
  cliente?: ClienteFiado;
}

export interface ClienteFiado {
  id: string;
  nome: string;
  disponivelCentavos: number;
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

export function subtotal(carrinho: Carrinho): number {
  return carrinho.itens.reduce((soma, item) => soma + totalItem(item), 0);
}

export function total(carrinho: Carrinho): number {
  return Math.max(subtotal(carrinho) - carrinho.descontoCentavos, 0);
}

export function pago(carrinho: Carrinho): number {
  return carrinho.pagamentos.reduce((soma, p) => soma + p.centavos, 0);
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
export function problemaParaFinalizar(carrinho: Carrinho): string | null {
  if (carrinho.itens.length === 0) return "Nenhum item na venda";
  if (falta(carrinho) > 0) return "Pagamento não cobre o total";
  const emDinheiro = carrinho.pagamentos
    .filter((p) => p.forma === "dinheiro")
    .reduce((soma, p) => soma + p.centavos, 0);
  if (troco(carrinho) > emDinheiro) return "Troco só pode sair de pagamento em dinheiro";
  const aPrazo = carrinho.pagamentos.filter((p) => p.forma === "prazo").reduce((soma, p) => soma + p.centavos, 0);
  if (aPrazo > 0 && !carrinho.cliente) return "Escolha o cliente da venda a prazo (Alt+5)";
  if (carrinho.cliente && aPrazo > carrinho.cliente.disponivelCentavos) {
    return `${carrinho.cliente.nome} só pode comprar mais ${(carrinho.cliente.disponivelCentavos / 100).toFixed(2).replace(".", ",")} a prazo`;
  }
  return null;
}

export function montarVenda(carrinho: Carrinho, cpf?: string) {
  return {
    chave_idempotencia: carrinho.chave,
    itens: carrinho.itens.map((item) => ({ produto_id: item.produtoId, quantidade: String(item.quantidade) })),
    pagamentos: carrinho.pagamentos.map((p) => ({ forma: p.forma, valor: centavosParaApi(p.centavos) })),
    desconto: centavosParaApi(carrinho.descontoCentavos),
    cliente_cpf: cpf || null,
    cliente_id: carrinho.cliente?.id ?? null,
    pre_venda_id: carrinho.preVenda?.id ?? null,
  };
}

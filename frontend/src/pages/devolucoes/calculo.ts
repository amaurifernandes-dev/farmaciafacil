// Contas da tela de devolução, sem React, para poder testar. Seguem as do servidor.

import type { Devolucao, ItemDevolvivel } from "../../api/tipos";

/** "1.000" (API) -> 1; "1,5" (digitado) -> 1.5. Vazio ou inválido: 0. */
export function lerQuantidade(texto: string): number {
  const numero = Number(texto.trim().replace(",", "."));
  return Number.isFinite(numero) && numero > 0 ? numero : 0;
}

/** Valor já devolvido de cada item da venda, em centavos. */
export function devolvidoPorItem(devolucoes: Devolucao[]): Record<string, number> {
  const soma: Record<string, number> = {};
  for (const d of devolucoes) {
    for (const i of d.itens) soma[i.venda_item_id] = (soma[i.venda_item_id] ?? 0) + Math.round(Number(i.valor) * 100);
  }
  return soma;
}

/**
 * Quanto o cliente recebe por `quantidade` do item, em centavos.
 * Devolvendo tudo o que falta, leva o restante exato (os centavos do arredondamento).
 */
export function valorDoItem(item: ItemDevolvivel, quantidade: number, jaDevolvidoCentavos: number): number {
  if (quantidade <= 0) return 0;
  const pago = Math.round(Number(item.valor_pago) * 100);
  if (Math.abs(quantidade - Number(item.disponivel)) < 1e-9) return pago - jaDevolvidoCentavos;
  return Math.round((pago * quantidade) / Number(item.quantidade));
}

/** Motivo pronto para o gerente só tocar. */
export const MOTIVOS = ["Troca por outro produto", "Produto com defeito", "Comprou errado", "Desistiu da compra"];

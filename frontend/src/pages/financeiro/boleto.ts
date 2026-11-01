import type { BoletoLido } from "../../api/tipos";

export const soNumeros = (texto: string) => texto.replace(/\D/g, "");

/** Já tem números suficientes para conferir: código de barras (44) ou linha digitável (47 ou 48). */
export function codigoCompleto(texto: string): boolean {
  return [44, 47, 48].includes(soNumeros(texto).length);
}

/** Conta de consumo vai para "Água, luz, telefone"; prefeitura e governo, para impostos; boleto, fornecedores. */
export function categoriaDoBoleto(lido: BoletoLido): string {
  if (lido.tipo === "bancario") return "fornecedores";
  if (["Água e esgoto", "Energia elétrica e gás", "Telefone e internet"].includes(lido.segmento ?? "")) return "contas_consumo";
  if (["Prefeitura", "Órgão do governo", "Multa de trânsito"].includes(lido.segmento ?? "")) return "impostos";
  return "outras";
}

export function descricaoDoBoleto(lido: BoletoLido): string {
  if (lido.tipo === "arrecadacao") return lido.segmento ? `Conta de ${lido.segmento.toLowerCase()}` : "Conta de consumo";
  return lido.banco_nome ? `Boleto ${lido.banco_nome}` : `Boleto banco ${lido.banco}`;
}

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** Formata centavos (inteiro) ou string decimal da API como R$ 0,00. */
export function reais(valor: number | string, emCentavos = typeof valor === "number"): string {
  const numero = typeof valor === "string" ? Number(valor) : valor;
  return moeda.format(emCentavos ? numero / 100 : numero);
}

export function quantidade(valor: string | number): string {
  return Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 3 });
}

export function data(iso: string | null): string {
  if (!iso) return "-";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

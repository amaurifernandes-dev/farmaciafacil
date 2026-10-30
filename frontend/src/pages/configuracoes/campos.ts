import type { Campo } from "../../components/Cadastro";

// Campos de endereço e contato, iguais em clientes, fornecedores e lojas.
export const CAMPOS_ENDERECO: Campo[] = [
  { nome: "cep", rotulo: "CEP", inputMode: "numeric" },
  { nome: "endereco", rotulo: "Endereço e número" },
  { nome: "bairro", rotulo: "Bairro" },
  { nome: "cidade", rotulo: "Cidade" },
  { nome: "uf", rotulo: "UF" },
];

/** 12345678901 -> 123.456.789-01; 12345678000190 -> 12.345.678/0001-90. */
export function documento(valor: string | null): string {
  if (!valor) return "-";
  if (valor.length === 11) return valor.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  if (valor.length === 14) return valor.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  return valor;
}

export function telefone(valor: string | null): string {
  if (!valor) return "-";
  return valor.replace(/(\d{2})(\d{4,5})(\d{4})/, "($1) $2-$3");
}

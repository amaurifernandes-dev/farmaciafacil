import type { FormaServico, TipoServico } from "../../api/tipos";

export const NOMES_TIPO: Record<TipoServico, string> = {
  pressao: "Pressão arterial",
  glicemia: "Glicemia capilar",
  temperatura: "Temperatura",
  injetavel: "Aplicação de injetável",
  outro: "Outro serviço",
};

export const NOMES_FORMA: Record<FormaServico, string> = {
  dinheiro: "Dinheiro",
  pix: "Pix",
  debito: "Cartão de débito",
  credito: "Cartão de crédito",
  cortesia: "Cortesia (sem cobrar)",
};

export interface CampoResultado {
  nome: string;
  rotulo: string;
  tipo?: "numero" | "texto" | "data" | "check" | "select";
  opcoes?: { valor: string; rotulo: string }[];
  obrigatorio?: boolean;
  dica?: string;
}

export const CAMPOS_RESULTADO: Record<TipoServico, CampoResultado[]> = {
  pressao: [
    { nome: "sistolica", rotulo: "Máxima (sistólica)", tipo: "numero", obrigatorio: true, dica: "mmHg, ex.: 120" },
    { nome: "diastolica", rotulo: "Mínima (diastólica)", tipo: "numero", obrigatorio: true, dica: "mmHg, ex.: 80" },
    { nome: "frequencia", rotulo: "Batimentos por minuto", tipo: "numero" },
    {
      nome: "braco",
      rotulo: "Braço",
      tipo: "select",
      opcoes: [
        { valor: "", rotulo: "-" },
        { valor: "esquerdo", rotulo: "Esquerdo" },
        { valor: "direito", rotulo: "Direito" },
      ],
    },
  ],
  glicemia: [
    { nome: "valor", rotulo: "Glicemia (mg/dL)", tipo: "numero", obrigatorio: true },
    { nome: "jejum", rotulo: "Em jejum (8 horas ou mais sem comer)", tipo: "check" },
  ],
  temperatura: [{ nome: "graus", rotulo: "Temperatura (°C)", tipo: "numero", obrigatorio: true, dica: "ex.: 36,5" }],
  injetavel: [
    { nome: "medicamento", rotulo: "Medicamento", obrigatorio: true },
    { nome: "dose", rotulo: "Dose", obrigatorio: true, dica: "ex.: 2 ml" },
    {
      nome: "via",
      rotulo: "Via",
      tipo: "select",
      obrigatorio: true,
      opcoes: [
        { valor: "IM", rotulo: "Intramuscular (IM)" },
        { valor: "SC", rotulo: "Subcutânea (SC)" },
        { valor: "ID", rotulo: "Intradérmica (ID)" },
      ],
    },
    { nome: "local", rotulo: "Local da aplicação", dica: "ex.: glúteo direito" },
    { nome: "lote", rotulo: "Lote do medicamento" },
    { nome: "validade", rotulo: "Validade", tipo: "data" },
    { nome: "prescritor", rotulo: "Quem receitou", obrigatorio: true },
    { nome: "prescritor_crm", rotulo: "CRM", obrigatorio: true },
    { nome: "prescritor_uf", rotulo: "UF do CRM" },
    { nome: "receita_data", rotulo: "Data da receita", tipo: "data", obrigatorio: true },
  ],
  outro: [{ nome: "descricao", rotulo: "O que foi feito", obrigatorio: true }],
};

/** Monta o objeto de resultados para a API: números com ponto, vazios fora. */
export function montarResultados(tipo: TipoServico, valores: Record<string, string | boolean>) {
  const saida: Record<string, string | number | boolean> = {};
  for (const campo of CAMPOS_RESULTADO[tipo]) {
    const valor = valores[campo.nome];
    if (campo.tipo === "check") {
      saida[campo.nome] = Boolean(valor);
      continue;
    }
    const texto = String(valor ?? "").trim();
    if (!texto) continue;
    if (campo.tipo === "numero") {
      const numero = Number(texto.replace(",", "."));
      saida[campo.nome] = Number.isFinite(numero) ? numero : texto;
    } else {
      saida[campo.nome] = texto;
    }
  }
  return saida;
}

export function idade(nascimento: string | null, em = new Date()): number | null {
  if (!nascimento) return null;
  const [a, m, d] = nascimento.split("-").map(Number);
  let anos = em.getFullYear() - a;
  if (em.getMonth() + 1 < m || (em.getMonth() + 1 === m && em.getDate() < d)) anos -= 1;
  return anos;
}

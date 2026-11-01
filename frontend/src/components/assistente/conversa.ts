import type { CartaoGuia, Fala, MensagemModelo } from "./tipos";

const CHAVE_CONVERSA = "ff.assistente.conversa";
const CHAVE_GUIA = "ff.assistente.guia";

export interface Conversa {
  historico: MensagemModelo[];
  falas: Fala[];
}

export const CONVERSA_VAZIA: Conversa = { historico: [], falas: [] };

/** A conversa fica na aba do navegador: sobrevive a trocar de tela, some ao fechar a aba ou sair. */
export function lerConversa(armazem: Storage = sessionStorage): Conversa {
  try {
    const bruto = armazem.getItem(CHAVE_CONVERSA);
    const lida = bruto ? (JSON.parse(bruto) as Conversa) : null;
    return lida && Array.isArray(lida.historico) && Array.isArray(lida.falas) ? lida : CONVERSA_VAZIA;
  } catch {
    return CONVERSA_VAZIA;
  }
}

export function salvarConversa(conversa: Conversa, armazem: Storage = sessionStorage) {
  try {
    if (conversa.falas.length === 0) armazem.removeItem(CHAVE_CONVERSA);
    else armazem.setItem(CHAVE_CONVERSA, JSON.stringify(conversa));
  } catch {
    // Sem espaço ou bloqueado: a conversa só não sobrevive à troca de tela.
  }
}

export interface GuiaAtivo extends CartaoGuia {
  feitos: number[];
}

export function lerGuia(armazem: Storage = sessionStorage): GuiaAtivo | null {
  try {
    const bruto = armazem.getItem(CHAVE_GUIA);
    return bruto ? (JSON.parse(bruto) as GuiaAtivo) : null;
  } catch {
    return null;
  }
}

export function salvarGuia(guia: GuiaAtivo | null, armazem: Storage = sessionStorage) {
  try {
    if (guia) armazem.setItem(CHAVE_GUIA, JSON.stringify(guia));
    else armazem.removeItem(CHAVE_GUIA);
  } catch {
    // Idem.
  }
}

/** O passo a passo aparece na tela do guia e nas telas abaixo dela (ex.: /compras/notas/123). */
export function guiaNestaTela(guia: GuiaAtivo | null, pathname: string): boolean {
  if (!guia) return false;
  return pathname === guia.rota || pathname.startsWith(`${guia.rota}/`);
}

export function marcarPasso(guia: GuiaAtivo, indice: number): GuiaAtivo {
  const feitos = guia.feitos.includes(indice) ? guia.feitos.filter((i) => i !== indice) : [...guia.feitos, indice];
  return { ...guia, feitos: feitos.sort((a, b) => a - b) };
}

/** Desconto da promoção em reais, para o cartão de produtos. */
export function economia(preco: string, precoFinal: string): number {
  return Math.max(0, Math.round((Number(preco) - Number(precoFinal)) * 100) / 100);
}

/** Ao sair, a conversa (que pode ter dados de clientes) e o guia aberto somem. */
export function esquecerConversa(armazem: Storage = sessionStorage) {
  try {
    armazem.removeItem(CHAVE_CONVERSA);
    armazem.removeItem(CHAVE_GUIA);
  } catch {
    // nada guardado
  }
}

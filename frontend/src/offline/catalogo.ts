// Procura no catálogo guardado, igual o servidor faria: pelo código de barras ou pelo nome.

import type { ProdutoPDV } from "../api/tipos";

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function porCodigo(produtos: ProdutoPDV[], codigo: string): ProdutoPDV | null {
  const limpo = codigo.trim();
  return produtos.find((p) => p.ean === limpo || p.codigos?.some((c) => c.ean === limpo)) ?? null;
}

export function porNome(produtos: ProdutoPDV[], termo: string, limite = 20): ProdutoPDV[] {
  const palavras = semAcento(termo).split(/\s+/).filter(Boolean);
  if (palavras.length === 0) return [];
  return produtos
    .filter((p) => {
      const texto = semAcento(`${p.nome} ${p.apresentacao ?? ""} ${p.fabricante ?? ""}`);
      return palavras.every((palavra) => texto.includes(palavra));
    })
    .slice(0, limite);
}

/** Depois de uma venda offline, o saldo da cópia baixa para o próximo cliente ver o certo. */
export function baixarSaldos(produtos: ProdutoPDV[], vendidos: { produtoId: string; quantidade: number }[]): ProdutoPDV[] {
  const tirar = new Map<string, number>();
  for (const v of vendidos) tirar.set(v.produtoId, (tirar.get(v.produtoId) ?? 0) + v.quantidade);
  return produtos.map((p) =>
    tirar.has(p.id) ? { ...p, saldo: String(Math.max(Number(p.saldo) - (tirar.get(p.id) ?? 0), 0)) } : p,
  );
}

/** Falha de conexão (sem internet, servidor fora), e não uma recusa do servidor. */
export function ehFalhaDeRede(erro: unknown): boolean {
  if (erro instanceof TypeError) return true; // fetch não conseguiu conectar
  const status = (erro as { status?: number } | null)?.status;
  return status === 502 || status === 503 || status === 504;
}

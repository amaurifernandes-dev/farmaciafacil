// Guarda no próprio computador (IndexedDB) a cópia do catálogo e as vendas feitas sem internet.
// IndexedDB e não localStorage: aguenta milhares de produtos e não some ao fechar o navegador.

import type { ProdutoPDV } from "../api/tipos";

export interface CatalogoLocal {
  gerado_em: string;
  loja_id: string;
  desconto_maximo_caixa: string;
  produtos: ProdutoPDV[];
}

export interface VendaGuardada {
  chave: string;
  /** O corpo do POST /vendas, pronto para reenviar igual. */
  corpo: Record<string, unknown> & { chave_idempotencia: string; offline_em: string };
  total_centavos: number;
  itens: number;
  guardada_em: string;
  /** Recusada pelo servidor: o motivo, para o gerente resolver. */
  problema?: string;
}

const NOME = "farmaciafacil-caixa";
const CATALOGO = "catalogo";
const FILA = "fila";

function abrir(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const pedido = indexedDB.open(NOME, 1);
    pedido.onupgradeneeded = () => {
      const banco = pedido.result;
      if (!banco.objectStoreNames.contains(CATALOGO)) banco.createObjectStore(CATALOGO);
      if (!banco.objectStoreNames.contains(FILA)) banco.createObjectStore(FILA, { keyPath: "chave" });
    };
    pedido.onsuccess = () => resolve(pedido.result);
    pedido.onerror = () => reject(pedido.error);
  });
}

async function operar<T>(loja: string, modo: IDBTransactionMode, acao: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const banco = await abrir();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transacao = banco.transaction(loja, modo);
      const pedido = acao(transacao.objectStore(loja));
      transacao.oncomplete = () => resolve(pedido.result as T);
      transacao.onerror = () => reject(transacao.error);
      transacao.onabort = () => reject(transacao.error);
    });
  } finally {
    banco.close();
  }
}

export const salvarCatalogo = (catalogo: CatalogoLocal) =>
  operar<void>(CATALOGO, "readwrite", (s) => s.put(catalogo, "atual"));

export const lerCatalogo = () =>
  operar<CatalogoLocal | undefined>(CATALOGO, "readonly", (s) => s.get("atual")).catch(() => undefined);

export const guardarVenda = (venda: VendaGuardada) => operar<void>(FILA, "readwrite", (s) => s.put(venda));

export const vendasGuardadas = () =>
  operar<VendaGuardada[]>(FILA, "readonly", (s) => s.getAll())
    .then((lista) => lista.sort((a, b) => a.guardada_em.localeCompare(b.guardada_em)))
    .catch(() => [] as VendaGuardada[]);

export const tirarDaFila = (chave: string) => operar<void>(FILA, "readwrite", (s) => s.delete(chave));

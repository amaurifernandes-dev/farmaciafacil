/** O que o servidor do assistente devolve, e os cartões que a tela mostra junto da resposta. */

export interface ItemProduto {
  produto_id: string;
  nome: string;
  apresentacao: string | null;
  fabricante: string | null;
  preco: string;
  preco_final: string;
  promocao: string | null;
  so_clientes: boolean;
  estoque: string;
}

export interface CartaoGuia {
  tipo: "guia";
  id: string;
  titulo: string;
  rota: string;
  passos: string[];
}

export type Cartao =
  | { tipo: "produtos"; termos: string[]; itens: ItemProduto[] }
  | {
      tipo: "pre_venda";
      id: string;
      numero: number;
      total: string;
      /** O caixa aplica as promoções ao receber; aqui vai a estimativa sem cliente identificado. */
      total_com_promocoes: string;
      itens: { descricao: string; quantidade: string; total: string }[];
    }
  | { tipo: "cliente"; id: string; nome: string }
  | CartaoGuia;

/** Mensagem no formato da API do Claude: a tela guarda e manda de volta sem mexer. */
export interface MensagemModelo {
  role: "user" | "assistant";
  content: Record<string, unknown>[];
}

export interface RespostaAssistente {
  historico: MensagemModelo[];
  resposta: string;
  cartoes: Cartao[];
}

/** O que aparece no balão da conversa. */
export interface Fala {
  de: "eu" | "assistente";
  texto: string;
  cartoes?: Cartao[];
  erro?: boolean;
}

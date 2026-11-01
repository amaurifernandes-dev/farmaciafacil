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
  | CartaoGuia
  | CartaoVendas
  | CartaoTabela
  | CartaoPedidoCompra;

/** Pedido de compra separado por fornecedor. O usuário copia, envia ou salva em Compras > Pedidos. */
export interface CartaoPedidoCompra {
  tipo: "pedido_compra";
  loja: string | null;
  loja_id?: string | null;
  data: string;
  total: string;
  itens: number;
  grupos: {
    fornecedor_id: string | null;
    fornecedor: string;
    telefone: string | null;
    whatsapp: string | null;
    email: string | null;
    total: string;
    sem_custo: number;
    texto: string;
    itens: {
      produto_id: string;
      nome: string;
      ean: string | null;
      quantidade: number;
      custo: string;
      /** Custo como número decimal ("3.0000"), para gravar no pedido. */
      custo_unitario?: string | null;
      total: string;
    }[];
  }[];
}

/** Resumo das vendas de um período. Os valores já vêm formatados do servidor. */
export interface CartaoVendas {
  tipo: "vendas";
  titulo: string;
  periodo: string;
  indicadores: { rotulo: string; valor: string }[];
  /** % em relação ao período anterior de mesmo tamanho; null se não houve venda nele. */
  variacao: number | null;
  anterior: string;
  comparado_com: string;
  formas: { forma: string; valor: string }[];
  vendedores: { nome: string; vendas: number; total: string }[];
  rota: string;
}

export interface CartaoTabela {
  tipo: "tabela";
  titulo: string;
  subtitulo: string;
  colunas: { rotulo: string; num: boolean }[];
  linhas: string[][];
  vazio: string;
  rota: string;
  rotulo_rota?: string;
}

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

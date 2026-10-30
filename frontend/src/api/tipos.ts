// Tipos espelhando as respostas da API. Valores em dinheiro e quantidades
// chegam como string ("8.90") para não perder precisão.

export type Papel = "admin" | "gerente" | "farmaceutico" | "caixa" | "atendente" | "estoque";

export interface Sessao {
  access_token: string;
  usuario_id: string;
  farmacia_id: string;
  nome: string;
  papel: Papel;
}

export interface Produto {
  id: string;
  ean: string | null;
  nome: string;
  apresentacao: string | null;
  fabricante: string | null;
  ncm: string | null;
  cest: string | null;
  unidade: string;
  preco_venda: string;
  preco_custo: string | null;
  estoque_minimo: string;
  controla_lote: boolean;
  tipo: "medicamento" | "perfumaria" | "outros";
  registro_ms: string | null;
  ativo: boolean;
  codigos: { id: string; ean: string }[];
}

export interface ProdutoPDV extends Produto {
  saldo: string;
}

export interface PaginaProdutos {
  itens: Produto[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export interface Caixa {
  id: string;
  usuario_id: string;
  terminal_id: string | null;
  loja_id: string | null;
  status: "aberto" | "fechado";
  valor_abertura: string;
  aberto_em: string;
  fechado_em: string | null;
  valor_fechamento_informado: string | null;
}

export interface ResumoCaixa {
  caixa: Caixa;
  operador: string;
  terminal: string | null;
  loja: string | null;
  quantidade_vendas: number;
  total_vendido: string;
  por_forma: Record<string, string>;
  dinheiro_esperado: string;
  diferenca: string | null;
}

export type FormaPagamento = "dinheiro" | "debito" | "credito" | "pix";

export interface Venda {
  id: string;
  numero: number;
  caixa_id: string;
  status: "finalizada" | "cancelada";
  subtotal: string;
  desconto: string;
  total: string;
  troco: string;
  itens: { id: string; descricao: string; quantidade: string; preco_unitario: string; total: string }[];
  pagamentos: { forma: FormaPagamento; valor: string }[];
  finalizada_em: string;
  motivo_cancelamento: string | null;
}

export interface Lote {
  id: string;
  produto_id: string;
  numero_lote: string;
  validade: string | null;
  quantidade: string;
}

export interface LoteComProduto extends Lote {
  produto_nome: string;
  dias_para_vencer: number | null;
}

export interface Alertas {
  vencidos: LoteComProduto[];
  vencendo: LoteComProduto[];
  abaixo_do_minimo: { produto_id: string; nome: string; saldo: string; estoque_minimo: string }[];
}

export interface Painel {
  farmacia: string;
  uf: string;
  hoje: string;
  vendas_hoje: string;
  quantidade_vendas_hoje: number;
  ticket_medio_hoje: string;
  vendas_ontem: string;
  semana: { data: string; total: string; quantidade: number }[];
  caixas_abertos: number;
  meu_caixa_aberto: boolean;
  produtos_ativos: number;
  lotes_vencidos: number;
  lotes_vencendo: number;
  dias_alerta_vencimento: number;
  clientes: number;
  abaixo_do_minimo: number;
}

export type ModoCaixa = "mono" | "multi";

export interface Loja {
  id: string;
  nome: string;
  matriz: boolean;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  inscricao_estadual: string | null;
  telefone: string | null;
  email: string | null;
  cep: string | null;
  endereco: string | null;
  bairro: string | null;
  cidade: string | null;
  uf: string;
  responsavel_tecnico: string | null;
  crf: string | null;
  modo_caixa: ModoCaixa;
  terminal_central_id: string | null;
  ativo: boolean;
}

export interface Terminal {
  id: string;
  loja_id: string;
  nome: string;
  ativo: boolean;
  vinculado: boolean;
  vinculado_em: string | null;
  ultimo_uso_em: string | null;
  pode_receber: boolean;
  central: boolean;
  caixa_aberto_id: string | null;
}

export interface EsteTerminal {
  terminal: Terminal;
  loja: Loja;
  pode_receber: boolean;
  motivo: string | null;
}

export interface Configuracoes {
  desconto_maximo_caixa: string;
  dias_alerta_vencimento: number;
}

export interface ItemPreVenda {
  produto_id: string;
  ean: string | null;
  descricao: string;
  quantidade: string;
  preco_unitario: string;
  total: string;
}

export interface PreVenda {
  id: string;
  numero: number;
  loja_id: string;
  vendedor: string;
  status: "aberta" | "recebida" | "cancelada";
  itens: ItemPreVenda[];
  total: string;
  cliente_cpf: string | null;
  criado_em: string;
}

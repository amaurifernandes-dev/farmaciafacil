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
  cfop: string | null;
  icms_origem: string;
  icms_situacao_tributaria: string | null;
  pis_cofins_situacao_tributaria: string | null;
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
  /** Promoções que valem hoje nesta loja; o carrinho escolhe a melhor. */
  promocoes?: PromocaoPDV[];
}

export type TipoPromocao = "percentual" | "preco_fixo" | "leve_pague";

export interface PromocaoPDV {
  id: string;
  nome: string;
  tipo: TipoPromocao;
  percentual: string | null;
  preco: string | null;
  leve: number | null;
  pague: number | null;
  so_clientes: boolean;
  resumo: string;
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
  recebimentos_dinheiro: string;
  dinheiro_esperado: string;
  diferenca: string | null;
}

export type FormaPagamento = "dinheiro" | "debito" | "credito" | "pix" | "prazo";

export interface Venda {
  id: string;
  numero: number;
  caixa_id: string;
  status: "finalizada" | "cancelada";
  subtotal: string;
  desconto: string;
  total: string;
  troco: string;
  cliente_id?: string | null;
  pontos_ganhos?: number;
  pontos_resgatados?: number;
  desconto_pontos?: string;
  itens: { id: string; descricao: string; quantidade: string; preco_unitario: string; total: string }[];
  pagamentos: { forma: FormaPagamento; valor: string }[];
  finalizada_em: string;
  motivo_cancelamento: string | null;
  nota: NotaFiscal | null;
}

export interface NotaFiscal {
  id: string;
  status: "processando" | "autorizada" | "rejeitada" | "cancelada" | "erro";
  numero: string | null;
  serie: string | null;
  chave: string | null;
  mensagem: string | null;
  url_danfe: string | null;
}

export interface Lote {
  id: string;
  loja_id: string;
  produto_id: string;
  numero_lote: string;
  validade: string | null;
  quantidade: string;
}

export interface LoteComProduto extends Lote {
  produto_nome: string;
  loja_nome: string;
  dias_para_vencer: number | null;
}

export interface Alertas {
  vencidos: LoteComProduto[];
  vencendo: LoteComProduto[];
  abaixo_do_minimo: {
    produto_id: string;
    nome: string;
    loja_id: string;
    loja_nome: string;
    saldo: string;
    estoque_minimo: string;
  }[];
}

export interface SaldoProduto {
  produto_id: string;
  nome: string;
  apresentacao: string | null;
  ean: string | null;
  estoque_minimo: string;
  total: string;
  /** Saldo vendável por id da loja. */
  por_loja: Record<string, string>;
  vencido: string;
}

export interface PaginaSaldos {
  itens: SaldoProduto[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export type StatusNotaEntrada = "pendente" | "confirmada" | "cancelada";

export interface NotaEntradaResumo {
  id: string;
  loja_id: string;
  fornecedor_id: string;
  fornecedor_nome: string;
  chave: string;
  numero: number;
  serie: number;
  emitida_em: string;
  valor_produtos: string;
  valor_total: string;
  status: StatusNotaEntrada;
  criado_em: string;
  confirmada_em: string | null;
  quantidade_itens: number;
  itens_sem_produto: number;
}

export interface ItemNotaEntrada {
  id: string;
  ordem: number;
  codigo_fornecedor: string;
  ean: string | null;
  descricao: string;
  ncm: string | null;
  cest: string | null;
  registro_ms: string | null;
  unidade: string;
  quantidade: string;
  valor_unitario: string;
  valor_total: string;
  numero_lote: string | null;
  validade: string | null;
  produto_id: string | null;
  produto_nome: string | null;
  produto_controla_lote: boolean | null;
  fator: number;
}

export interface NotaEntrada extends NotaEntradaResumo {
  itens: ItemNotaEntrada[];
}

export interface PrecoFornecedor {
  fornecedor_id: string;
  fornecedor_nome: string;
  custo_unitario: string;
  comprado_em: string;
}

export interface ItemSugestao {
  produto_id: string;
  nome: string;
  apresentacao: string | null;
  ean: string | null;
  saldo: string;
  estoque_minimo: string;
  vendido_no_periodo: string;
  media_diaria: string;
  dias_de_estoque: string | null;
  sugerido: string;
  ultimo_custo: string | null;
  fornecedores: PrecoFornecedor[];
}

export interface SugestaoCompras {
  loja_id: string;
  dias_historico: number;
  dias_cobertura: number;
  itens: ItemSugestao[];
  total_estimado: string;
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
  dias_prazo_padrao: number;
  fidelidade_ativa: boolean;
  pontos_por_real: string;
  valor_ponto: string;
  pontos_minimo_resgate: number;
  pontos_validade_meses: number | null;
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

export type TipoConta = "pagar" | "receber";
export type SituacaoConta = "abertas" | "vencidas" | "pagas" | "canceladas" | "todas";

export interface Conta {
  id: string;
  tipo: TipoConta;
  loja_id: string;
  descricao: string;
  categoria: string;
  fornecedor_id: string | null;
  cliente_id: string | null;
  pessoa: string | null;
  documento: string | null;
  parcela: number;
  parcelas: number;
  valor: string;
  vencimento: string;
  status: "aberta" | "paga" | "cancelada";
  vencida: boolean;
  pago_em: string | null;
  valor_pago: string | null;
  forma_pagamento: string | null;
  nota_entrada_id: string | null;
  venda_id: string | null;
  observacao: string | null;
  criado_em: string;
}

export interface TotaisContas {
  vencidas: string;
  quantidade_vencidas: number;
  vence_hoje: string;
  proximos_7_dias: string;
  em_aberto: string;
  pago_no_mes: string;
}

export interface PaginaContas {
  itens: Conta[];
  total: number;
  soma: string;
  totais: TotaisContas;
}

export interface CreditoCliente {
  cliente_id: string;
  nome: string;
  limite: string;
  em_aberto: string;
  disponivel: string;
  vencido: string;
  contas: Conta[];
}

export interface DiaFluxo {
  data: string;
  vendas: string;
  recebimentos: string;
  pagamentos: string;
  previsto_receber: string;
  previsto_pagar: string;
  saldo: string;
  acumulado: string;
}

export interface FluxoCaixa {
  inicio: string;
  fim: string;
  dias: DiaFluxo[];
  entradas: string;
  saidas: string;
  resultado: string;
  vencido_receber: string;
  vencido_pagar: string;
}

export interface Categorias {
  pagar: { id: string; nome: string }[];
  receber: { id: string; nome: string }[];
}

export interface Cliente {
  id: string;
  nome: string;
  cpf: string | null;
  data_nascimento: string | null;
  telefone: string | null;
  email: string | null;
  cep: string | null;
  endereco: string | null;
  bairro: string | null;
  cidade: string | null;
  uf: string | null;
  aceita_ofertas: boolean;
  consentimento_em: string | null;
  observacoes: string | null;
  limite_credito: string | null;
  ativo: boolean;
  criado_em: string;
  /** Só na listagem. */
  pontos?: number;
  ultima_compra?: string | null;
}

export interface MovimentoPontos {
  id: string;
  tipo: "ganho" | "resgate" | "estorno" | "ajuste" | "expirado";
  pontos: number;
  venda_id: string | null;
  venda_numero: number | null;
  observacao: string | null;
  criado_em: string;
}

export interface Pontos {
  ativo: boolean;
  saldo: number;
  valor: string;
  valor_ponto: string;
  minimo_resgate: number;
  pode_resgatar: boolean;
  expiram_em: string | null;
  movimentos: MovimentoPontos[];
}

export interface FichaCliente {
  cliente: Cliente;
  compras: {
    quantidade: number;
    total: string;
    ticket_medio: string;
    primeira: string | null;
    ultima: string | null;
    dias_sem_comprar: number | null;
  };
  pontos: Pontos;
  fiado_em_aberto: string;
  fiado_vencido: string;
  produtos_frequentes: { produto_id: string; descricao: string; vezes: number; quantidade: string; ultima: string }[];
  ultimas_compras: {
    id: string;
    numero: number;
    finalizada_em: string;
    status: "finalizada" | "cancelada";
    total: string;
    itens: number;
    formas: FormaPagamento[];
    pontos_ganhos: number;
    pontos_resgatados: number;
  }[];
}

export interface Promocao extends PromocaoPDV {
  inicio: string;
  fim: string | null;
  loja_id: string | null;
  ativa: boolean;
  situacao: "vigente" | "agendada" | "encerrada" | "pausada";
  produtos: { id: string; nome: string; preco_venda: string; preco_promocional: string | null }[];
  resultado: { vendas: number; unidades: string; faturado: string; desconto: string };
  criado_em: string;
}

export interface ResumoVendas {
  quantidade: number;
  faturamento: string;
  descontos: string;
  descontos_promocao: string;
  ticket_medio: string;
  custo: string;
  lucro_bruto: string;
  margem: string;
  itens_sem_custo: number;
  canceladas: number;
  valor_cancelado: string;
}

export interface RelatorioVendas {
  inicio: string;
  fim: string;
  resumo: ResumoVendas;
  anterior: ResumoVendas;
  por_dia: { data: string; quantidade: number; total: string }[];
  por_forma: { forma: FormaPagamento; valor: string }[];
  por_operador: { nome: string; quantidade: number; total: string }[];
}

export interface RelatorioProdutos {
  inicio: string;
  fim: string;
  faturamento: string;
  produtos: {
    produto_id: string;
    nome: string;
    quantidade: string;
    faturamento: string;
    custo: string | null;
    lucro: string | null;
    margem: string | null;
    participacao: string;
    curva: "A" | "B" | "C";
  }[];
  curva_a: number;
  curva_b: number;
  curva_c: number;
}

export interface RelatorioParados {
  dias: number;
  valor_total: string;
  produtos: {
    produto_id: string;
    nome: string;
    saldo: string;
    custo_unitario: string | null;
    valor_parado: string | null;
    ultima_venda: string | null;
    dias_parado: number | null;
    validade_mais_proxima: string | null;
  }[];
}

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
  vende_online: boolean;
  registro_ms: string | null;
  /** Lista da Portaria 344 ou "ATB" (antibiótico). Vazio: não é controlado. */
  controle: ListaControle | null;
  embalagem_sngpc: "caixa" | "frasco";
  /** Farmácia Popular: quanto o governo paga por caixa. Vazio: fora do programa. */
  popular_valor: string | null;
  /** % de comissão do vendedor. Vazio: a padrão da farmácia. */
  comissao: string | null;
  ativo: boolean;
  codigos: { id: string; ean: string }[];
}

export type ListaControle = "A1" | "A2" | "A3" | "B1" | "B2" | "C1" | "C2" | "C3" | "C4" | "C5" | "ATB";

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

export type FormaPagamento = "dinheiro" | "debito" | "credito" | "pix" | "prazo" | "convenio" | "popular";

export interface Venda {
  id: string;
  numero: number;
  caixa_id: string;
  status: "finalizada" | "cancelada";
  subtotal: string;
  desconto: string;
  total: string;
  troco: string;
  taxa_entrega?: string;
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
  faltas_no_periodo: string;
  encomendas_abertas: string;
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
  encomendas_chegaram: number;
  pedidos_novos: number;
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
  codigo_municipio: string | null;
  uf: string;
  responsavel_tecnico: string | null;
  crf: string | null;
  responsavel_cpf: string | null;
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
  loja_online_ativa: boolean;
  loja_online_endereco: string | null;
  loja_online_loja_id: string | null;
  loja_online_mensagem: string | null;
  whatsapp: string | null;
  entrega_ativa: boolean;
  entrega_minimo: string;
  entrega_area: string | null;
  entrega_taxa: string;
  entrega_gratis_acima: string | null;
  entrega_bairros: TaxaBairro[];
  pix_chave: string | null;
  pix_nome: string | null;
  pix_cidade: string | null;
  pix_no_site: boolean;
  popular_validade_receita: number;
  popular_intervalo_dias: number;
  comissao_padrao: string;
}

export interface TaxaBairro {
  bairro: string;
  taxa: string;
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
  entrega: boolean;
  /** Já somada no total. */
  taxa_entrega: string;
  /** Pix do site já confirmado: o caixa recebe como Pix. */
  pago_antecipado: string;
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
  convenio_id: string | null;
  convenio_matricula: string | null;
  convenio_limite: string | null;
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

export type SituacaoFalta = "encomendas" | "chegaram" | "avisados" | "faltas" | "encerradas" | "todas";

export interface Falta {
  id: string;
  loja_id: string;
  loja_nome: string;
  produto_id: string | null;
  descricao: string;
  quantidade: string;
  cliente_id: string | null;
  nome: string | null;
  telefone: string | null;
  observacao: string | null;
  status: "registrada" | "aberta" | "avisado" | "entregue" | "cancelada";
  origem: "balcao" | "pdv";
  encomenda: boolean;
  saldo: string | null;
  chegou: boolean;
  usuario_nome: string;
  criado_em: string;
  avisado_em: string | null;
  finalizada_em: string | null;
}

export interface ListaFaltas {
  resumo: {
    encomendas: number;
    chegaram: number;
    avisados: number;
    faltas_30_dias: number;
    mais_pedidos: { produto_id: string | null; descricao: string; vezes: number; quantidade: string }[];
  };
  itens: Falta[];
}

export type StatusPedido = "novo" | "separando" | "pronto" | "saiu" | "entregue" | "cancelado";
export type FormaPedido = "dinheiro" | "cartao" | "pix";

export interface ItemPedido {
  produto_id: string;
  descricao: string;
  quantidade: string;
  preco_unitario: string;
  desconto: string;
  total: string;
}

export interface Pedido {
  id: string;
  numero: number;
  codigo: string;
  canal: "site" | "whatsapp" | "telefone";
  loja_id: string;
  loja_nome: string;
  cliente_id: string | null;
  nome: string;
  telefone: string;
  entrega: boolean;
  endereco: string | null;
  forma_pagamento: FormaPedido;
  troco_para: string | null;
  observacao: string | null;
  bairro: string | null;
  taxa_entrega: string;
  total: string;
  status: StatusPedido;
  motivo_cancelamento: string | null;
  pix_copia_e_cola: string | null;
  pix_pago_em: string | null;
  pre_venda_numero: number | null;
  pago: boolean;
  itens: ItemPedido[];
  criado_em: string;
  atualizado_em: string;
}

export interface ListaPedidos {
  resumo: { novo: number; separando: number; pronto: number; saiu: number; entregues_hoje: number; total_hoje: string };
  pedidos: Pedido[];
}

export interface LojaPublica {
  nome: string;
  mensagem: string | null;
  whatsapp: string | null;
  telefone: string | null;
  endereco: string | null;
  cidade: string | null;
  uf: string;
  entrega: boolean;
  entrega_minimo: string;
  entrega_area: string | null;
  entrega_taxa: string;
  entrega_gratis_acima: string | null;
  bairros: TaxaBairro[];
  pix: boolean;
}

export interface ProdutoPublico {
  id: string;
  nome: string;
  apresentacao: string | null;
  fabricante: string | null;
  preco: string;
  preco_promocional: string | null;
  promocao: string | null;
  maximo: number;
}

export interface PedidoPublico {
  numero: number;
  codigo: string;
  status: StatusPedido;
  entrega: boolean;
  forma_pagamento: FormaPedido;
  troco_para: string | null;
  taxa_entrega: string;
  total: string;
  itens: ItemPedido[];
  criado_em: string;
  motivo_cancelamento: string | null;
  pix_copia_e_cola: string | null;
  pix_pago: boolean;
}

export type Regime = "simples" | "presumido" | "real";

export interface ConfiguracaoFiscal {
  ambiente: "homologacao" | "producao";
  emitir_automaticamente: boolean;
  cfop_padrao: string;
  icms_situacao_tributaria_padrao: string;
  pis_cofins_situacao_tributaria_padrao: string;
  regime: Regime;
  perfil_efd: "A" | "B" | "C";
  contador_nome: string | null;
  contador_cpf: string | null;
  contador_crc: string | null;
  contador_email: string | null;
}

export interface LinhaCfop {
  cfop: string;
  cst: string;
  valor: string;
  icms: string;
  icms_st: string;
}

export interface FechamentoFiscal {
  mes: string;
  inicio: string;
  fim: string;
  loja_id: string;
  loja_nome: string;
  cnpj: string;
  regime: Regime;
  saidas: {
    vendas: number;
    total_vendido: string;
    nfce_autorizadas: number;
    valor_nfce: string;
    nfce_canceladas: number;
    por_cfop: LinhaCfop[];
  };
  entradas: { notas: number; valor_total: string; icms: string; icms_st: string; ipi: string; por_cfop: LinhaCfop[] };
  pgdas: { normal: string; icms_st: string; monofasico: string; st_e_monofasico: string; total: string };
  pendencias: { tipo: string; texto: string; quantidade: number }[];
  sped_disponivel: boolean;
}

// --- Remédios controlados (SNGPC) ---

/** Dados da receita que o balconista copia na venda de controlado. Os códigos são os do SNGPC. */
export interface Receita {
  tipo_receituario: number;
  numero_notificacao: string | null;
  data_prescricao: string;
  prescritor_nome: string;
  prescritor_conselho: "CRM" | "CRMV" | "CRO" | "CRF" | "RMS";
  prescritor_numero: string;
  prescritor_uf: string;
  uso_prolongado: boolean;
  comprador_nome: string | null;
  comprador_tipo_documento: number | null;
  comprador_documento: string | null;
  comprador_orgao: string | null;
  comprador_uf: string | null;
  paciente_nome: string | null;
  paciente_idade: number | null;
  paciente_unidade_idade: 1 | 2;
  paciente_sexo: 1 | 2 | null;
  cid: string | null;
}

export interface LinhaLivro {
  data: string;
  produto_id: string;
  produto: string;
  lista: string;
  lote: string;
  tipo: string;
  entrada: string;
  saida: string;
  saldo: string;
  documento: string | null;
  receita: string | null;
  pessoa: string | null;
}

export interface SaldoControlado {
  lote_id: string;
  produto_id: string;
  produto: string;
  lista: string;
  registro_ms: string | null;
  lote: string;
  validade: string | null;
  quantidade: string;
}

export interface ResumoControlados {
  loja_id: string;
  inicio: string;
  fim: string;
  totais: { entradas: string; vendas: string; perdas: string; transferencias: string };
  pendencias: { codigo: string; texto: string; bloqueia: boolean }[];
  saldos: SaldoControlado[];
  livro: LinhaLivro[];
}

// --- Convênios com empresas ---

export interface Convenio {
  id: string;
  nome: string;
  cnpj: string | null;
  contato: string | null;
  telefone: string | null;
  email: string | null;
  desconto: string;
  limite_padrao: string;
  dia_fechamento: number;
  dias_para_pagar: number;
  observacao: string | null;
  ativo: boolean;
  criado_em: string;
  funcionarios: number;
  em_aberto: string;
  a_receber: string;
  /** Último fechamento previsto: as compras até esta data vão para a fatura. */
  fechamento: string;
  pronto_para_fechar: boolean;
}

export interface FuncionarioConvenio {
  cliente_id: string;
  nome: string;
  cpf: string | null;
  matricula: string | null;
  limite: string;
  usado: string;
  disponivel: string;
  ativo: boolean;
}

export interface CompraConvenio {
  id: string;
  venda_id: string;
  venda_numero: number;
  cliente_id: string;
  nome: string;
  matricula: string | null;
  data: string;
  valor: string;
  status: string;
  conta_id: string | null;
}

export interface FaturaConvenio {
  conta_id: string;
  descricao: string;
  valor: string;
  vencimento: string;
  status: "aberta" | "paga";
  vencida: boolean;
  pago_em: string | null;
  compras: number;
}

export interface ConvenioDetalhe {
  convenio: Convenio;
  funcionarios: FuncionarioConvenio[];
  compras_abertas: CompraConvenio[];
  faturas: FaturaConvenio[];
}

export interface ConvenioDoCliente {
  convenio_id: string;
  nome: string;
  desconto: string;
  limite: string;
  usado: string;
  disponivel: string;
}

/** O que o balconista copia da receita e do autorizador do governo, na venda pela Farmácia Popular. */
export interface DadosPopular {
  paciente_cpf: string;
  paciente_nome: string;
  prescritor_crm: string;
  prescritor_uf: string;
  receita_data: string;
  autorizacao: string;
}

export interface ItemPopular {
  produto_id: string;
  descricao: string;
  quantidade: string;
  total: string;
  governo: string;
}

export interface VendaPopular extends DadosPopular {
  id: string;
  venda_id: string;
  loja_id: string;
  numero: number;
  data: string;
  itens: ItemPopular[];
  valor_governo: string;
  valor_paciente: string;
  status: "aberta" | "lancada";
  conta_id: string | null;
}

export interface MesPopular {
  mes: string;
  vendas: VendaPopular[];
  quantidade: number;
  pacientes: number;
  total_governo: string;
  total_paciente: string;
  em_aberto: string;
  lancamentos: Conta[];
  pode_lancar: boolean;
}

export type MotivoEtiqueta =
  | "nunca_impressa"
  | "preco_subiu"
  | "preco_baixou"
  | "promocao_comecou"
  | "promocao_acabou"
  | "promocao_mudou";

export interface EtiquetaItem {
  produto_id: string;
  nome: string;
  apresentacao: string | null;
  fabricante: string | null;
  ean: string | null;
  unidade: string;
  preco: string;
  preco_promocional: string | null;
  promocao: string | null;
  promocao_fim: string | null;
  saldo: string;
  impressa: { preco: string; preco_promocional: string | null; promocao: string | null; impressa_em: string } | null;
  motivo: MotivoEtiqueta | null;
}

export interface ListaEtiquetas {
  loja_id: string;
  itens: EtiquetaItem[];
  para_trocar: number;
  nunca_impressas: number;
  preco_mudou: number;
  promocao: number;
}

export interface VendedorComissao {
  usuario_id: string;
  nome: string;
  papel: Papel;
  recebe_comissao: boolean;
  vendas: number;
  vendido: string;
  comissao: string;
  ticket_medio: string;
  percentual: string;
}

export interface RelatorioComissoes {
  inicio: string;
  fim: string;
  comissao_padrao: string;
  vendedores: VendedorComissao[];
  total_vendido: string;
  total_comissao: string;
}

export interface DetalheVendedor {
  inicio: string;
  fim: string;
  vendedor: VendedorComissao;
  vendas: { venda_id: string; numero: number; finalizada_em: string; vendido: string; comissao: string; pre_venda: boolean }[];
  produtos: { produto_id: string; descricao: string; quantidade: string; vendido: string; percentual: string; comissao: string }[];
}

import type { Sessao } from "./api/tipos";
import type { NomeIcone } from "./components/Icone";
import type { Modulo } from "./modulos";
import { atende, cuidaDoEstoque, ehAdmin, ehFarmaceutico, ehGerente, podeReceber } from "./sessao";

/** Grupos do menu lateral, na ordem em que aparecem. */
export const GRUPOS = [
  { id: "dia", rotulo: "Dia a dia" },
  { id: "farmacia", rotulo: "Farmácia" },
  { id: "estoque", rotulo: "Estoque e compras" },
  { id: "gestao", rotulo: "Gestão" },
  { id: "config", rotulo: "Configurações" },
] as const;

export type Grupo = (typeof GRUPOS)[number]["id"];

export interface Tela {
  para: string;
  rotulo: string;
  icone: NomeIcone;
  grupo: Grupo;
  /** Uma frase sobre a tela, mostrada na busca. */
  descricao: string;
  /** Outros nomes que as pessoas usam para achar a tela na busca. */
  palavras?: string;
  /** Quem pode ver. Sem isto, todos os perfis. */
  pode?: (sessao: Sessao | null) => boolean;
  /** Fica marcado também nas páginas abaixo deste caminho. */
  agrupa?: boolean;
  /** Aba dentro de outra tela: aparece só na busca, não no menu. */
  aba?: boolean;
  /** Função que o administrador pode desligar no Gerenciamento de telas. */
  modulo?: Modulo;
}

const naoGerente = (s: Sessao | null) => atende(s) && !ehGerente(s);

/** Todas as telas da gestão. O menu e a busca saem daqui, filtrados pelo perfil de quem entrou. */
export const TELAS: Tela[] = [
  // Dia a dia
  { para: "/", rotulo: "Visão geral", icone: "painel", grupo: "dia", descricao: "Resumo do dia, avisos e atalhos", palavras: "inicio painel dashboard home" },
  { para: "/vendas", rotulo: "Vendas / PDV", icone: "carrinho", grupo: "dia", agrupa: true, pode: atende, descricao: "Vendas do dia e entrada no caixa", palavras: "venda pdv cupom balcao" },
  { para: "/vendas/pre-venda", rotulo: "Nova pré-venda", icone: "carrinho", grupo: "dia", aba: true, pode: atende, descricao: "Separar os produtos do cliente para pagar no caixa", palavras: "orcamento pre venda" },
  { para: "/pdv", rotulo: "Abrir o caixa (PDV)", icone: "caixa", grupo: "dia", aba: true, pode: podeReceber, descricao: "Tela cheia do caixa para receber", palavras: "frente de caixa receber pagamento" },
  { para: "/pedidos", rotulo: "Pedidos", icone: "recibo", modulo: "pedidos", grupo: "dia", pode: atende, descricao: "Pedidos da loja online, WhatsApp e telefone", palavras: "site delivery entrega whatsapp" },
  { para: "/clientes", rotulo: "Clientes", icone: "pessoa", grupo: "dia", agrupa: true, pode: atende, descricao: "Cadastro, histórico de compras, pontos e fiado", palavras: "cliente cadastro fiado pontos fidelidade" },
  { para: "/faltas", rotulo: "Faltas e encomendas", icone: "sino", modulo: "faltas", grupo: "dia", descricao: "O que o cliente pediu e não tinha", palavras: "encomenda falta reserva" },
  { para: "/caixas", rotulo: "Caixas", icone: "caixa", grupo: "dia", agrupa: true, pode: podeReceber, descricao: "Abrir, fechar e conferir os caixas", palavras: "abertura fechamento sangria suprimento pdv" },
  { para: "/caixas/fechamento-do-dia", rotulo: "Fechamento do dia", icone: "recibo", grupo: "dia", aba: true, pode: ehGerente, descricao: "Todos os caixas do dia por forma de pagamento, sangrias e diferenças", palavras: "fechamento caixa conferencia sangria diferenca relatorio do dia" },
  { para: "/devolucoes", rotulo: "Trocas e devoluções", icone: "troca", modulo: "devolucoes", grupo: "dia", pode: ehGerente, descricao: "Devolver itens de uma venda e vale-troca", palavras: "troca devolucao vale estorno" },
  { para: "/vendas-offline", rotulo: "Vendas sem internet", icone: "alerta", grupo: "dia", pode: ehGerente, descricao: "Vendas feitas sem internet que precisam de atenção", palavras: "offline sem internet recusadas" },

  // Farmácia
  { para: "/controlados", rotulo: "Controlados", icone: "remedio", modulo: "controlados", grupo: "farmacia", pode: ehFarmaceutico, descricao: "Livro de controlados e envio ao SNGPC", palavras: "sngpc portaria 344 receita anvisa" },
  { para: "/servicos", rotulo: "Serviços farmacêuticos", icone: "estetoscopio", modulo: "servicos", grupo: "farmacia", pode: ehFarmaceutico, descricao: "Pressão, glicemia, injetáveis e declarações", palavras: "servico pressao glicemia injecao aplicacao" },
  { para: "/popular", rotulo: "Farmácia Popular", icone: "remedio", modulo: "popular", grupo: "farmacia", pode: ehGerente, descricao: "Vendas do programa do governo e o que receber", palavras: "popular governo gratuidade" },
  { para: "/convenios", rotulo: "Convênios", icone: "loja", modulo: "convenios", grupo: "farmacia", agrupa: true, pode: ehGerente, descricao: "Empresas conveniadas e faturas do mês", palavras: "convenio empresa fatura" },

  // Estoque e compras
  { para: "/estoque", rotulo: "Estoque", icone: "pacote", grupo: "estoque", agrupa: true, descricao: "Alertas de estoque baixo, vencendo e vencido", palavras: "alerta vencimento validade minimo" },
  { para: "/estoque/saldos", rotulo: "Saldo por loja", icone: "pacote", grupo: "estoque", aba: true, descricao: "Quanto tem de cada produto em cada loja", palavras: "saldo quantidade estoque" },
  { para: "/estoque/inventario", rotulo: "Inventário", icone: "pacote", grupo: "estoque", aba: true, descricao: "Contagem do estoque e ajuste das diferenças", palavras: "contagem balanco inventario" },
  { para: "/estoque/entrada", rotulo: "Entrada manual", icone: "entrada", grupo: "estoque", aba: true, pode: cuidaDoEstoque, descricao: "Dar entrada sem nota fiscal", palavras: "entrada ajuste lote" },
  { para: "/estoque/transferencia", rotulo: "Transferir entre lojas", icone: "troca", grupo: "estoque", aba: true, pode: cuidaDoEstoque, descricao: "Mandar produtos de uma loja para outra", palavras: "transferencia filial" },
  { para: "/compras", rotulo: "Compras", icone: "caminhao", grupo: "estoque", agrupa: true, pode: cuidaDoEstoque, descricao: "Notas de entrada pelo XML", palavras: "nota fiscal xml nfe entrada fornecedor" },
  { para: "/compras/pedidos", rotulo: "Pedidos de compra", icone: "caminhao", grupo: "estoque", aba: true, pode: cuidaDoEstoque, descricao: "O que foi pedido a cada fornecedor e o que chegou", palavras: "pedido compra fornecedor distribuidora" },
  { para: "/compras/sugestao", rotulo: "Sugestão de compras", icone: "caminhao", grupo: "estoque", aba: true, pode: cuidaDoEstoque, descricao: "O que comprar pelo ritmo de vendas", palavras: "sugestao reposicao comprar" },
  { para: "/etiquetas", rotulo: "Etiquetas de preço", icone: "etiqueta", modulo: "etiquetas", grupo: "estoque", descricao: "Imprimir e trocar etiquetas de gôndola", palavras: "etiqueta preco gondola imprimir" },

  // Gestão
  { para: "/financeiro", rotulo: "Financeiro", icone: "dinheiro", grupo: "gestao", agrupa: true, pode: ehGerente, descricao: "Contas a pagar", palavras: "contas pagar boleto despesa" },
  { para: "/financeiro/receber", rotulo: "Contas a receber", icone: "dinheiro", grupo: "gestao", aba: true, pode: ehGerente, descricao: "Fiado, convênios e cartões a receber", palavras: "receber fiado cartao" },
  { para: "/financeiro/fluxo", rotulo: "Fluxo de caixa", icone: "dinheiro", grupo: "gestao", aba: true, pode: ehGerente, descricao: "Entradas e saídas previstas", palavras: "fluxo caixa saldo" },
  { para: "/relatorios", rotulo: "Relatórios", icone: "grafico", grupo: "gestao", pode: ehGerente, descricao: "Vendas, mais vendidos, curva ABC e parados", palavras: "relatorio abc margem lucro" },
  { para: "/promocoes", rotulo: "Promoções", icone: "etiqueta", modulo: "promocoes", grupo: "gestao", pode: ehGerente, descricao: "Preços promocionais por período", palavras: "promocao oferta desconto" },
  { para: "/metas", rotulo: "Metas de vendas", icone: "alvo", modulo: "metas", grupo: "gestao", pode: ehGerente, descricao: "Metas do mês por loja e por vendedor", palavras: "meta objetivo" },
  { para: "/comissoes", rotulo: "Comissões", icone: "pessoas", modulo: "comissoes", grupo: "gestao", pode: ehGerente, descricao: "Quanto cada vendedor ganhou", palavras: "comissao vendedor" },
  { para: "/comissoes", rotulo: "Minhas vendas", icone: "grafico", modulo: "comissoes", grupo: "dia", pode: naoGerente, descricao: "Suas vendas, comissão e meta do mês", palavras: "minha comissao meta" },
  { para: "/fiscal", rotulo: "Fechamento fiscal", icone: "recibo", grupo: "gestao", pode: ehGerente, descricao: "SPED e arquivos do mês para o contador", palavras: "sped contador fiscal imposto" },

  // Configurações
  { para: "/configuracoes", rotulo: "Configurações", icone: "engrenagem", grupo: "config", aba: true, descricao: "Cadastros e configurações da farmácia", palavras: "cadastros ajustes" },
  { para: "/configuracoes/produtos", rotulo: "Produtos", icone: "pacote", grupo: "config", descricao: "Preços, códigos de barras e dados fiscais", palavras: "produto cadastro preco ean codigo" },
  { para: "/configuracoes/fornecedores", rotulo: "Fornecedores", icone: "caminhao", grupo: "config", pode: cuidaDoEstoque, descricao: "Distribuidoras e contatos de compra", palavras: "fornecedor distribuidora" },
  { para: "/configuracoes/usuarios", rotulo: "Usuários", icone: "pessoas", grupo: "config", pode: ehAdmin, descricao: "Quem acessa o sistema e o que pode fazer", palavras: "usuario senha perfil acesso funcionario" },
  { para: "/configuracoes/farmacia", rotulo: "Minha farmácia", icone: "loja", grupo: "config", pode: ehGerente, descricao: "Dados da farmácia, matriz e filiais", palavras: "loja filial matriz cnpj" },
  { para: "/configuracoes/telas", rotulo: "Gerenciamento de telas", icone: "painel", grupo: "config", pode: ehAdmin, descricao: "Ligar e desligar funções do sistema para todos", palavras: "modulos funcoes ligar desligar esconder habilitar telas" },
  { para: "/configuracoes/licenca", rotulo: "Licença", icone: "recibo", grupo: "config", pode: ehAdmin, descricao: "Validade, limites e renovação da licença do sistema", palavras: "licenca chave ativacao renovar vencimento contrato plano" },
  { para: "/configuracoes/gerais", rotulo: "Configurações gerais", icone: "ajustes", grupo: "config", pode: ehGerente, descricao: "Caixas, descontos, pontos, loja online e assistente de IA", palavras: "configuracao regras ia assistente pontos loja online" },
];

/** As telas que esta pessoa vê: pelo perfil e pelas funções ligadas no Gerenciamento de telas. */
export function telasDe(sessao: Sessao | null, ligado: (m: Modulo) => boolean = () => true): Tela[] {
  return TELAS.filter((t) => (!t.pode || t.pode(sessao)) && (!t.modulo || ligado(t.modulo)));
}

/** A função desligada a que este endereço pertence (para avisar em vez de abrir a tela). */
export function moduloDoEndereco(pathname: string): Modulo | undefined {
  if (pathname === "/") return undefined;
  return telaAtual(TELAS.filter((t) => t.modulo), pathname)?.modulo;
}

export function ativa(tela: Tela, pathname: string): boolean {
  if (tela.para === "/") return pathname === "/";
  return tela.agrupa ? pathname === tela.para || pathname.startsWith(`${tela.para}/`) : pathname === tela.para;
}

/** A tela mais específica que corresponde ao endereço (a aba ganha da tela principal). */
export function telaAtual(telas: Tela[], pathname: string): Tela | undefined {
  const candidatas = telas.filter((t) => pathname === t.para || (t.para !== "/" && pathname.startsWith(`${t.para}/`)));
  return candidatas.sort((a, b) => b.para.length - a.para.length)[0] ?? (pathname === "/" ? telas[0] : undefined);
}

function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Busca por pedaços de palavras, sem ligar para acento: "ped comp" acha "Pedidos de compra". */
export function buscarTelas(telas: Tela[], termo: string): Tela[] {
  const partes = normalizar(termo).split(/\s+/).filter(Boolean);
  if (!partes.length) return telas.filter((t) => !t.aba);
  const pontuadas = telas
    .map((t) => {
      const nome = normalizar(t.rotulo);
      const palavras = `${nome} ${normalizar(t.palavras ?? "")}`;
      const tudo = `${palavras} ${normalizar(t.descricao)}`;
      if (!partes.every((p) => tudo.includes(p))) return null;
      // Primeiro o nome que começa com o que foi digitado, depois o nome que contém, depois os apelidos, depois o resto.
      const pontos = nome.startsWith(partes[0])
        ? 0
        : partes.every((p) => nome.includes(p))
          ? 1
          : partes.every((p) => palavras.includes(p))
            ? 2
            : 3;
      return { t, pontos };
    })
    .filter((x): x is { t: Tela; pontos: number } => x !== null);
  return pontuadas.sort((a, b) => a.pontos - b.pontos).map((x) => x.t);
}

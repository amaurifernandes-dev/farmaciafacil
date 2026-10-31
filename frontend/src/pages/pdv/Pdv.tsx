import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ErroApi, mensagem } from "../../api/cliente";
import type {
  EsteTerminal,
  FormaPagamento,
  PaginaProdutos,
  PreVenda,
  Produto,
  ProdutoPDV,
  ResumoCaixa,
  Venda,
} from "../../api/tipos";
import { quantidade as fmtQtd, reais } from "../../formato";
import { useSessao } from "../../sessao";
import {
  adicionarProduto,
  alterarQuantidade,
  descontoConvenio,
  descontoPontos,
  descontoPromocoes,
  falta,
  governoNoItem,
  interpretarEntrada,
  itensDoPopular,
  itensSemSaldo,
  lerQuantidade,
  maximoDePontos,
  montarVenda,
  novoCarrinho,
  paraCentavos,
  parteDoGoverno,
  problemaParaFinalizar,
  promocaoDoItem,
  receituarioDoCarrinho,
  removerItem,
  subtotal,
  total,
  totalItem,
  troco,
  type Carrinho,
  type ItemCarrinho,
} from "./carrinho";
import type { Cliente as ClienteCadastro, ConvenioDoCliente, CreditoCliente, Pontos } from "../../api/tipos";
import { lerEsteTerminal } from "../caixas/Caixas";
import FecharCaixa from "./FecharCaixa";
import PopularDaVenda from "./PopularDaVenda";
import ReceitaDaVenda from "./ReceitaDaVenda";

type Modo =
  | "venda"
  | "busca"
  | "quantidade"
  | "desconto"
  | "pagamento"
  | "cliente"
  | "pontos"
  | "preVenda"
  | "falta"
  | "receita"
  | "popular"
  | "fechar";

/** O que o cliente pediu e não tinha, para anotar com F1 na lista de faltas. */
interface FaltaPendente {
  produtoId?: string;
  descricao: string;
  quantidade: number;
}

const FORMAS: { tecla: string; forma: FormaPagamento; nome: string }[] = [
  { tecla: "1", forma: "dinheiro", nome: "Dinheiro" },
  { tecla: "2", forma: "debito", nome: "Débito" },
  { tecla: "3", forma: "credito", nome: "Crédito" },
  { tecla: "4", forma: "pix", nome: "Pix" },
  { tecla: "5", forma: "prazo", nome: "A prazo" },
  { tecla: "6", forma: "convenio", nome: "Convênio" },
];

const CHAVE_VENDA = "ff.venda-em-andamento";

// A venda em andamento fica no navegador: se a página recarregar, nada se perde.
function carregarCarrinho(): Carrinho {
  try {
    const salvo = localStorage.getItem(CHAVE_VENDA);
    if (salvo) return JSON.parse(salvo) as Carrinho;
  } catch {
    /* ignora e começa do zero */
  }
  return novoCarrinho();
}

export default function Pdv() {
  const { sessao } = useSessao();
  const [terminal, setTerminal] = useState<EsteTerminal | null | undefined>(undefined);
  const [caixa, setCaixa] = useState<ResumoCaixa | null | undefined>(undefined);
  const [carrinho, setCarrinho] = useState<Carrinho>(carregarCarrinho);
  const [modo, setModo] = useState<Modo>("venda");
  const [texto, setTexto] = useState("");
  const [selecionado, setSelecionado] = useState(-1);
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string; link?: string; comprovante?: string } | null>(null);
  const [forma, setForma] = useState<FormaPagamento>("dinheiro");
  const [resultados, setResultados] = useState<ProdutoPDV[]>([]);
  const [indiceBusca, setIndiceBusca] = useState(0);
  const [clientes, setClientes] = useState<ClienteCadastro[]>([]);
  // De onde veio a escolha do cliente: da venda a prazo (Alt+5) ou do F8, e para onde voltar.
  const [clienteParaPrazo, setClienteParaPrazo] = useState(false);
  const [voltarPara, setVoltarPara] = useState<Modo>("venda");
  const [confirmarCancelar, setConfirmarCancelar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [faltaPendente, setFaltaPendente] = useState<FaltaPendente | null>(null);
  const campo = useRef<HTMLInputElement>(null);

  const atualizarCaixa = useCallback(async () => {
    try {
      const este = await lerEsteTerminal();
      setTerminal(este);
      if (!este?.pode_receber) return;
      setCaixa(await api<ResumoCaixa>("/caixas/atual"));
    } catch (e) {
      if (e instanceof ErroApi && e.status === 404) setCaixa(null);
      else setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }, []);

  useEffect(() => {
    atualizarCaixa();
  }, [atualizarCaixa]);

  useEffect(() => {
    localStorage.setItem(CHAVE_VENDA, JSON.stringify(carrinho));
  }, [carrinho]);

  // O campo principal nunca perde o foco: o leitor de código de barras "digita" nele.
  useEffect(() => {
    campo.current?.focus();
  });

  function mudarModo(novo: Modo) {
    setModo(novo);
    setTexto("");
    setConfirmarCancelar(false);
    if (novo === "pagamento") setTexto(falta(carrinho) ? (falta(carrinho) / 100).toFixed(2).replace(".", ",") : "");
  }

  function erro(textoErro: string) {
    setAviso({ tipo: "erro", texto: textoErro });
  }

  function textoValor(centavos: number) {
    return centavos ? (centavos / 100).toFixed(2).replace(".", ",") : "";
  }

  function identificarCliente(paraPrazo: boolean) {
    setClienteParaPrazo(paraPrazo);
    setVoltarPara(modo === "pagamento" ? "pagamento" : "venda");
    setClientes([]);
    setIndiceBusca(0);
    mudarModo("cliente");
  }

  /** F9: troca os pontos do cliente por desconto. */
  function usarPontos() {
    if (carrinho.itens.length === 0) return;
    const cliente = carrinho.cliente;
    if (!cliente) {
      identificarCliente(false);
      return setAviso({ tipo: "erro", texto: "Primeiro identifique o cliente (CPF, telefone ou nome)" });
    }
    if (!cliente.pontos) return erro("O programa de pontos está desligado. Ligue em Configurações gerais.");
    if (cliente.pontos.saldo < cliente.pontos.minimo) {
      return erro(`${cliente.nome} tem ${cliente.pontos.saldo} pontos. O mínimo para trocar é ${cliente.pontos.minimo}.`);
    }
    setVoltarPara(modo === "pagamento" ? "pagamento" : "venda");
    setModo("pontos");
    setTexto(String(maximoDePontos(carrinho)));
    setAviso({ tipo: "ok", texto: `${cliente.nome} tem ${cliente.pontos.saldo} pontos. Enter usa o máximo; 0 tira.` });
  }

  /** A prazo precisa de um cliente com limite: escolhe antes de lançar o valor. */
  function escolherForma(nova: FormaPagamento) {
    setForma(nova);
    if (nova === "prazo" && !carrinho.cliente) identificarCliente(true);
    if (nova === "convenio") {
      if (!carrinho.cliente) {
        identificarCliente(false);
        return setAviso({ tipo: "erro", texto: "Identifique o funcionário da empresa conveniada (CPF, telefone ou nome)" });
      }
      valorNoConvenio(carrinho);
    }
  }

  /** Alt+7: venda pela Farmácia Popular. */
  function abrirPopular() {
    if (carrinho.itens.length === 0) return;
    if (itensDoPopular(carrinho).length === 0 && !carrinho.popular) {
      return erro("Nenhum remédio desta venda está na Farmácia Popular. Marque no cadastro do produto quanto o governo paga.");
    }
    mudarModo("popular");
  }

  /** Sugere no campo o que cabe no convênio do cliente, ou avisa que ele não é conveniado. */
  function valorNoConvenio(atual: Carrinho) {
    const convenio = atual.cliente?.convenio;
    if (!convenio) {
      setForma("dinheiro");
      return erro(`${atual.cliente?.nome ?? "Este cliente"} não é de nenhuma empresa conveniada.`);
    }
    if (convenio.disponivelCentavos <= 0) {
      setForma("dinheiro");
      return erro(`${atual.cliente?.nome} já usou todo o limite do convênio ${convenio.nome}.`);
    }
    setTexto(textoValor(Math.min(falta(atual), convenio.disponivelCentavos)));
    setAviso({ tipo: "ok", texto: `Convênio ${convenio.nome}: pode comprar até ${reais(convenio.disponivelCentavos)}.` });
  }

  async function buscarCliente(termo: string) {
    if (!termo.trim()) return;
    try {
      const pagina = await api<{ itens: ClienteCadastro[] }>(`/clientes?busca=${encodeURIComponent(termo.trim())}&por_pagina=8`);
      if (pagina.itens.length === 0) return erro("Cliente não encontrado. Cadastre no menu Clientes.");
      if (pagina.itens.length === 1) return escolherCliente(pagina.itens[0]);
      setClientes(pagina.itens);
      setIndiceBusca(0);
      setAviso(null);
    } catch (e) {
      erro(mensagem(e));
    }
  }

  async function escolherCliente(cliente: ClienteCadastro) {
    try {
      const [credito, pontos, convenio] = await Promise.all([
        api<CreditoCliente>(`/financeiro/clientes/${cliente.id}/credito`),
        api<Pontos>(`/clientes/${cliente.id}/pontos`),
        cliente.convenio_id
          ? api<ConvenioDoCliente>(`/convenios/cliente/${cliente.id}`).catch(() => null)
          : Promise.resolve(null),
      ]);
      const temLimite = Number(credito.limite) > 0;
      const disponivel = temLimite ? Math.max(paraCentavos(credito.disponivel) ?? 0, 0) : 0;
      const atualizado: Carrinho = {
        ...carrinho,
        pontosResgatados: 0,
        cliente: {
          id: cliente.id,
          nome: cliente.nome,
          disponivelCentavos: disponivel,
          pontos: pontos.ativo
            ? { saldo: pontos.saldo, valorPonto: pontos.valor_ponto, minimo: pontos.minimo_resgate }
            : undefined,
          convenio: convenio
            ? {
                nome: convenio.nome,
                desconto: convenio.desconto,
                disponivelCentavos: Math.max(paraCentavos(convenio.disponivel) ?? 0, 0),
              }
            : undefined,
        },
      };
      setCarrinho(atualizado);
      setClientes([]);
      const sobrePontos = pontos.ativo
        ? ` ${pontos.saldo} pontos (${reais(pontos.valor)})${pontos.pode_resgatar ? ", F9 troca por desconto" : ""}.`
        : "";
      const vencido = Number(credito.vencido) > 0 ? ` Atenção: ${reais(credito.vencido)} de fiado vencido.` : "";

      const sobreConvenio = convenio
        ? ` Convênio ${convenio.nome}${Number(convenio.desconto) ? ` (${Number(convenio.desconto).toLocaleString("pt-BR")}% de desconto)` : ""}.`
        : "";
      if (!clienteParaPrazo) {
        setModo(voltarPara);
        if (voltarPara === "pagamento" && forma === "convenio") return valorNoConvenio(atualizado);
        setTexto(voltarPara === "pagamento" ? textoValor(falta(atualizado)) : "");
        return setAviso({
          tipo: vencido ? "erro" : "ok",
          texto: `Cliente: ${cliente.nome}.${sobreConvenio}${sobrePontos}${vencido}`,
        });
      }
      setClienteParaPrazo(false);
      setModo("pagamento");
      if (!temLimite || disponivel <= 0) {
        setForma("dinheiro");
        setTexto(textoValor(falta(atualizado)));
        return erro(
          temLimite
            ? `${cliente.nome} já usou todo o limite (deve ${reais(credito.em_aberto)}).`
            : `${cliente.nome} não tem limite para comprar a prazo.`,
        );
      }
      setForma("prazo");
      setTexto(textoValor(Math.min(falta(atualizado), disponivel)));
      setAviso(
        vencido
          ? { tipo: "erro", texto: `${vencido.trim()}` }
          : { tipo: "ok", texto: `${cliente.nome} pode comprar até ${reais(disponivel)} a prazo.${sobrePontos}` },
      );
    } catch (e) {
      erro(mensagem(e));
    }
  }

  async function adicionarPorCodigo(entrada: string) {
    const lido = interpretarEntrada(entrada);
    if (!lido) {
      // Não é código de barras: trata como busca por nome.
      if (entrada.trim()) await buscar(entrada);
      return;
    }
    try {
      const produto = await api<ProdutoPDV>(`/produtos/ean/${lido.codigo}`);
      incluir(produto, lido.quantidade);
    } catch (e) {
      setFaltaPendente({ descricao: "", quantidade: lido.quantidade });
      erro(`${lido.codigo}: ${mensagem(e)}. F1 anota na lista de faltas.`);
    }
  }

  function incluir(produto: ProdutoPDV, qtd: number) {
    const novo = adicionarProduto(carrinho, produto, qtd);
    setCarrinho(novo);
    setSelecionado(novo.itens.findIndex((item) => item.produtoId === produto.id));
    const semSaldo = itensSemSaldo(novo).find((item) => item.produtoId === produto.id);
    setFaltaPendente(null);
    setAviso(
      semSaldo
        ? {
            tipo: "erro",
            texto: `Atenção: só há ${fmtQtd(semSaldo.saldo)} de ${semSaldo.descricao} em estoque. F1 anota a falta.`,
          }
        : null,
    );
  }

  async function buscar(termo: string) {
    try {
      const pagina = await api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(termo)}&por_pagina=20`);
      if (pagina.itens.length === 0) {
        setFaltaPendente({ descricao: termo.trim(), quantidade: 1 });
        return erro(`Nenhum produto encontrado para "${termo}". F1 anota na lista de faltas.`);
      }
      // A listagem não traz saldo; o PDV consulta pelo EAN ao escolher.
      setResultados(pagina.itens.map((p) => ({ ...p, saldo: "0" })));
      setIndiceBusca(0);
      setModo("busca");
      setTexto(termo);
    } catch (e) {
      erro(mensagem(e));
    }
  }

  async function escolherDaBusca(produto: ProdutoPDV) {
    try {
      const completo = produto.ean ? await api<ProdutoPDV>(`/produtos/ean/${produto.ean}`) : produto;
      incluir(completo, 1);
    } catch (e) {
      erro(mensagem(e));
    }
    mudarModo("venda");
  }

  async function receberPreVenda(numeroDigitado: string) {
    const numero = Number(numeroDigitado.trim().replace("#", ""));
    if (!Number.isInteger(numero) || numero <= 0) return erro("Número de pré-venda inválido");
    if (carrinho.itens.length > 0) return erro("Finalize ou cancele a venda atual antes de receber uma pré-venda");
    try {
      const pre = await api<PreVenda>(`/pre-vendas/numero/${numero}`);
      if (pre.status !== "aberta") return erro(`A pré-venda nº ${numero} já foi ${pre.status}`);
      let novo: Carrinho = {
        ...novoCarrinho(),
        preVenda: { id: pre.id, numero: pre.numero },
        taxaEntregaCentavos: paraCentavos(pre.taxa_entrega) ?? 0,
      };
      for (const item of pre.itens) {
        // Busca o produto de novo para pegar o preço e o saldo de agora.
        const produto = item.ean
          ? await api<ProdutoPDV>(`/produtos/ean/${item.ean}`)
          : { ...(await api<Produto>(`/produtos/${item.produto_id}`)), saldo: item.quantidade };
        novo = adicionarProduto(novo, produto, Number(item.quantidade));
      }
      // Pix do site já confirmado pela equipe: entra como pagamento, falta só finalizar.
      const pagoAntes = paraCentavos(pre.pago_antecipado) ?? 0;
      if (pagoAntes > 0) novo = { ...novo, pagamentos: [{ forma: "pix", centavos: pagoAntes }] };
      setCarrinho(novo);
      setSelecionado(0);
      mudarModo("venda");
      const extra = [
        pre.entrega ? `entrega ${reais(paraCentavos(pre.taxa_entrega) ?? 0)}` : "",
        pagoAntes > 0 ? "Pix já pago pelo site" : "",
      ].filter(Boolean).join(", ");
      setAviso({
        tipo: "ok",
        texto: `Pré-venda nº ${numero} carregada (${pre.vendedor}${extra ? `; ${extra}` : ""}). Confira e receba com F4.`,
      });
    } catch (e) {
      erro(mensagem(e));
    }
  }

  /** F1: o que faltou é o item sem estoque selecionado, o último não encontrado, ou o que o caixa digitar. */
  function anotarFalta() {
    const item = carrinho.itens[selecionado];
    const pendente =
      item && item.quantidade > item.saldo
        ? { produtoId: item.produtoId, descricao: item.descricao, quantidade: item.quantidade - Math.max(item.saldo, 0) }
        : (faltaPendente ?? { descricao: "", quantidade: 1 });
    setFaltaPendente(pendente);
    setModo("falta");
    setTexto(pendente.descricao);
    const quem = carrinho.cliente ? ` Fica como encomenda de ${carrinho.cliente.nome}.` : " Para virar encomenda, identifique o cliente (F8) antes.";
    setAviso({ tipo: "ok", texto: `Confira o que faltou e aperte Enter.${quem}` });
  }

  async function registrarFalta(descricao: string) {
    const pendente = faltaPendente;
    // Se o caixa mudou o texto, não é mais o produto do carrinho.
    const produtoId = pendente?.produtoId && descricao.trim() === pendente.descricao ? pendente.produtoId : undefined;
    if (!produtoId && !descricao.trim()) return erro("Escreva o que o cliente pediu");
    try {
      await api("/faltas", {
        corpo: {
          produto_id: produtoId ?? null,
          descricao: descricao.trim(),
          quantidade: String(pendente?.quantidade ?? 1),
          cliente_id: carrinho.cliente?.id ?? null,
          origem: "pdv",
        },
      });
      setFaltaPendente(null);
      mudarModo("venda");
      setAviso({
        tipo: "ok",
        texto: carrinho.cliente
          ? `Encomenda anotada para ${carrinho.cliente.nome}. Quando chegar, aparece em Faltas e encomendas.`
          : `Falta anotada: ${descricao.trim()}. Ela entra na sugestão de compras.`,
      });
    } catch (e) {
      erro(mensagem(e));
    }
  }

  async function finalizar() {
    const problema = problemaParaFinalizar(carrinho);
    if (problema) return erro(problema);
    setEnviando(true);
    try {
      const venda = await api<Venda>("/vendas", { corpo: montarVenda(carrinho) });
      setCarrinho(novoCarrinho());
      setSelecionado(-1);
      mudarModo("venda");
      const ganhos = venda.pontos_ganhos ? ` ${carrinho.cliente?.nome} ganhou ${venda.pontos_ganhos} pontos.` : "";
      const textoTroco = (Number(venda.troco) > 0 ? ` Troco: ${reais(venda.troco)}` : "") + ganhos;
      const aviso = avisoDaVenda(venda, textoTroco);
      setAviso(
        carrinho.popular
          ? { ...aviso, texto: `${aviso.texto} Imprima o comprovante da Farmácia Popular para o paciente assinar.`, comprovante: `/popular/comprovante/${venda.id}` }
          : aviso,
      );
      atualizarCaixa();
    } catch (e) {
      erro(mensagem(e));
    } finally {
      setEnviando(false);
    }
  }

  function enviarCampo(evento: FormEvent) {
    evento.preventDefault();
    const valor = texto;
    switch (modo) {
      case "venda":
        setTexto("");
        adicionarPorCodigo(valor);
        break;
      case "busca":
        if (resultados[indiceBusca]) escolherDaBusca(resultados[indiceBusca]);
        break;
      case "quantidade": {
        const qtd = lerQuantidade(valor);
        if (qtd === null || selecionado < 0) return erro("Quantidade inválida");
        setCarrinho(alterarQuantidade(carrinho, selecionado, qtd));
        mudarModo("venda");
        break;
      }
      case "preVenda":
        receberPreVenda(valor);
        break;
      case "falta":
        registrarFalta(valor);
        break;
      case "cliente":
        if (clientes.length > 0 && clientes[indiceBusca]) escolherCliente(clientes[indiceBusca]);
        else buscarCliente(valor);
        break;
      case "pontos": {
        const quantos = valor.trim() === "" ? 0 : Number(valor.trim());
        if (!Number.isInteger(quantos) || quantos < 0) return erro("Informe um número inteiro de pontos");
        const pontos = carrinho.cliente?.pontos;
        if (quantos > 0 && pontos && quantos < pontos.minimo) return erro(`O mínimo para trocar é ${pontos.minimo} pontos`);
        if (quantos > maximoDePontos(carrinho)) return erro(`Dá para usar no máximo ${maximoDePontos(carrinho)} pontos nesta compra`);
        const atualizado = { ...carrinho, pontosResgatados: quantos };
        setCarrinho(atualizado);
        setModo(voltarPara);
        setTexto(voltarPara === "pagamento" ? textoValor(falta(atualizado)) : "");
        setAviso(quantos ? { tipo: "ok", texto: `${quantos} pontos viraram ${reais(descontoPontos(atualizado))} de desconto.` } : null);
        break;
      }
      case "desconto": {
        const centavos = paraCentavos(valor || "0");
        if (centavos === null || centavos > subtotal(carrinho)) return erro("Desconto inválido");
        setCarrinho({ ...carrinho, descontoCentavos: centavos });
        mudarModo("venda");
        break;
      }
      case "pagamento": {
        if (valor.trim() === "" && falta(carrinho) === 0) return void finalizar();
        const centavos = paraCentavos(valor);
        if (!centavos) return erro("Valor inválido");
        const atualizado = { ...carrinho, pagamentos: [...carrinho.pagamentos, { forma, centavos }] };
        setCarrinho(atualizado);
        setAviso(null);
        const restante = falta(atualizado);
        setTexto(restante ? (restante / 100).toFixed(2).replace(".", ",") : "");
        break;
      }
    }
  }

  // Atalhos de teclado do PDV.
  useEffect(() => {
    function tecla(evento: KeyboardEvent) {
      if (!caixa || modo === "fechar" || modo === "receita" || modo === "popular") return;
      const atalhos: Record<string, () => void> = {
        F1: () => modo === "venda" && anotarFalta(),
        F2: () => mudarModo("busca"),
        F3: () => selecionado >= 0 && mudarModo("quantidade"),
        F4: () => {
          if (carrinho.itens.length === 0) return;
          // Controlado: primeiro a receita, depois o pagamento.
          const tipo = receituarioDoCarrinho(carrinho);
          mudarModo(tipo && carrinho.receita?.tipo_receituario !== tipo ? "receita" : "pagamento");
        },
        F5: () => receituarioDoCarrinho(carrinho) && mudarModo("receita"),
        F6: () => carrinho.itens.length > 0 && mudarModo("desconto"),
        F7: () => mudarModo("preVenda"),
        F8: () => (modo === "venda" || modo === "pagamento") && identificarCliente(false),
        F9: () => (modo === "venda" || modo === "pagamento") && usarPontos(),
        F10: () => carrinho.itens.length === 0 ? mudarModo("fechar") : erro("Finalize ou cancele a venda antes de fechar o caixa"),
        Escape: () => {
          if (modo === "cliente" && clienteParaPrazo) {
            setClienteParaPrazo(false);
            setForma("dinheiro");
            return mudarModo("pagamento");
          }
          if (modo === "cliente" || modo === "pontos") return mudarModo(voltarPara);
          if (modo !== "venda") return mudarModo("venda");
          if (carrinho.itens.length === 0) return;
          if (!confirmarCancelar) {
            setConfirmarCancelar(true);
            return setAviso({ tipo: "erro", texto: "Aperte Esc de novo para cancelar a venda" });
          }
          setCarrinho(novoCarrinho());
          setSelecionado(-1);
          setForma("dinheiro");
          setConfirmarCancelar(false);
          setAviso({ tipo: "ok", texto: "Venda cancelada" });
        },
        ArrowUp: () => {
          if (modo === "busca" || modo === "cliente") setIndiceBusca((i) => Math.max(i - 1, 0));
          else if (modo === "venda") setSelecionado((i) => Math.max(i - 1, 0));
        },
        ArrowDown: () => {
          if (modo === "busca") setIndiceBusca((i) => Math.min(i + 1, resultados.length - 1));
          else if (modo === "cliente") setIndiceBusca((i) => Math.min(i + 1, clientes.length - 1));
          else if (modo === "venda") setSelecionado((i) => Math.min(i + 1, carrinho.itens.length - 1));
        },
        Delete: () => {
          if (modo !== "venda" || selecionado < 0) return;
          setCarrinho(removerItem(carrinho, selecionado));
          setSelecionado((i) => Math.min(i, carrinho.itens.length - 2));
        },
      };
      // No pagamento, Alt+1 a Alt+5 escolhem a forma sem atrapalhar a digitação do valor.
      if (modo === "pagamento" && evento.altKey) {
        if (evento.key === "7") {
          evento.preventDefault();
          return abrirPopular();
        }
        const escolhida = FORMAS.find((f) => f.tecla === evento.key);
        if (escolhida) {
          evento.preventDefault();
          return escolherForma(escolhida.forma);
        }
      }
      const acao = atalhos[evento.key];
      if (acao) {
        evento.preventDefault();
        acao();
      }
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  if (terminal === undefined) return <div className="pdv-centro">Carregando...</div>;
  if (terminal === null || !terminal.pode_receber) return <SemCaixaAqui terminal={terminal} />;
  if (caixa === undefined) return <div className="pdv-centro">Carregando...</div>;
  if (caixa === null) return <AbrirCaixa aoAbrir={atualizarCaixa} />;
  if (modo === "fechar") {
    return (
      <FecharCaixa
        caixa={caixa}
        aoVoltar={() => mudarModo("venda")}
        aoFechar={() => {
          setCaixa(null);
          setModo("venda");
        }}
      />
    );
  }

  if (modo === "receita") {
    const tipo = receituarioDoCarrinho(carrinho);
    if (tipo) {
      return (
        <div className="pdv-centro-largo">
          <ReceitaDaVenda
            tipo={tipo}
            inicial={carrinho.receita}
            remedios={carrinho.itens.filter((i) => i.controle).map((i) => i.descricao)}
            aoVoltar={() => mudarModo("venda")}
            aoSalvar={(receita) => {
              setCarrinho({ ...carrinho, receita });
              setModo("pagamento");
              setTexto(falta(carrinho) ? (falta(carrinho) / 100).toFixed(2).replace(".", ",") : "");
              setAviso({ tipo: "ok", texto: "Receita guardada. Agora o pagamento." });
            }}
          />
        </div>
      );
    }
  }

  if (modo === "popular") {
    const comCliente = !!carrinho.cliente;
    const voltar = (atualizado: Carrinho) => {
      setModo("pagamento");
      setTexto(textoValor(falta(atualizado)));
    };
    return (
      <div className="pdv-centro-largo">
        <PopularDaVenda
          inicial={carrinho.popular}
          nome={carrinho.cliente?.nome}
          itens={itensDoPopular(carrinho).map((i) => ({ descricao: i.descricao, governo: governoNoItem(i, comCliente) }))}
          totalVenda={total(carrinho)}
          aoVoltar={() => voltar(carrinho)}
          aoTirar={
            carrinho.popular
              ? () => {
                  const atualizado = { ...carrinho, popular: undefined };
                  setCarrinho(atualizado);
                  voltar(atualizado);
                  setAviso({ tipo: "ok", texto: "Tirei a Farmácia Popular desta venda." });
                }
              : undefined
          }
          aoSalvar={(popular) => {
            const atualizado = { ...carrinho, popular };
            setCarrinho(atualizado);
            voltar(atualizado);
            setForma("dinheiro");
            setAviso({
              tipo: "ok",
              texto: `Farmácia Popular: o governo paga ${reais(parteDoGoverno(atualizado))}. Agora a parte do paciente.`,
            });
          }}
        />
      </div>
    );
  }

  const rotulos: Record<Modo, string> = {
    venda: "Código de barras (ou nome do produto)",
    busca: "Buscar produto por nome",
    quantidade: "Nova quantidade do item selecionado",
    desconto: "Desconto na venda (R$)",
    pagamento: `Valor em ${FORMAS.find((f) => f.forma === forma)?.nome} (Enter vazio finaliza)`,
    cliente: `${clienteParaPrazo ? "Cliente da venda a prazo" : "Cliente"}: CPF, telefone ou nome (Enter busca; Esc volta)`,
    pontos: "Quantos pontos usar como desconto (Enter confirma; 0 tira)",
    preVenda: "Número da pré-venda",
    falta: "O que o cliente pediu e não tinha (Enter anota; Esc volta)",
    receita: "",
    popular: "",
    fechar: "",
  };

  return (
    <div className="pdv">
      <header className="pdv-topo">
        <strong>
          FarmáciaFácil · {terminal.terminal.nome} · {terminal.loja.nome}
        </strong>
        <span>
          {carrinho.preVenda && <>Pré-venda nº {carrinho.preVenda.numero} · </>}
          {sessao?.nome} · Caixa aberto · {caixa.quantidade_vendas} vendas · {reais(caixa.total_vendido)}
        </span>
        <Link to="/">Início</Link>
      </header>

      <section className="pdv-itens">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Produto</th>
              <th className="num">Qtd</th>
              <th className="num">Preço</th>
              <th className="num">Total</th>
            </tr>
          </thead>
          <tbody>
            {carrinho.itens.map((item, i) => (
              <tr
                key={item.produtoId}
                className={[i === selecionado ? "selecionado" : "", item.quantidade > item.saldo ? "sem-saldo" : ""].join(" ")}
                onClick={() => setSelecionado(i)}
              >
                <td>{i + 1}</td>
                <td>
                  {item.descricao}
                  {item.controle && <span className="selo selo-controle">Controlado</span>}
                  {item.popularCentavos ? <span className="selo selo-popular">Farmácia Popular</span> : null}
                  <PromocaoDoItem item={item} comCliente={!!carrinho.cliente} />
                </td>
                <td className="num">{fmtQtd(item.quantidade)}</td>
                <td className="num">{reais(item.precoCentavos)}</td>
                <td className="num">{reais(totalItem(item))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {carrinho.itens.length === 0 && <p className="vazio">Bipe um produto para começar</p>}
      </section>

      <aside className="pdv-lateral">
        <div className="totais">
          <div>Subtotal <span>{reais(subtotal(carrinho))}</span></div>
          {descontoPromocoes(carrinho) > 0 && (
            <div className="linha-promocao">
              Promoções <span>-{reais(descontoPromocoes(carrinho))}</span>
            </div>
          )}
          {descontoConvenio(carrinho) > 0 && (
            <div className="linha-promocao">
              Convênio {carrinho.cliente?.convenio?.nome} <span>-{reais(descontoConvenio(carrinho))}</span>
            </div>
          )}
          {carrinho.descontoCentavos > 0 && <div>Desconto <span>-{reais(carrinho.descontoCentavos)}</span></div>}
          {descontoPontos(carrinho) > 0 && (
            <div>
              Pontos ({carrinho.pontosResgatados}) <span>-{reais(descontoPontos(carrinho))}</span>
            </div>
          )}
          {(carrinho.taxaEntregaCentavos ?? 0) > 0 && (
            <div>Entrega <span>{reais(carrinho.taxaEntregaCentavos ?? 0)}</span></div>
          )}
          <div className="total">Total <span>{reais(total(carrinho))}</span></div>
          {parteDoGoverno(carrinho) > 0 && (
            <div className="pagamento">
              Farmácia Popular (governo) <span>{reais(parteDoGoverno(carrinho))}</span>
            </div>
          )}
          {carrinho.pagamentos.map((p, i) => (
            <div key={i} className="pagamento">
              {FORMAS.find((f) => f.forma === p.forma)?.nome} <span>{reais(p.centavos)}</span>
            </div>
          ))}
          {(carrinho.pagamentos.length > 0 || parteDoGoverno(carrinho) > 0) && (
            falta(carrinho) > 0
              ? <div className="falta">Falta <span>{reais(falta(carrinho))}</span></div>
              : <div className="troco">Troco <span>{reais(troco(carrinho))}</span></div>
          )}
        </div>

        {modo === "pagamento" && (
          <div className="formas">
            {FORMAS.map((f) => (
              <button key={f.forma} className={f.forma === forma ? "ativa" : ""} onClick={() => escolherForma(f.forma)}>
                Alt+{f.tecla} {f.nome}
              </button>
            ))}
            {(itensDoPopular(carrinho).length > 0 || carrinho.popular) && (
              <button className={carrinho.popular ? "ativa" : ""} onClick={abrirPopular}>
                Alt+7 Farmácia Popular
              </button>
            )}
          </div>
        )}

        {receituarioDoCarrinho(carrinho) && (
          <div className={`pdv-cliente ${carrinho.receita ? "" : "pdv-receita-falta"}`}>
            <small>Receita</small>
            {carrinho.receita ? (
              <>
                <strong>{carrinho.receita.prescritor_nome}</strong>
                <small>
                  {carrinho.receita.prescritor_conselho} {carrinho.receita.prescritor_numero}/{carrinho.receita.prescritor_uf}
                  {carrinho.receita.numero_notificacao && ` · nº ${carrinho.receita.numero_notificacao}`}
                </small>
              </>
            ) : (
              <strong>Falta preencher (F5)</strong>
            )}
          </div>
        )}

        {carrinho.popular && (
          <div className="pdv-cliente">
            <small>Farmácia Popular</small>
            <strong>{carrinho.popular.paciente_nome}</strong>
            <small>
              Autorização {carrinho.popular.autorizacao} · CRM {carrinho.popular.prescritor_crm}/{carrinho.popular.prescritor_uf}
            </small>{" "}
            <button type="button" className="botao-pequeno" onClick={abrirPopular}>
              Alterar
            </button>
          </div>
        )}

        {carrinho.cliente && (
          <div className="pdv-cliente">
            <small>Cliente</small>
            <strong>{carrinho.cliente.nome}</strong>
            {carrinho.cliente.pontos && (
              <small className="pontos">
                {carrinho.cliente.pontos.saldo.toLocaleString("pt-BR")} pontos
                {carrinho.pontosResgatados
                  ? ` · usando ${carrinho.pontosResgatados}`
                  : carrinho.cliente.pontos.saldo >= carrinho.cliente.pontos.minimo && " · F9 usar"}
              </small>
            )}
            {carrinho.cliente.convenio && (
              <small className="pontos">
                Convênio {carrinho.cliente.convenio.nome} · pode usar {reais(carrinho.cliente.convenio.disponivelCentavos)}
              </small>
            )}
            {carrinho.cliente.disponivelCentavos > 0 && (
              <small>Pode comprar até {reais(carrinho.cliente.disponivelCentavos)} a prazo</small>
            )}{" "}
            <button
              type="button"
              className="botao-pequeno"
              onClick={() =>
                setCarrinho({
                  ...carrinho,
                  cliente: undefined,
                  pontosResgatados: 0,
                  pagamentos: carrinho.pagamentos.filter((p) => p.forma !== "prazo"),
                })
              }
            >
              Tirar
            </button>
          </div>
        )}

        {modo === "cliente" && clientes.length > 0 && (
          <ul className="resultados">
            {clientes.map((c, i) => (
              <li key={c.id} className={i === indiceBusca ? "selecionado" : ""} onClick={() => escolherCliente(c)}>
                {c.nome} <span>{c.telefone ?? ""}</span>
              </li>
            ))}
          </ul>
        )}

        {modo === "busca" && (
          <ul className="resultados">
            {resultados.map((p, i) => (
              <li key={p.id} className={i === indiceBusca ? "selecionado" : ""} onClick={() => escolherDaBusca(p)}>
                {p.nome} {p.apresentacao} <span>{reais(p.preco_venda)}</span>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <form className="pdv-campo" onSubmit={enviarCampo}>
        <label htmlFor="campo">{rotulos[modo]}</label>
        <input
          id="campo"
          ref={campo}
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            if (modo === "busca" && e.target.value.length >= 3) buscar(e.target.value);
          }}
          autoComplete="off"
          disabled={enviando}
        />
        {aviso && (
          <p className={aviso.tipo}>
            {aviso.texto}
            {aviso.link && (
              <>
                {" "}
                <a href={aviso.link} target="_blank" rel="noreferrer">
                  Imprimir cupom
                </a>
              </>
            )}
            {aviso.comprovante && (
              <>
                {" "}
                <a href={aviso.comprovante} target="_blank" rel="noreferrer">
                  Imprimir comprovante da Farmácia Popular
                </a>
              </>
            )}
          </p>
        )}
      </form>

      <footer className="pdv-atalhos">
        <span>F1 Anotar falta</span>
        <span>F2 Buscar</span>
        <span>F3 Quantidade</span>
        <span>F4 Pagamento (Alt+5 a prazo, Alt+6 convênio, Alt+7 Farmácia Popular)</span>
        <span>F5 Receita</span>
        <span>F6 Desconto</span>
        <span>F7 Receber pré-venda</span>
        <span>F8 Cliente</span>
        <span>F9 Usar pontos</span>
        <span>Del Remover item</span>
        <span>Esc Voltar/Cancelar</span>
        <span>F10 Fechar caixa</span>
      </footer>
    </div>
  );
}

/** Mostra a promoção que vale no item ou, se for do clube, avisa que precisa identificar o cliente. */
function PromocaoDoItem({ item, comCliente }: { item: ItemCarrinho; comCliente: boolean }) {
  const valendo = promocaoDoItem(item, comCliente);
  if (valendo) {
    return (
      <small className="pdv-promocao">
        {valendo.promocao.nome}: {valendo.promocao.resumo} (−{reais(valendo.centavos)})
      </small>
    );
  }
  const doClube = !comCliente && promocaoDoItem(item, true);
  if (doClube) {
    return (
      <small className="pdv-promocao clube">
        {doClube.promocao.resumo} para cliente identificado: F8 (−{reais(doClube.centavos)})
      </small>
    );
  }
  const leve = (item.promocoes ?? []).find((p) => p.tipo === "leve_pague" && (!p.so_clientes || comCliente));
  return leve ? <small className="pdv-promocao clube">{leve.resumo}: leve mais para ganhar</small> : null;
}

function AbrirCaixa({ aoAbrir }: { aoAbrir: () => void }) {
  const [valor, setValor] = useState("0,00");
  const [erro, setErro] = useState("");

  async function abrir(evento: FormEvent) {
    evento.preventDefault();
    const centavos = paraCentavos(valor);
    if (centavos === null) return setErro("Valor inválido");
    try {
      await api("/caixas/abrir", { corpo: { valor_abertura: (centavos / 100).toFixed(2) } });
      aoAbrir();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <form className="pdv-centro cartao" onSubmit={abrir}>
      <h2>Abrir caixa</h2>
      <label>
        Dinheiro na gaveta (R$)
        <input value={valor} onChange={(e) => setValor(e.target.value)} autoFocus onFocus={(e) => e.target.select()} />
      </label>
      {erro && <p className="erro">{erro}</p>}
      <button type="submit">Abrir (Enter)</button>
      <Link to="/">Ir para o início</Link>
    </form>
  );
}

function SemCaixaAqui({ terminal }: { terminal: EsteTerminal | null }) {
  return (
    <div className="pdv-centro cartao">
      <h2>{terminal ? `${terminal.terminal.nome} não recebe pagamentos` : "Este computador não é um caixa"}</h2>
      <p>
        {terminal
          ? terminal.motivo
          : "Só computadores registrados como PDV podem abrir caixa. Um gerente registra o computador em Caixas."}
      </p>
      <Link to="/vendas/pre-venda" className="botao">
        Fazer pré-venda
      </Link>
      <Link to="/caixas">Ir para Caixas</Link>
      <Link to="/">Ir para o início</Link>
    </div>
  );
}

function avisoDaVenda(venda: Venda, textoTroco: string): { tipo: "erro" | "ok"; texto: string; link?: string } {
  const texto = `Venda nº ${venda.numero} finalizada.${textoTroco}`;
  const nota = venda.nota;
  if (!nota) return { tipo: "ok", texto };
  if (nota.status === "autorizada") {
    return { tipo: "ok", texto: `${texto} NFC-e nº ${nota.numero} autorizada.`, link: nota.url_danfe ?? undefined };
  }
  if (nota.status === "processando") {
    return { tipo: "erro", texto: `${texto} NFC-e em processamento: confira na lista de vendas.` };
  }
  return { tipo: "erro", texto: `${texto} NFC-e não emitida: ${nota.mensagem ?? "erro desconhecido"}` };
}

import { describe, expect, it } from "vitest";

import type { ProdutoPDV, PromocaoPDV } from "../../api/tipos";
import {
  adicionarProduto,
  descontoPromocoes,
  falta,
  interpretarEntrada,
  maximoDePontos,
  montarVenda,
  novoCarrinho,
  paraCentavos,
  parteDoGoverno,
  descontoConvenio,
  problemaParaFinalizar,
  receituarioDoCarrinho,
  removerItem,
  subtotal,
  total,
  troco,
} from "./carrinho";

function produto(campos: Partial<ProdutoPDV> = {}): ProdutoPDV {
  return {
    id: "p1",
    ean: "7891234567890",
    nome: "Dipirona 500mg",
    apresentacao: "10 comp",
    fabricante: null,
    ncm: null,
    cest: null,
    cfop: null,
    icms_origem: "0",
    vende_online: false,
    icms_situacao_tributaria: null,
    pis_cofins_situacao_tributaria: null,
    unidade: "UN",
    preco_venda: "8.90",
    preco_custo: null,
    estoque_minimo: "0",
    controla_lote: true,
    tipo: "medicamento",
    registro_ms: null,
    controle: null,
    embalagem_sngpc: "caixa",
    popular_valor: null,
    comissao: null,
    ativo: true,
    codigos: [],
    saldo: "10",
    ...campos,
  };
}

describe("interpretarEntrada", () => {
  it("lê código bipado como 1 unidade", () => {
    expect(interpretarEntrada("7891234567890")).toEqual({ quantidade: 1, codigo: "7891234567890" });
  });
  it("lê quantidade antes do asterisco", () => {
    expect(interpretarEntrada("3*7891234567890")).toEqual({ quantidade: 3, codigo: "7891234567890" });
    expect(interpretarEntrada("1,5*78912345")).toEqual({ quantidade: 1.5, codigo: "78912345" });
  });
  it("recusa texto que não é código", () => {
    expect(interpretarEntrada("dipirona")).toBeNull();
    expect(interpretarEntrada("0*7891234567890")).toBeNull();
    expect(interpretarEntrada("123")).toBeNull();
  });
});

describe("paraCentavos", () => {
  it("aceita formato da API e digitado", () => {
    expect(paraCentavos("8.90")).toBe(890);
    expect(paraCentavos("10,5")).toBe(1050);
    expect(paraCentavos("1.234,56")).toBe(123456);
    expect(paraCentavos("20")).toBe(2000);
  });
  it("recusa valores inválidos", () => {
    expect(paraCentavos("abc")).toBeNull();
    expect(paraCentavos("-1")).toBeNull();
    expect(paraCentavos("1,234")).toBeNull();
  });
});

describe("carrinho", () => {
  it("bipar o mesmo produto soma a quantidade", () => {
    let c = adicionarProduto(novoCarrinho(), produto(), 1);
    c = adicionarProduto(c, produto(), 2);
    expect(c.itens).toHaveLength(1);
    expect(c.itens[0].quantidade).toBe(3);
    expect(c.itens[0].descricao).toBe("Dipirona 500mg 10 comp");
    expect(subtotal(c)).toBe(2670);
  });

  it("calcula desconto, falta e troco", () => {
    let c = adicionarProduto(novoCarrinho(), produto(), 3);
    c = { ...c, descontoCentavos: 70 };
    expect(total(c)).toBe(2600);
    c = { ...c, pagamentos: [{ forma: "pix", centavos: 1000 }] };
    expect(falta(c)).toBe(1600);
    expect(problemaParaFinalizar(c)).toBe("Pagamento não cobre o total");
    c = { ...c, pagamentos: [...c.pagamentos, { forma: "dinheiro", centavos: 2000 }] };
    expect(troco(c)).toBe(400);
    expect(problemaParaFinalizar(c)).toBeNull();
  });

  it("soma a taxa de entrega da pré-venda no total", () => {
    let c = adicionarProduto({ ...novoCarrinho(), taxaEntregaCentavos: 950 }, produto(), 2);
    c = { ...c, descontoCentavos: 80 };
    expect(total(c)).toBe(1780 - 80 + 950);
    c = { ...c, pagamentos: [{ forma: "dinheiro", centavos: 2700 }] };
    expect(troco(c)).toBe(50);
  });

  it("não deixa troco sair do cartão", () => {
    let c = adicionarProduto(novoCarrinho(), produto(), 1);
    c = { ...c, pagamentos: [{ forma: "debito", centavos: 1000 }] };
    expect(problemaParaFinalizar(c)).toMatch(/Troco/);
  });

  it("monta o corpo da venda para a API", () => {
    let c = adicionarProduto(novoCarrinho(), produto(), 2);
    c = adicionarProduto(c, produto({ id: "p2", nome: "Sabonete", apresentacao: null, preco_venda: "3.00" }), 1);
    c = removerItem(c, 1);
    c = { ...c, pagamentos: [{ forma: "dinheiro", centavos: 2000 }] };
    expect(montarVenda(c, "52998224725")).toEqual({
      chave_idempotencia: c.chave,
      itens: [{ produto_id: "p1", quantidade: "2" }],
      pagamentos: [{ forma: "dinheiro", valor: "20.00" }],
      desconto: "0.00",
      cliente_cpf: "52998224725",
      cliente_id: null,
      pontos_resgatados: 0,
      pre_venda_id: null,
      receita: null,
      popular: null,
    });
    expect(montarVenda({ ...c, preVenda: { id: "pv1", numero: 7 } }).pre_venda_id).toBe("pv1");
  });
});

describe("venda a prazo", () => {
  it("exige o cliente e respeita o disponível", () => {
    let carrinho = adicionarProduto(novoCarrinho(), produto({ preco_venda: "30.00" }), 1);
    carrinho = { ...carrinho, pagamentos: [{ forma: "prazo", centavos: 3000 }] };
    expect(problemaParaFinalizar(carrinho)).toMatch(/Escolha o cliente/);

    carrinho = { ...carrinho, cliente: { id: "c1", nome: "João", disponivelCentavos: 2000 } };
    expect(problemaParaFinalizar(carrinho)).toMatch(/João só pode comprar mais 20,00/);

    carrinho = { ...carrinho, cliente: { id: "c1", nome: "João", disponivelCentavos: 5000 } };
    expect(problemaParaFinalizar(carrinho)).toBeNull();
    expect(montarVenda(carrinho).cliente_id).toBe("c1");
  });
});

describe("pontos", () => {
  const maria = { id: "c1", nome: "Maria", disponivelCentavos: 0, pontos: { saldo: 500, valorPonto: "0.05", minimo: 100 } };

  it("viram desconto e entram na venda", () => {
    let carrinho = adicionarProduto(novoCarrinho(), produto({ preco_venda: "30.00" }), 1);
    carrinho = { ...carrinho, cliente: maria, pontosResgatados: 200 };
    expect(total(carrinho)).toBe(2000);
    expect(montarVenda(carrinho).pontos_resgatados).toBe(200);
  });

  it("não passam do valor da compra nem do mínimo", () => {
    let carrinho = adicionarProduto(novoCarrinho(), produto({ preco_venda: "12.34" }), 1);
    carrinho = { ...carrinho, cliente: maria };
    expect(maximoDePontos(carrinho)).toBe(246);
    carrinho = { ...carrinho, pontosResgatados: 50, pagamentos: [{ forma: "dinheiro", centavos: 1234 }] };
    expect(problemaParaFinalizar(carrinho)).toMatch(/mínimo/);
    carrinho = { ...carrinho, pontosResgatados: 300 };
    expect(problemaParaFinalizar(carrinho)).toMatch(/valem mais/);
  });

  it("exigem o cliente", () => {
    let carrinho = adicionarProduto(novoCarrinho(), produto(), 1);
    carrinho = { ...carrinho, pontosResgatados: 100, pagamentos: [{ forma: "dinheiro", centavos: 890 }] };
    expect(problemaParaFinalizar(carrinho)).toMatch(/Escolha o cliente/);
  });
});

describe("promoções", () => {
  const promo = (campos: Partial<PromocaoPDV>): PromocaoPDV => ({
    id: "pr1", nome: "Promo", tipo: "percentual", percentual: null, preco: null, leve: null, pague: null,
    so_clientes: false, resumo: "", ...campos,
  });

  it("calcula como o servidor e vale a melhor", () => {
    const fralda = produto({ preco_venda: "10.00", promocoes: [promo({ tipo: "leve_pague", leve: 3, pague: 2 })] });
    const sabonete = produto({
      id: "p2",
      preco_venda: "4.00",
      promocoes: [promo({ tipo: "preco_fixo", preco: "2.99" }), promo({ id: "pr3", percentual: "10" })],
    });
    let carrinho = adicionarProduto(novoCarrinho(), fralda, 7);
    carrinho = adicionarProduto(carrinho, sabonete, 2);
    expect(descontoPromocoes(carrinho)).toBe(2000 + 202);
    expect(total(carrinho)).toBe(7800 - 2202);
  });

  it("promoção do clube só com cliente identificado", () => {
    const vitamina = produto({ preco_venda: "30.00", promocoes: [promo({ percentual: "25", so_clientes: true })] });
    let carrinho = adicionarProduto(novoCarrinho(), vitamina, 1);
    expect(total(carrinho)).toBe(3000);
    carrinho = { ...carrinho, cliente: { id: "c1", nome: "Maria", disponivelCentavos: 0 } };
    expect(total(carrinho)).toBe(2250);
  });

  it("venda com controlado pede a receita certa", () => {
    let c = adicionarProduto(novoCarrinho(), produto(), 1);
    expect(receituarioDoCarrinho(c)).toBeNull();
    c = adicionarProduto(c, produto({ id: "p2", nome: "Clonazepam", controle: "B1" }), 1);
    c = { ...c, pagamentos: [{ forma: "dinheiro", centavos: 5000 }] };
    expect(receituarioDoCarrinho(c)).toBe(2);
    expect(problemaParaFinalizar(c)).toMatch(/receita \(F5\)/);
    const receita = {
      tipo_receituario: 2, numero_notificacao: "123", data_prescricao: "2026-10-30", prescritor_nome: "Dra. Paula",
      prescritor_conselho: "CRM" as const, prescritor_numero: "1", prescritor_uf: "SP", uso_prolongado: false,
      comprador_nome: "José", comprador_tipo_documento: 2, comprador_documento: "1", comprador_orgao: "SSP",
      comprador_uf: "SP", paciente_nome: null, paciente_idade: null, paciente_unidade_idade: 1 as const,
      paciente_sexo: null, cid: null,
    };
    c = { ...c, receita };
    expect(problemaParaFinalizar(c)).toBeNull();
    expect(montarVenda(c).receita).toEqual(receita);
    // Tirou o controlado: a receita não vai.
    expect(montarVenda(removerItem(c, 1)).receita).toBeNull();
  });

  it("conveniado ganha o desconto e não passa do limite do convênio", () => {
    let c = adicionarProduto(novoCarrinho(), produto({ preco_venda: "40.00" }), 1);
    c = adicionarProduto(c, produto({ id: "p2", preco_venda: "20.00", promocoes: [promo({ percentual: "50" })] }), 1);
    c = { ...c, cliente: { id: "c1", nome: "Pedro", disponivelCentavos: 0, convenio: { nome: "Metalúrgica", desconto: "10.00", disponivelCentavos: 4000 } } };
    // (40 + 20 - 10 da promoção) x 10% = 5
    expect(descontoConvenio(c)).toBe(500);
    expect(total(c)).toBe(4500);
    c = { ...c, pagamentos: [{ forma: "convenio", centavos: 4500 }] };
    expect(problemaParaFinalizar(c)).toMatch(/só pode comprar mais 40,00 no convênio/);
    c = { ...c, pagamentos: [{ forma: "convenio", centavos: 4000 }, { forma: "pix", centavos: 500 }] };
    expect(problemaParaFinalizar(c)).toBeNull();
    const semConvenio = { ...c, cliente: { id: "c2", nome: "Ana", disponivelCentavos: 0 } };
    expect(descontoConvenio(semConvenio)).toBe(0);
    expect(problemaParaFinalizar(semConvenio)).toMatch(/Pagamento não cobre|empresa conveniada/);
  });

  it("Farmácia Popular: o governo paga até o valor do programa e o paciente paga o resto", () => {
    let c = adicionarProduto(novoCarrinho(), produto({ preco_venda: "25.00", popular_valor: "18.40" }), 1);
    c = adicionarProduto(c, produto({ id: "p2", preco_venda: "9.00", popular_valor: "12.00" }), 1);
    c = adicionarProduto(c, produto({ id: "p3", preco_venda: "20.00" }), 1);
    // Sem os dados do programa, o governo não paga nada.
    expect(parteDoGoverno(c)).toBe(0);
    c = {
      ...c,
      popular: {
        paciente_cpf: "52998224725", paciente_nome: "Maria", prescritor_crm: "123", prescritor_uf: "SP",
        receita_data: "2026-10-01", autorizacao: "12345",
      },
    };
    expect(parteDoGoverno(c)).toBe(1840 + 900);
    expect(falta(c)).toBe(5400 - 2740);
    c = { ...c, pagamentos: [{ forma: "dinheiro", centavos: 3000 }] };
    expect(problemaParaFinalizar(c)).toBeNull();
    expect(troco(c)).toBe(340);
    expect(montarVenda(c).pagamentos[0]).toEqual({ forma: "popular", valor: "27.40" });
    // Só item fora do programa: não dá para vender pela Farmácia Popular.
    const fora = { ...c, itens: c.itens.slice(2), pagamentos: [] };
    expect(problemaParaFinalizar(fora)).toMatch(/Nenhum remédio/);
  });
});

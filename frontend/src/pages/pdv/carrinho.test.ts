import { describe, expect, it } from "vitest";

import type { ProdutoPDV } from "../../api/tipos";
import {
  adicionarProduto,
  falta,
  interpretarEntrada,
  maximoDePontos,
  montarVenda,
  novoCarrinho,
  paraCentavos,
  problemaParaFinalizar,
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
    icms_situacao_tributaria: null,
    pis_cofins_situacao_tributaria: null,
    unidade: "UN",
    preco_venda: "8.90",
    preco_custo: null,
    estoque_minimo: "0",
    controla_lote: true,
    tipo: "medicamento",
    registro_ms: null,
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

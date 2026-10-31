import { describe, expect, it } from "vitest";

import type { Devolucao, ItemDevolvivel } from "../../api/tipos";
import { devolvidoPorItem, lerQuantidade, textoPontos, valorDoItem } from "./calculo";

const item = (extra: Partial<ItemDevolvivel> = {}): ItemDevolvivel => ({
  venda_item_id: "i1",
  produto_id: "p1",
  descricao: "Shampoo",
  tipo_produto: "perfumaria",
  quantidade: "3.000",
  devolvida: "0.000",
  disponivel: "3.000",
  valor_pago: "10.00",
  valor_unitario: "3.33",
  bloqueio: null,
  volta_estoque_sugerido: true,
  ...extra,
});

describe("devolução", () => {
  it("divide o valor pago pela quantidade", () => {
    expect(valorDoItem(item(), 1, 0)).toBe(333);
    expect(valorDoItem(item(), 2, 0)).toBe(667);
    expect(valorDoItem(item(), 0, 0)).toBe(0);
  });

  it("a última unidade leva os centavos que sobraram", () => {
    const resto = item({ devolvida: "1.000", disponivel: "2.000" });
    expect(valorDoItem(resto, 2, 333)).toBe(667);
    expect(valorDoItem(item(), 3, 0)).toBe(1000);
  });

  it("soma o já devolvido por item", () => {
    const anteriores = [
      { itens: [{ venda_item_id: "i1", valor: "3.33" }] },
      { itens: [{ venda_item_id: "i1", valor: "3.34" }, { venda_item_id: "i2", valor: "5.00" }] },
    ] as unknown as Devolucao[];
    expect(devolvidoPorItem(anteriores)).toEqual({ i1: 667, i2: 500 });
  });

  it("lê a quantidade digitada", () => {
    expect(lerQuantidade("2")).toBe(2);
    expect(lerQuantidade("1,5")).toBe(1.5);
    expect(lerQuantidade("")).toBe(0);
    expect(lerQuantidade("-1")).toBe(0);
  });

  it("explica os pontos", () => {
    expect(textoPontos(0)).toBe("");
    expect(textoPontos(-23)).toContain("perdeu 23 pontos");
    expect(textoPontos(1)).toContain("recebeu de volta 1 ponto de");
  });
});

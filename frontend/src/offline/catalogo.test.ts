import { describe, expect, it } from "vitest";

import { ErroApi } from "../api/cliente";
import type { ProdutoPDV } from "../api/tipos";
import { baixarSaldos, ehFalhaDeRede, porCodigo, porNome } from "./catalogo";

const produto = (extra: Partial<ProdutoPDV>): ProdutoPDV =>
  ({ id: "p", ean: null, nome: "", apresentacao: null, fabricante: null, saldo: "0", codigos: [], ...extra }) as ProdutoPDV;

const produtos = [
  produto({ id: "1", ean: "7891234567895", nome: "Dipirona", apresentacao: "500mg 10 comp.", saldo: "5" }),
  produto({ id: "2", ean: "7890000000062", nome: "Shampoo anticaspa", codigos: [{ id: "c", ean: "7899999999999" }], saldo: "2" }),
  produto({ id: "3", nome: "Pomada Cicatrizante", fabricante: "Médley" }),
];

describe("catálogo guardado", () => {
  it("acha pelo código de barras principal ou pelos outros códigos", () => {
    expect(porCodigo(produtos, "7891234567895")?.id).toBe("1");
    expect(porCodigo(produtos, " 7899999999999 ")?.id).toBe("2");
    expect(porCodigo(produtos, "000")).toBeNull();
  });

  it("acha pelo nome, sem ligar para acento e maiúscula", () => {
    expect(porNome(produtos, "dipi 500").map((p) => p.id)).toEqual(["1"]);
    expect(porNome(produtos, "medley").map((p) => p.id)).toEqual(["3"]);
    expect(porNome(produtos, "  ")).toEqual([]);
  });

  it("baixa o saldo depois da venda offline, sem ficar negativo", () => {
    const depois = baixarSaldos(produtos, [{ produtoId: "1", quantidade: 2 }, { produtoId: "2", quantidade: 3 }]);
    expect(depois.map((p) => p.saldo)).toEqual(["3", "0", "0"]);
  });

  it("separa falta de internet de recusa do servidor", () => {
    expect(ehFalhaDeRede(new TypeError("Failed to fetch"))).toBe(true);
    expect(ehFalhaDeRede(new ErroApi(503, "fora"))).toBe(true);
    expect(ehFalhaDeRede(new ErroApi(400, "Faltam R$ 1,00"))).toBe(false);
  });
});

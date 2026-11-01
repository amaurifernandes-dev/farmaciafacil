import { describe, expect, it } from "vitest";

import type { BoletoLido } from "../../api/tipos";
import { categoriaDoBoleto, codigoCompleto, descricaoDoBoleto } from "./boleto";

const lido = (extra: Partial<BoletoLido>) => ({ tipo: "bancario", banco: "341", banco_nome: "Itaú", segmento: null, ...extra }) as BoletoLido;

describe("boleto", () => {
  it("sabe quando o código está completo", () => {
    expect(codigoCompleto("00190.50095 40144.816069 06809.350314 3 37370000000100")).toBe(true);
    expect(codigoCompleto("00190.50095 40144")).toBe(false);
    expect(codigoCompleto("8".repeat(48))).toBe(true);
  });

  it("sugere categoria e descrição", () => {
    expect(categoriaDoBoleto(lido({}))).toBe("fornecedores");
    expect(descricaoDoBoleto(lido({}))).toBe("Boleto Itaú");
    const luz = lido({ tipo: "arrecadacao", segmento: "Energia elétrica e gás", banco: null, banco_nome: null });
    expect(categoriaDoBoleto(luz)).toBe("contas_consumo");
    expect(descricaoDoBoleto(luz)).toBe("Conta de energia elétrica e gás");
    expect(categoriaDoBoleto(lido({ tipo: "arrecadacao", segmento: "Prefeitura" }))).toBe("impostos");
  });
});

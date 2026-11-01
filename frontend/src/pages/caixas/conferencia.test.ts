import { describe, expect, it } from "vitest";

import type { ResumoCaixa } from "../../api/tipos";
import { conferir, contagemVazia, formasParaConferir } from "./conferencia";

const resumo = {
  dinheiro_esperado: "80.00",
  por_forma: { dinheiro: "30.00", debito: "40.00", credito: "0", pix: "15.50", prazo: "20.00" },
} as unknown as ResumoCaixa;

describe("conferência do fechamento", () => {
  it("só pede cartão e Pix que tiveram venda", () => {
    expect(formasParaConferir(resumo)).toEqual(["debito", "pix"]);
  });

  it("exige o dinheiro contado", () => {
    expect(conferir(resumo, contagemVazia()).erro).toMatch(/dinheiro/);
  });

  it("fecha sem observação quando tudo bate", () => {
    const r = conferir(resumo, { dinheiro: "80", formas: { debito: "40,00", pix: "" }, observacao: "" });
    expect(r.erro).toBe("");
    expect(r.corpo).toEqual({
      valor_fechamento_informado: "80.00",
      conferencia: { debito: "40.00" },
      observacao: null,
    });
    expect(r.linhas.find((l) => l.forma === "pix")?.diferenca).toBeNull();
  });

  it("com diferença, pede o motivo", () => {
    const contagem = { dinheiro: "75,00", formas: { pix: "15,50" }, observacao: "" };
    const sem = conferir(resumo, contagem);
    expect(sem.diferencaTotal).toBe(-500);
    expect(sem.erro).toMatch(/motivo/);
    const com = conferir(resumo, { ...contagem, observacao: "Troco errado" });
    expect(com.corpo?.observacao).toBe("Troco errado");
  });

  it("avisa valor escrito errado", () => {
    expect(conferir(resumo, { dinheiro: "80", formas: { debito: "abc" }, observacao: "" }).erro).toMatch(/errado/);
  });
});

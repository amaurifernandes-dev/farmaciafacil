import { describe, expect, it } from "vitest";

import { idade, montarResultados } from "./campos";

describe("serviços farmacêuticos", () => {
  it("monta os resultados para a API", () => {
    expect(montarResultados("pressao", { sistolica: "130", diastolica: " 85 ", frequencia: "", braco: "" })).toEqual({
      sistolica: 130,
      diastolica: 85,
    });
    expect(montarResultados("temperatura", { graus: "37,8" })).toEqual({ graus: 37.8 });
    expect(montarResultados("glicemia", { valor: "98" })).toEqual({ valor: 98, jejum: false });
  });

  it("calcula a idade pela data de nascimento", () => {
    expect(idade("1950-03-10", new Date(2026, 9, 31))).toBe(76);
    expect(idade("1950-12-10", new Date(2026, 9, 31))).toBe(75);
    expect(idade(null)).toBeNull();
  });
});

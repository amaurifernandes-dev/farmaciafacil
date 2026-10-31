import { describe, expect, it } from "vitest";

import { lerValor, sugerir } from "./Metas";

describe("metas", () => {
  it("lê o valor digitado", () => {
    expect(lerValor("15.000")).toBe("15000.00");
    expect(lerValor("R$ 12.500,50")).toBe("12500.50");
    expect(lerValor("8000")).toBe("8000.00");
    expect(lerValor("  ")).toBeNull();
    expect(lerValor("abc")).toBe("invalido");
    expect(lerValor("0")).toBe("invalido");
  });

  it("sugere pelo mês passado, arredondando para a centena", () => {
    expect(sugerir("12345.67", 10)).toBe("13600");
    expect(sugerir("1000", 0)).toBe("1000");
    expect(sugerir("0", 10)).toBeNull();
  });
});

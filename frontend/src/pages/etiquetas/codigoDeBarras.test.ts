import { describe, expect, it } from "vitest";

import { barrasEan, eanValido } from "./codigoDeBarras";

describe("código de barras", () => {
  it("confere o dígito verificador", () => {
    expect(eanValido("7891234567895")).toBe(true);
    expect(eanValido("7891234567890")).toBe(false);
    expect(eanValido("96385074")).toBe(true);
    expect(eanValido("123")).toBe(false);
  });

  it("monta as 95 barras do EAN-13 e as 67 do EAN-8", () => {
    const barras = barrasEan("4006381333931") as string;
    expect(barras).toHaveLength(95);
    // Início, meio e fim fixos.
    expect(barras.slice(0, 3)).toBe("101");
    expect(barras.slice(45, 50)).toBe("01010");
    expect(barras.slice(-3)).toBe("101");
    // 4 = LGLLGG: o primeiro dígito depois dele (0) usa L.
    expect(barras.slice(3, 10)).toBe("0001101");
    expect(barrasEan("96385074")).toHaveLength(67);
    expect(barrasEan("7891234567890")).toBeNull();
  });
});

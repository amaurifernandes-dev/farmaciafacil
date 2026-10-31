import { describe, expect, it } from "vitest";

import { filtroRepetidas } from "./leitorCamera";

describe("leitura pela câmera", () => {
  it("não conta a mesma caixa duas vezes seguidas", () => {
    let t = 0;
    const deixa = filtroRepetidas(1500, () => t);
    expect(deixa("789")).toBe(true);
    t = 500;
    expect(deixa("789")).toBe(false); // a câmera continua vendo a mesma caixa
    t = 1500;
    expect(deixa("789")).toBe(false); // ainda parado em cima dela
    t = 3500;
    expect(deixa("789")).toBe(true); // tirou e mostrou de novo
    expect(deixa("456")).toBe(true); // outro produto passa na hora
  });
});

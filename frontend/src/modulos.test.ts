import { describe, expect, it } from "vitest";

import type { Sessao } from "./api/tipos";
import { estaLigado, MODULOS } from "./modulos";
import { moduloDoEndereco, TELAS, telasDe } from "./telas";

const admin = { papel: "admin", nome: "Ana", usuario_id: "u", farmacia_id: "f", access_token: "t" } as Sessao;

describe("Gerenciamento de telas", () => {
  it("desligar uma função tira as telas dela até do administrador", () => {
    const desligados = ["faltas", "devolucoes"];
    const telas = telasDe(admin, (m) => estaLigado(desligados, m)).map((t) => t.para);
    expect(telas).not.toContain("/faltas");
    expect(telas).not.toContain("/devolucoes");
    expect(telas).toContain("/vendas");
    expect(telas).toContain("/configuracoes/telas");
  });

  it("a loja online depende dos pedidos", () => {
    expect(estaLigado([], "loja_online")).toBe(true);
    expect(estaLigado(["pedidos"], "loja_online")).toBe(false);
    expect(estaLigado(["pedidos"], "faltas")).toBe(true);
  });

  it("acha a função de um endereço, inclusive de páginas internas", () => {
    expect(moduloDoEndereco("/faltas")).toBe("faltas");
    expect(moduloDoEndereco("/convenios/123")).toBe("convenios");
    expect(moduloDoEndereco("/")).toBeUndefined();
    expect(moduloDoEndereco("/vendas")).toBeUndefined();
  });

  it("toda função tem uma tela ou um lugar onde aparece", () => {
    const comTela = new Set(TELAS.map((t) => t.modulo).filter(Boolean));
    for (const m of MODULOS) expect(comTela.has(m.id) || m.id === "loja_online").toBe(true);
  });
});

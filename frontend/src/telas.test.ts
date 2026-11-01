import { describe, expect, it } from "vitest";

import type { Papel, Sessao } from "./api/tipos";
import { buscarTelas, telaAtual, telasDe } from "./telas";

const sessao = (papel: Papel): Sessao => ({ access_token: "x", usuario_id: "u", farmacia_id: "f", nome: "Teste", papel });
const caminhos = (papel: Papel) => telasDe(sessao(papel)).map((t) => t.para);

describe("telas por perfil", () => {
  it("o caixa não vê compras, financeiro nem usuários", () => {
    const telas = caminhos("caixa");
    expect(telas).toContain("/vendas");
    expect(telas).toContain("/caixas");
    for (const fechada of ["/compras", "/financeiro", "/configuracoes/usuarios", "/relatorios", "/controlados"]) {
      expect(telas).not.toContain(fechada);
    }
  });

  it("o estoque vê compras, mas não vendas nem caixa", () => {
    const telas = caminhos("estoque");
    expect(telas).toContain("/compras");
    expect(telas).toContain("/compras/pedidos");
    expect(telas).not.toContain("/vendas");
    expect(telas).not.toContain("/caixas");
  });

  it("gerente vê comissões e o vendedor vê as próprias vendas, no mesmo endereço", () => {
    const rotulo = (papel: Papel) => telasDe(sessao(papel)).find((t) => t.para === "/comissoes")?.rotulo;
    expect(rotulo("gerente")).toBe("Comissões");
    expect(rotulo("atendente")).toBe("Minhas vendas");
    expect(rotulo("estoque")).toBeUndefined();
  });

  it("só o administrador vê usuários", () => {
    expect(caminhos("admin")).toContain("/configuracoes/usuarios");
    expect(caminhos("gerente")).not.toContain("/configuracoes/usuarios");
  });
});

describe("busca de telas", () => {
  const todas = telasDe(sessao("admin"));
  const achar = (termo: string) => buscarTelas(todas, termo).map((t) => t.rotulo);

  it("acha sem acento e por pedaços", () => {
    expect(achar("ped comp")[0]).toBe("Pedidos de compra");
    expect(achar("inventario")[0]).toBe("Inventário");
    expect(achar("contas a pagar")[0]).toBe("Financeiro");
    expect(achar("boleto")[0]).toBe("Financeiro");
  });

  it("acha pelas palavras do dia a dia", () => {
    expect(achar("sngpc")).toEqual(["Controlados"]);
    expect(achar("xml")[0]).toBe("Compras");
    expect(achar("assistente")).toContain("Configurações gerais");
  });

  it("não mostra tela que o perfil não pode abrir", () => {
    expect(buscarTelas(telasDe(sessao("caixa")), "nota fiscal xml")).toEqual([]);
  });

  it("sem termo, lista só as telas do menu", () => {
    expect(buscarTelas(todas, "").some((t) => t.aba)).toBe(false);
  });
});

describe("tela atual", () => {
  const todas = telasDe(sessao("admin"));
  it("a aba ganha da tela principal", () => {
    expect(telaAtual(todas, "/compras/pedidos/123")?.rotulo).toBe("Pedidos de compra");
    expect(telaAtual(todas, "/compras/notas/9")?.rotulo).toBe("Compras");
    expect(telaAtual(todas, "/")?.rotulo).toBe("Visão geral");
  });
});

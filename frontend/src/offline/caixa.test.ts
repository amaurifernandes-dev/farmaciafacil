import { describe, expect, it } from "vitest";

import type { EsteTerminal, ResumoCaixa, Sessao } from "../api/tipos";
import type { VendaGuardada } from "./banco";
import { abrirSemInternet, fecharSemInternet, somarGuardadas } from "./caixa";

const terminal = {
  terminal: { id: "t1", nome: "PDV 01", loja_id: "l1" },
  loja: { id: "l1", nome: "Matriz" },
  pode_receber: true,
  motivo: null,
} as unknown as EsteTerminal;
const sessao: Sessao = { access_token: "x", usuario_id: "u1", farmacia_id: "f1", nome: "Amauri", papel: "caixa" };

function venda(caixa_id: string, total: number, pagamentos: [string, string][], extra: Partial<VendaGuardada> = {}): VendaGuardada {
  return {
    chave: Math.random().toString(),
    corpo: { offline_em: "2026-11-01T10:00:00Z", caixa_id, pagamentos: pagamentos.map(([forma, valor]) => ({ forma, valor })) },
    total_centavos: total,
    itens: 1,
    guardada_em: "2026-11-01T10:00:00Z",
    ...extra,
  };
}

describe("caixa sem internet", () => {
  it("abre com o id criado aqui e guarda a abertura para enviar", () => {
    const { resumo, guardada } = abrirSemInternet(terminal, sessao, 5000, new Date("2026-11-01T08:00:00Z"), "c1");
    expect(resumo.caixa).toMatchObject({ id: "c1", status: "aberto", valor_abertura: "50.00", terminal_id: "t1" });
    expect(resumo.dinheiro_esperado).toBe("50.00");
    expect(guardada).toMatchObject({
      tipo: "abrir",
      caminho: "/caixas/abrir",
      corpo: { id: "c1", valor_abertura: "50.00", offline_em: "2026-11-01T08:00:00.000Z" },
    });
  });

  it("soma as vendas guardadas deste caixa, tirando o troco", () => {
    const { resumo } = abrirSemInternet(terminal, sessao, 5000, new Date(), "c1");
    const somado = somarGuardadas(resumo, [
      venda("c1", 1240, [["dinheiro", "20.00"]]), // troco 7,60
      venda("c1", 1000, [["pix", "10.00"]]),
      venda("outro", 999, [["dinheiro", "9.99"]]),
      venda("c1", 500, [["dinheiro", "5.00"]], { problema: "recusada" }),
      { ...venda("c1", 0, []), tipo: "abrir" },
    ]);
    expect(somado.quantidade_vendas).toBe(2);
    expect(somado.total_vendido).toBe("22.40");
    expect(somado.por_forma).toEqual({ dinheiro: "20.00", pix: "10.00" });
    expect(somado.dinheiro_esperado).toBe("62.40");
  });

  it("fecha calculando a diferença e guarda o fechamento", () => {
    const resumo = { ...abrirSemInternet(terminal, sessao, 5000, new Date(), "c1").resumo, dinheiro_esperado: "62.40" } as ResumoCaixa;
    const fechado = fecharSemInternet(resumo, 6000, new Date("2026-11-01T18:00:00Z"));
    expect(fechado.resumo.caixa.status).toBe("fechado");
    expect(fechado.resumo.diferenca).toBe("-2.40");
    expect(fechado.guardada).toMatchObject({
      tipo: "fechar",
      caminho: "/caixas/c1/fechar",
      corpo: { valor_fechamento_informado: "60.00", offline_em: "2026-11-01T18:00:00.000Z" },
    });
  });
});

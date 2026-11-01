import { describe, expect, it } from "vitest";

import type { Papel, Sessao } from "../api/tipos";
import { haQuanto, perfilDoPainel, variacao } from "./Inicio";

const sessao = (papel: Papel): Sessao => ({ access_token: "x", usuario_id: "u", farmacia_id: "f", nome: "T", papel });

describe("painel inicial", () => {
  it("cada perfil abre no seu painel", () => {
    expect(perfilDoPainel(sessao("admin"))).toBe("gerencia");
    expect(perfilDoPainel(sessao("gerente"))).toBe("gerencia");
    expect(perfilDoPainel(sessao("farmaceutico"))).toBe("farmaceutico");
    expect(perfilDoPainel(sessao("estoque"))).toBe("estoque");
    expect(perfilDoPainel(sessao("caixa"))).toBe("balcao");
    expect(perfilDoPainel(sessao("atendente"))).toBe("balcao");
  });

  it("diz há quanto tempo a pré-venda espera", () => {
    const agora = new Date("2026-11-01T15:00:00Z");
    expect(haQuanto("2026-11-01T14:59:40Z", agora)).toBe("agora");
    expect(haQuanto("2026-11-01T14:48:00Z", agora)).toBe("há 12 min");
    expect(haQuanto("2026-11-01T12:00:00Z", agora)).toBe("há 3 h");
    expect(haQuanto("2026-10-30T15:00:00Z", agora)).toBe("há 2 dia(s)");
  });

  it("compara com ontem", () => {
    expect(variacao(150, 100)).toBe(50);
    expect(variacao(10, 0)).toBeNull();
  });
});

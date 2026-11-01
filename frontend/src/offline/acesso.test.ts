import { describe, expect, it } from "vitest";

import type { Sessao } from "../api/tipos";
import { cifrar, decifrar, sessaoSemInternet, tokenValido } from "./acesso";

const token = (exp: number) => `x.${btoa(JSON.stringify({ exp }))}.y`;
const agora = new Date("2026-11-01T12:00:00Z");
const sessao: Sessao = {
  access_token: token(agora.getTime() / 1000 - 10),
  usuario_id: "u1",
  farmacia_id: "f1",
  nome: "Bia",
  papel: "caixa",
};

describe("acesso sem internet", () => {
  it("só decifra com a senha certa e não guarda a senha", async () => {
    const acesso = await cifrar(" Bia@Exemplo.com ", "senha-forte", { sessao, token_offline: "OFF" }, "2026-11-08T12:00:00Z");
    expect(acesso.email).toBe("bia@exemplo.com");
    expect(JSON.stringify(acesso)).not.toContain("senha-forte");
    expect(JSON.stringify(acesso)).not.toContain("OFF");
    expect(await decifrar(acesso, "errada")).toBeNull();
    expect((await decifrar(acesso, "senha-forte"))?.token_offline).toBe("OFF");
  });

  it("usa o login normal enquanto vale e o acesso offline depois", () => {
    expect(tokenValido(token(agora.getTime() / 1000 + 3600), agora)).toBe(true);
    expect(tokenValido("lixo", agora)).toBe(false);
    const vencido = sessaoSemInternet({ sessao, token_offline: "OFF" }, agora);
    expect(vencido).toMatchObject({ access_token: "OFF", token_offline: "OFF", offline: true });
    const valido = { ...sessao, access_token: token(agora.getTime() / 1000 + 3600) };
    expect(sessaoSemInternet({ sessao: valido, token_offline: "OFF" }, agora).access_token).toBe(valido.access_token);
  });
});

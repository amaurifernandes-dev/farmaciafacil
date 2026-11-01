import { describe, expect, it } from "vitest";

import {
  CONVERSA_VAZIA,
  economia,
  esquecerConversa,
  type GuiaAtivo,
  guiaNestaTela,
  lerConversa,
  lerGuia,
  marcarPasso,
  salvarConversa,
  salvarGuia,
} from "./conversa";
import { textoDaFala } from "./voz";

function memoria(): Storage {
  const dados = new Map<string, string>();
  return {
    get length() {
      return dados.size;
    },
    clear: () => dados.clear(),
    getItem: (k) => dados.get(k) ?? null,
    key: (i) => [...dados.keys()][i] ?? null,
    removeItem: (k) => void dados.delete(k),
    setItem: (k, v) => void dados.set(k, v),
  };
}

const GUIA: GuiaAtivo = { tipo: "guia", id: "receber_nota", titulo: "Receber nota", rota: "/compras", passos: ["a", "b", "c"], feitos: [] };

describe("conversa do assistente", () => {
  it("guarda e recupera a conversa na aba, e esquece ao sair", () => {
    const armazem = memoria();
    expect(lerConversa(armazem)).toEqual(CONVERSA_VAZIA);
    const conversa = {
      historico: [{ role: "user" as const, content: [{ type: "text", text: "oi" }] }],
      falas: [{ de: "eu" as const, texto: "oi" }],
    };
    salvarConversa(conversa, armazem);
    salvarGuia(GUIA, armazem);
    expect(lerConversa(armazem)).toEqual(conversa);
    expect(lerGuia(armazem)?.rota).toBe("/compras");
    esquecerConversa(armazem);
    expect(lerConversa(armazem)).toEqual(CONVERSA_VAZIA);
    expect(lerGuia(armazem)).toBeNull();
  });

  it("ignora o que estiver estragado", () => {
    const armazem = memoria();
    armazem.setItem("ff.assistente.conversa", "{quebrado");
    expect(lerConversa(armazem)).toEqual(CONVERSA_VAZIA);
    armazem.setItem("ff.assistente.conversa", JSON.stringify({ falas: 1 }));
    expect(lerConversa(armazem)).toEqual(CONVERSA_VAZIA);
  });

  it("mostra o passo a passo na tela do guia e nas de baixo", () => {
    expect(guiaNestaTela(GUIA, "/compras")).toBe(true);
    expect(guiaNestaTela(GUIA, "/compras/notas/1")).toBe(true);
    expect(guiaNestaTela(GUIA, "/comprasx")).toBe(false);
    expect(guiaNestaTela(GUIA, "/")).toBe(false);
    expect(guiaNestaTela(null, "/compras")).toBe(false);
  });

  it("marca e desmarca passos", () => {
    const um = marcarPasso(GUIA, 2);
    const dois = marcarPasso(um, 0);
    expect(dois.feitos).toEqual([0, 2]);
    expect(marcarPasso(dois, 2).feitos).toEqual([0]);
  });

  it("calcula a economia da promoção", () => {
    expect(economia("59.90", "29.95")).toBe(29.95);
    expect(economia("10.00", "10.00")).toBe(0);
  });

  it("junta os pedaços da fala", () => {
    const resultados = [
      { isFinal: true, 0: { transcript: "procura protetor" } },
      { isFinal: false, 0: { transcript: "  solar " } },
    ];
    expect(textoDaFala(resultados)).toBe("procura protetor solar");
  });
});

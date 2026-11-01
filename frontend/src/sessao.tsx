import { createContext, useContext, useState, type ReactNode } from "react";

import { api, lerChaveTerminal, lerSessao, salvarSessao } from "./api/cliente";
import type { Sessao } from "./api/tipos";
import { cifrar, entrarSemInternet, guardarAcesso } from "./offline/acesso";
import { ehFalhaDeRede } from "./offline/catalogo";

interface ContextoSessao {
  sessao: Sessao | null;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
}

const Contexto = createContext<ContextoSessao | null>(null);

export function SessaoProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(lerSessao);

  async function entrar(email: string, senha: string) {
    let nova: Sessao;
    try {
      nova = await api<Sessao>("/auth/login", { corpo: { email, senha } });
    } catch (e) {
      // Caixa sem internet: confere a senha com o acesso guardado neste computador.
      if (!ehFalhaDeRede(e) || !lerChaveTerminal()) throw e;
      nova = await entrarSemInternet(email, senha);
      salvarSessao(nova);
      setSessao(nova);
      return;
    }
    salvarSessao(nova);
    if (lerChaveTerminal() && podeReceber(nova)) {
      // Num PDV: guarda o acesso para entrar sem internet nos próximos 7 dias.
      try {
        const off = await api<{ token_offline: string; expira_em: string }>("/auth/token-offline", { corpo: {} });
        nova = { ...nova, token_offline: off.token_offline };
        salvarSessao(nova);
        await guardarAcesso(await cifrar(email, senha, { sessao: nova, token_offline: off.token_offline }, off.expira_em));
      } catch {
        /* sem o acesso guardado, este operador só não entra sem internet */
      }
    }
    setSessao(nova);
  }

  function sair() {
    salvarSessao(null);
    setSessao(null);
  }

  return <Contexto.Provider value={{ sessao, entrar, sair }}>{children}</Contexto.Provider>;
}

export function useSessao(): ContextoSessao {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useSessao fora do SessaoProvider");
  return contexto;
}

export function ehGerente(sessao: Sessao | null): boolean {
  return sessao?.papel === "admin" || sessao?.papel === "gerente";
}

export function ehAdmin(sessao: Sessao | null): boolean {
  return sessao?.papel === "admin";
}

/** Perfis que podem abrir caixa e receber pagamentos. */
export function podeReceber(sessao: Sessao | null): boolean {
  return ["admin", "gerente", "farmaceutico", "caixa"].includes(sessao?.papel ?? "");
}

/** Perfis que cuidam do livro de remédios controlados (SNGPC). */
export function ehFarmaceutico(sessao: Sessao | null): boolean {
  return ["admin", "gerente", "farmaceutico"].includes(sessao?.papel ?? "");
}

/** Perfis que cadastram produtos e fornecedores e dão entrada no estoque. */
export function cuidaDoEstoque(sessao: Sessao | null): boolean {
  return ["admin", "gerente", "farmaceutico", "estoque"].includes(sessao?.papel ?? "");
}

export const NOMES_PAPEIS: Record<Sessao["papel"], string> = {
  admin: "Administrador",
  gerente: "Gerente",
  farmaceutico: "Farmacêutico",
  caixa: "Operador de caixa",
  atendente: "Atendente",
  estoque: "Estoque",
};

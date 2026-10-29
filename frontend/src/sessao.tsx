import { createContext, useContext, useState, type ReactNode } from "react";

import { api, lerSessao, salvarSessao } from "./api/cliente";
import type { Sessao } from "./api/tipos";

interface ContextoSessao {
  sessao: Sessao | null;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
}

const Contexto = createContext<ContextoSessao | null>(null);

export function SessaoProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(lerSessao);

  async function entrar(email: string, senha: string) {
    const nova = await api<Sessao>("/auth/login", { corpo: { email, senha } });
    salvarSessao(nova);
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

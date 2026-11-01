import { useEffect, useState } from "react";

import { api } from "./api/cliente";

/** Onde o sistema está instalado: na nuvem (internet) ou num computador da própria farmácia. */
export interface Instalacao {
  modo: "nuvem" | "farmacia";
  /** A loja online e o Pix pelo site só existem com o sistema na internet. */
  loja_online: boolean;
}

const NA_NUVEM: Instalacao = { modo: "nuvem", loja_online: true };
let lida: Promise<Instalacao> | null = null;

/** Pergunta uma vez ao servidor; sem resposta (sem internet), segue como na nuvem. */
export function lerInstalacao(): Promise<Instalacao> {
  lida ??= api<Instalacao>("/instalacao").catch(() => {
    lida = null;
    return NA_NUVEM;
  });
  return lida;
}

export function useInstalacao(): Instalacao | null {
  const [instalacao, setInstalacao] = useState<Instalacao | null>(null);
  useEffect(() => {
    let vivo = true;
    lerInstalacao().then((i) => vivo && setInstalacao(i));
    return () => {
      vivo = false;
    };
  }, []);
  return instalacao;
}

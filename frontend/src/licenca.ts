import { useEffect, useState } from "react";

import { api } from "./api/cliente";
import type { Licenca, Sessao } from "./api/tipos";

let lida: { farmacia: string; licenca: Promise<Licenca | null> } | null = null;

/** Pergunta uma vez por sessão; sem resposta (sem internet, por exemplo), não mostra aviso. */
export function useLicenca(sessao: Sessao | null): Licenca | null {
  const [licenca, setLicenca] = useState<Licenca | null>(null);
  useEffect(() => {
    if (!sessao || sessao.offline) return;
    if (lida?.farmacia !== sessao.farmacia_id) {
      lida = { farmacia: sessao.farmacia_id, licenca: api<Licenca>("/licenca").catch(() => null) };
    }
    let vivo = true;
    lida.licenca.then((l) => vivo && setLicenca(l));
    return () => {
      vivo = false;
    };
  }, [sessao]);
  return licenca;
}

/** Depois de ativar ou renovar: o aviso do topo some na hora. */
export function avisarLicenca(farmaciaId: string, licenca: Licenca) {
  lida = { farmacia: farmaciaId, licenca: Promise.resolve(licenca) };
}

export const NOMES_PLANO = { mensal: "Mensal", anual: "Anual", vitalicio: "Vitalícia" } as const;

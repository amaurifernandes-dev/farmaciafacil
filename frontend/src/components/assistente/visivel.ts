import { useEffect, useState } from "react";

import { api } from "../../api/cliente";
import type { Sessao } from "../../api/tipos";

export interface StatusAssistente {
  /** O servidor tem a chave da Anthropic. */
  ligado: boolean;
  /** O administrador liberou o assistente para este perfil. */
  permitido: boolean;
  mensagem: string | null;
}

const chave = (usuarioId: string) => `ff.assistente.visivel.${usuarioId}`;

function lerVisivel(usuarioId: string): boolean {
  try {
    return localStorage.getItem(chave(usuarioId)) === "1";
  } catch {
    return false;
  }
}

/**
 * Se o assistente pode aparecer (chave no servidor + perfil liberado) e se a pessoa quer vê-lo.
 * Começa escondido: cada pessoa liga no botão do topo, e a escolha fica lembrada neste navegador.
 */
export function useAssistente(sessao: Sessao | null) {
  const [status, setStatus] = useState<StatusAssistente | null>(null);
  const [visivel, setVisivel] = useState(() => (sessao ? lerVisivel(sessao.usuario_id) : false));
  // Ligou agora no botão: abre a conversa já. Ao recarregar a página, só o botão aparece.
  const [abrirAgora, setAbrirAgora] = useState(false);

  useEffect(() => {
    if (!sessao || sessao.offline) return;
    let vivo = true;
    api<StatusAssistente>("/assistente/status")
      .then((s) => vivo && setStatus(s))
      .catch(() => vivo && setStatus(null));
    return () => {
      vivo = false;
    };
  }, [sessao]);

  function alternar() {
    if (!sessao) return;
    const novo = !visivel;
    setVisivel(novo);
    setAbrirAgora(novo);
    try {
      localStorage.setItem(chave(sessao.usuario_id), novo ? "1" : "0");
    } catch {
      // só não lembra a escolha
    }
  }

  const disponivel = Boolean(status?.ligado && status.permitido);
  return { status, disponivel, visivel: disponivel && visivel, abrirAgora, alternar };
}

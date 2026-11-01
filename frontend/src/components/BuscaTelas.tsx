import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { buscarTelas, GRUPOS, type Tela } from "../telas";
import Icone from "./Icone";

const NOME_GRUPO = Object.fromEntries(GRUPOS.map((g) => [g.id, g.rotulo]));

/** Janela "Ir para": acha qualquer tela pelo nome ou por palavras do dia a dia (Ctrl+K). */
export default function BuscaTelas({ telas, aoFechar }: { telas: Tela[]; aoFechar: () => void }) {
  const navegar = useNavigate();
  const [termo, setTermo] = useState("");
  const [marcada, setMarcada] = useState(0);
  const lista = useRef<HTMLUListElement>(null);
  const achadas = buscarTelas(telas, termo).slice(0, 12);

  useEffect(() => {
    setMarcada(0);
  }, [termo]);
  useEffect(() => {
    lista.current?.querySelector<HTMLElement>(`[data-indice="${marcada}"]`)?.scrollIntoView({ block: "nearest" });
  }, [marcada]);

  function ir(tela: Tela | undefined) {
    if (!tela) return;
    aoFechar();
    navegar(tela.para);
  }

  return (
    <div className="busca-telas-fundo" onMouseDown={aoFechar}>
      <div
        className="busca-telas"
        role="dialog"
        aria-modal="true"
        aria-label="Ir para uma tela"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <label className="busca-telas-campo">
          <Icone nome="busca" />
          <input
            autoFocus
            value={termo}
            placeholder="Para onde você quer ir? Ex.: contas a pagar, inventário, nota fiscal"
            aria-label="Nome da tela"
            onChange={(e) => setTermo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setMarcada((m) => Math.min(m + 1, achadas.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setMarcada((m) => Math.max(m - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                ir(achadas[marcada]);
              } else if (e.key === "Escape") {
                aoFechar();
              }
            }}
          />
          <kbd>Esc</kbd>
        </label>
        {achadas.length === 0 ? (
          <p className="busca-telas-vazio">Nenhuma tela com esse nome para o seu perfil.</p>
        ) : (
          <ul ref={lista} className="busca-telas-lista">
            {achadas.map((t, i) => (
              <li key={`${t.para}-${t.rotulo}`}>
                <button
                  type="button"
                  data-indice={i}
                  className={i === marcada ? "marcada" : ""}
                  onMouseEnter={() => setMarcada(i)}
                  onClick={() => ir(t)}
                >
                  <span className="busca-telas-icone">
                    <Icone nome={t.icone} />
                  </span>
                  <span className="busca-telas-texto">
                    <strong>{t.rotulo}</strong>
                    <small>{t.descricao}</small>
                  </span>
                  <span className="busca-telas-grupo">{NOME_GRUPO[t.grupo]}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="busca-telas-dica">
          <kbd>↑</kbd> <kbd>↓</kbd> para escolher · <kbd>Enter</kbd> para abrir · <kbd>Ctrl</kbd> + <kbd>K</kbd> abre esta busca de
          qualquer tela
        </p>
      </div>
    </div>
  );
}

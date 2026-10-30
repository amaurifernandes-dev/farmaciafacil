import { useEffect, useState } from "react";

import { api, mensagem } from "../api/cliente";
import type { PaginaProdutos, Produto } from "../api/tipos";
import { reais } from "../formato";

/** Campo para achar um produto pelo nome ou pelo código de barras (bipado ou digitado). */
export default function BuscaProduto({
  aoEscolher,
  inicial = "",
  autoFocus = false,
}: {
  aoEscolher: (produto: Produto) => void;
  inicial?: string;
  autoFocus?: boolean;
}) {
  const [termo, setTermo] = useState(inicial);
  const [resultados, setResultados] = useState<Produto[]>([]);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const busca = termo.trim();
    if (busca.length < 3) {
      setResultados([]);
      return;
    }
    const espera = setTimeout(() => {
      api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(busca)}&por_pagina=8`)
        .then((pagina) => {
          setResultados(pagina.itens);
          setErro(pagina.itens.length === 0 ? "Nenhum produto encontrado" : "");
        })
        .catch((e) => setErro(mensagem(e)));
    }, 250);
    return () => clearTimeout(espera);
  }, [termo]);

  function escolher(produto: Produto) {
    aoEscolher(produto);
    setTermo("");
    setResultados([]);
  }

  return (
    <div className="busca-produto">
      <input
        placeholder="Nome do produto ou código de barras"
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        onKeyDown={(e) => {
          // O leitor de código de barras termina com Enter: se só sobrou um, já escolhe.
          if (e.key === "Enter") {
            e.preventDefault();
            if (resultados.length === 1) escolher(resultados[0]);
          }
        }}
        autoFocus={autoFocus}
      />
      {resultados.length > 0 && (
        <ul className="resultados">
          {resultados.map((p) => (
            <li key={p.id} onClick={() => escolher(p)}>
              <span>
                {p.nome} {p.apresentacao && <small>{p.apresentacao}</small>}
                {p.ean && <small> · {p.ean}</small>}
              </span>
              <small>{reais(p.preco_venda)}</small>
            </li>
          ))}
        </ul>
      )}
      {erro && termo.trim().length >= 3 && <p className="vazio">{erro}</p>}
    </div>
  );
}

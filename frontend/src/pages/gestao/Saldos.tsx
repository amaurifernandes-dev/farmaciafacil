import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { PaginaSaldos } from "../../api/tipos";
import { quantidade } from "../../formato";
import { useLojas } from "../../lojas";

/** Quanto cada produto tem em cada loja. */
export default function Saldos() {
  const lojas = useLojas();
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState<PaginaSaldos | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const espera = setTimeout(() => {
      api<PaginaSaldos>(`/estoque/saldos?busca=${encodeURIComponent(busca.trim())}&por_pagina=100`)
        .then(setPagina)
        .catch((e) => setErro(mensagem(e)));
    }, 250);
    return () => clearTimeout(espera);
  }, [busca]);

  return (
    <div className="pagina">
      <h1>Saldo por loja</h1>
      <p className="vazio">Quantidade que pode ser vendida em cada loja. Lotes vencidos não entram na conta.</p>
      <div className="barra">
        <input placeholder="Buscar por nome ou código de barras" value={busca} onChange={(e) => setBusca(e.target.value)} />
      </div>
      {erro && <p className="erro">{erro}</p>}
      <section className="cartao">
        {pagina && pagina.itens.length === 0 ? (
          <p className="lista-vazia">Nenhum produto encontrado.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  {lojas.map((l) => (
                    <th key={l.id} className="num">
                      {l.nome}
                    </th>
                  ))}
                  {lojas.length > 1 && <th className="num">Total</th>}
                  <th className="num">Mínimo</th>
                </tr>
              </thead>
              <tbody>
                {pagina?.itens.map((p) => (
                  <tr key={p.produto_id}>
                    <td>
                      {p.nome} {p.apresentacao && <small>{p.apresentacao}</small>}
                      {Number(p.vencido) > 0 && (
                        <span className="etiqueta erro-etiqueta">{quantidade(p.vencido)} vencido(s)</span>
                      )}
                    </td>
                    {lojas.map((l) => {
                      const saldo = p.por_loja[l.id] ?? "0";
                      const baixo = Number(p.estoque_minimo) > 0 && Number(saldo) < Number(p.estoque_minimo);
                      return (
                        <td key={l.id} className={`num ${baixo ? "abaixo" : ""}`}>
                          {quantidade(saldo)}
                        </td>
                      );
                    })}
                    {lojas.length > 1 && (
                      <td className="num">
                        <strong>{quantidade(p.total)}</strong>
                      </td>
                    )}
                    <td className="num">{quantidade(p.estoque_minimo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {pagina && <p className="rodape">{pagina.total} produto(s)</p>}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Produto } from "../../api/tipos";
import BuscaProduto from "../../components/BuscaProduto";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { useLojas } from "../../lojas";

interface Linha {
  produto: Produto;
  numero_lote: string;
  validade: string;
  quantidade: string;
  custo_unitario: string;
}

/** Entrada sem nota fiscal eletrônica (ou quando o XML não está à mão). */
export default function Entrada() {
  const lojas = useLojas();
  const [lojaId, setLojaId] = useState("");
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [observacao, setObservacao] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);

  useEffect(() => {
    if (!lojaId && lojas.length > 0) setLojaId(lojas[0].id);
  }, [lojas, lojaId]);

  function adicionar(produto: Produto) {
    setLinhas([...linhas, { produto, numero_lote: "", validade: "", quantidade: "1", custo_unitario: "" }]);
    setAviso(null);
  }

  function alterar(indice: number, campo: keyof Omit<Linha, "produto">, valor: string) {
    setLinhas(linhas.map((linha, i) => (i === indice ? { ...linha, [campo]: valor } : linha)));
  }

  async function registrar() {
    try {
      await api("/estoque/entradas", {
        corpo: {
          loja_id: lojaId || null,
          observacao: observacao || null,
          itens: linhas.map((l) => ({
            produto_id: l.produto.id,
            numero_lote: l.produto.controla_lote ? l.numero_lote : null,
            validade: l.produto.controla_lote ? l.validade || null : null,
            quantidade: l.quantidade.replace(",", "."),
            custo_unitario: l.custo_unitario ? l.custo_unitario.replace(",", ".") : null,
          })),
        },
      });
      setLinhas([]);
      setObservacao("");
      setAviso({ tipo: "ok", texto: "Entrada registrada" });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Entrada manual</h1>
          <p className="vazio">
            Tem o XML da nota? Use <Link to="/compras">Compras</Link>: os itens entram sozinhos.
          </p>
        </div>
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} rotulo="Loja que recebe" />
      </div>

      <section className="cartao espaco-acima">
        <BuscaProduto aoEscolher={adicionar} autoFocus />

        {linhas.length > 0 && (
          <div className="tabela-rolagem espaco-acima">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Lote</th>
                  <th>Validade</th>
                  <th className="num">Quantidade</th>
                  <th className="num">Custo unit. (R$)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l, i) => (
                  <tr key={i}>
                    <td>{l.produto.nome}</td>
                    <td>
                      {l.produto.controla_lote ? (
                        <input value={l.numero_lote} onChange={(e) => alterar(i, "numero_lote", e.target.value)} required />
                      ) : (
                        <small>sem lote</small>
                      )}
                    </td>
                    <td>
                      {l.produto.controla_lote && (
                        <input type="date" value={l.validade} onChange={(e) => alterar(i, "validade", e.target.value)} required />
                      )}
                    </td>
                    <td className="num">
                      <input className="quantidade" value={l.quantidade} onChange={(e) => alterar(i, "quantidade", e.target.value)} />
                    </td>
                    <td className="num">
                      <input className="quantidade" value={l.custo_unitario} onChange={(e) => alterar(i, "custo_unitario", e.target.value)} />
                    </td>
                    <td>
                      <button type="button" className="botao-icone" title="Remover" onClick={() => setLinhas(linhas.filter((_, j) => j !== i))}>
                        <Icone nome="lixo" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {linhas.length > 0 && (
          <div className="barra espaco-acima">
            <input placeholder="Observação (ex.: NF 1234, fornecedor)" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
            <button className="botao" onClick={registrar}>
              Registrar entrada
            </button>
          </div>
        )}
        {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
      </section>
    </div>
  );
}

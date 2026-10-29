import { useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ProdutoPDV } from "../../api/tipos";
import { quantidade as fmtQtd } from "../../formato";

interface Linha {
  produto: ProdutoPDV;
  numero_lote: string;
  validade: string;
  quantidade: string;
  custo_unitario: string;
}

export default function Entrada() {
  const [codigo, setCodigo] = useState("");
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [observacao, setObservacao] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);

  async function adicionar(evento: FormEvent) {
    evento.preventDefault();
    if (!codigo.trim()) return;
    try {
      const produto = await api<ProdutoPDV>(`/produtos/ean/${codigo.trim()}`);
      setLinhas([...linhas, { produto, numero_lote: "", validade: "", quantidade: "1", custo_unitario: "" }]);
      setCodigo("");
      setAviso(null);
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  function alterar(indice: number, campo: keyof Omit<Linha, "produto">, valor: string) {
    setLinhas(linhas.map((linha, i) => (i === indice ? { ...linha, [campo]: valor } : linha)));
  }

  async function registrar() {
    try {
      await api("/estoque/entradas", {
        corpo: {
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
      <h1>Entrada de estoque</h1>
      <form className="barra" onSubmit={adicionar}>
        <input placeholder="Bipe ou digite o código de barras" value={codigo} onChange={(e) => setCodigo(e.target.value)} autoFocus />
        <button type="submit">Adicionar</button>
      </form>

      <table className="tabela">
        <thead>
          <tr>
            <th>Produto</th>
            <th>Saldo atual</th>
            <th>Lote</th>
            <th>Validade</th>
            <th>Quantidade</th>
            <th>Custo unit. (R$)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l, i) => (
            <tr key={i}>
              <td>{l.produto.nome}</td>
              <td>{fmtQtd(l.produto.saldo)}</td>
              <td>
                {l.produto.controla_lote ? (
                  <input value={l.numero_lote} onChange={(e) => alterar(i, "numero_lote", e.target.value)} required />
                ) : (
                  "sem lote"
                )}
              </td>
              <td>
                {l.produto.controla_lote && (
                  <input type="date" value={l.validade} onChange={(e) => alterar(i, "validade", e.target.value)} required />
                )}
              </td>
              <td>
                <input value={l.quantidade} onChange={(e) => alterar(i, "quantidade", e.target.value)} size={6} />
              </td>
              <td>
                <input value={l.custo_unitario} onChange={(e) => alterar(i, "custo_unitario", e.target.value)} size={8} />
              </td>
              <td>
                <button onClick={() => setLinhas(linhas.filter((_, j) => j !== i))}>Remover</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {linhas.length > 0 && (
        <div className="barra">
          <input placeholder="Observação (ex.: NF 1234, fornecedor)" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
          <button onClick={registrar}>Registrar entrada</button>
        </div>
      )}
      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
    </div>
  );
}

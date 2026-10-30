import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Lote, Produto } from "../../api/tipos";
import BuscaProduto from "../../components/BuscaProduto";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, quantidade as fmtQtd } from "../../formato";
import { useLojas } from "../../lojas";

interface Linha {
  produto: Produto;
  lote: Lote;
  quantidade: string;
}

function vencido(lote: Lote): boolean {
  return lote.validade !== null && lote.validade < new Date().toISOString().slice(0, 10);
}

/** Leva mercadoria de uma loja para outra, lote por lote. */
export default function Transferencia() {
  const lojas = useLojas();
  const [origem, setOrigem] = useState("");
  const [destino, setDestino] = useState("");
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [observacao, setObservacao] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);

  useEffect(() => {
    if (lojas.length > 1 && !origem) {
      setOrigem(lojas[0].id);
      setDestino(lojas[1].id);
    }
  }, [lojas, origem]);

  function trocarOrigem(lojaId: string) {
    setOrigem(lojaId);
    setLinhas([]);
    if (lojaId === destino) setDestino(lojas.find((l) => l.id !== lojaId)?.id ?? "");
  }

  async function adicionar(produto: Produto) {
    try {
      const lotes = await api<Lote[]>(`/estoque/lotes?produto_id=${produto.id}&loja_id=${origem}`);
      const disponiveis = lotes.filter((l) => !vencido(l) && !linhas.some((linha) => linha.lote.id === l.id));
      if (disponiveis.length === 0) {
        setAviso({ tipo: "erro", texto: `${produto.nome} não tem saldo nesta loja` });
        return;
      }
      setLinhas([...linhas, ...disponiveis.map((lote) => ({ produto, lote, quantidade: "" }))]);
      setAviso(null);
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  async function transferir() {
    const itens = linhas
      .filter((l) => Number(l.quantidade.replace(",", ".")) > 0)
      .map((l) => ({ lote_id: l.lote.id, quantidade: l.quantidade.replace(",", ".") }));
    if (itens.length === 0) {
      setAviso({ tipo: "erro", texto: "Informe a quantidade de pelo menos um lote" });
      return;
    }
    try {
      await api("/estoque/transferencias", {
        corpo: { loja_destino_id: destino, itens, observacao: observacao || null },
      });
      const nome = lojas.find((l) => l.id === destino)?.nome;
      setLinhas([]);
      setObservacao("");
      setAviso({ tipo: "ok", texto: `Transferência registrada. A mercadoria já aparece no estoque de ${nome}.` });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (lojas.length > 0 && lojas.length < 2) {
    return (
      <div className="pagina">
        <h1>Transferir entre lojas</h1>
        <p className="lista-vazia cartao">Cadastre uma filial em Configurações › Minha farmácia para transferir mercadoria.</p>
      </div>
    );
  }

  return (
    <div className="pagina">
      <h1>Transferir entre lojas</h1>
      <p className="vazio">O saldo sai de uma loja e entra na outra com o mesmo lote e validade.</p>

      <section className="cartao espaco-acima">
        <div className="lojas-transferencia">
          <SeletorLoja lojas={lojas} valor={origem} aoMudar={trocarOrigem} rotulo="Sai de" />
          <span className="seta-transferencia">
            <Icone nome="seta" />
          </span>
          <SeletorLoja lojas={lojas.filter((l) => l.id !== origem)} valor={destino} aoMudar={setDestino} rotulo="Vai para" />
        </div>
        <div className="espaco-acima">
          <BuscaProduto aoEscolher={adicionar} />
        </div>

        {linhas.length > 0 && (
          <div className="tabela-rolagem espaco-acima">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Lote</th>
                  <th>Validade</th>
                  <th className="num">Tem na origem</th>
                  <th className="num">Transferir</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l, i) => (
                  <tr key={l.lote.id}>
                    <td>{l.produto.nome}</td>
                    <td>{l.lote.numero_lote}</td>
                    <td>{data(l.lote.validade)}</td>
                    <td className="num">{fmtQtd(l.lote.quantidade)}</td>
                    <td className="num">
                      <input
                        className="quantidade"
                        value={l.quantidade}
                        onChange={(e) =>
                          setLinhas(linhas.map((linha, j) => (j === i ? { ...linha, quantidade: e.target.value } : linha)))
                        }
                        placeholder="0"
                      />
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
            <input placeholder="Observação (opcional)" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
            <button className="botao" onClick={transferir} disabled={!destino}>
              Transferir
            </button>
          </div>
        )}
        {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
      </section>
    </div>
  );
}

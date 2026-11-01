import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { NotaEntrada, NotaEntradaResumo, StatusNotaEntrada } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";

export const STATUS_NOTA: Record<StatusNotaEntrada, { rotulo: string; classe: string }> = {
  pendente: { rotulo: "Para conferir", classe: "etiqueta" },
  confirmada: { rotulo: "No estoque", classe: "etiqueta ok" },
  cancelada: { rotulo: "Cancelada", classe: "etiqueta erro-etiqueta" },
};

export default function Notas() {
  const navegar = useNavigate();
  const lojas = useLojas();
  const arquivo = useRef<HTMLInputElement>(null);
  const [lojaId, setLojaId] = useState("");
  const [notas, setNotas] = useState<NotaEntradaResumo[] | null>(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api<NotaEntradaResumo[]>("/compras/notas")
      .then(setNotas)
      .catch((e) => setErro(mensagem(e)));
  }, []);

  async function importar(lista: FileList | null) {
    const escolhido = lista?.[0];
    if (!escolhido) return;
    setErro("");
    setEnviando(true);
    try {
      const xml = await escolhido.text();
      const nota = await api<NotaEntrada>("/compras/notas", { corpo: { xml, loja_id: lojaId || null } });
      navegar(`/compras/notas/${nota.id}`);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setEnviando(false);
      if (arquivo.current) arquivo.current.value = "";
    }
  }

  const nomeLoja = (id: string) => lojas.find((l) => l.id === id)?.nome ?? "";

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Notas de entrada</h1>
          <p className="vazio">Importe o XML da nota do fornecedor: os produtos, lotes e validades entram sozinhos.</p>
        </div>
      </div>

      <section
        className="cartao importar-xml espaco-acima"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          importar(e.dataTransfer.files);
        }}
      >
        <span className="atalho-icone">
          <Icone nome="entrada" />
        </span>
        <div>
          <h2>Importar XML da nota</h2>
          <p className="vazio">
            Arraste o arquivo .xml para cá ou escolha no computador. A loja é reconhecida pelo CNPJ da nota.
          </p>
          <div className="acoes espaco-acima">
            <button className="botao" type="button" disabled={enviando} onClick={() => arquivo.current?.click()}>
              {enviando ? "Lendo a nota..." : "Escolher arquivo XML"}
            </button>
            {lojas.length > 1 && (
              <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Loja pelo CNPJ da nota" rotulo="" />
            )}
          </div>
          <input ref={arquivo} type="file" accept=".xml,text/xml,application/xml" hidden onChange={(e) => importar(e.target.files)} />
        </div>
      </section>
      {erro && <p className="erro espaco-acima">{erro}</p>}

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>Últimas notas</h2>
        </div>
        {notas && notas.length === 0 ? (
          <p className="lista-vazia">Nenhuma nota importada ainda.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nota</th>
                  <th>Fornecedor</th>
                  <th>Emissão</th>
                  {lojas.length > 1 && <th>Loja</th>}
                  <th className="num">Itens</th>
                  <th className="num">Valor</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {notas?.map((n) => (
                  <tr key={n.id}>
                    <td>
                      <Link to={`/compras/notas/${n.id}`}>
                        {n.numero} <small>série {n.serie}</small>
                      </Link>
                    </td>
                    <td>
                      {n.fornecedor_nome}
                      {n.pedido_id && (
                        <>
                          <br />
                          <small>
                            <Link to={`/compras/pedidos/${n.pedido_id}`}>pedido nº {n.pedido_numero}</Link>
                          </small>
                        </>
                      )}
                    </td>
                    <td>{data(n.emitida_em)}</td>
                    {lojas.length > 1 && <td>{nomeLoja(n.loja_id)}</td>}
                    <td className="num">{n.quantidade_itens}</td>
                    <td className="num">{reais(n.valor_total)}</td>
                    <td>
                      <span className={STATUS_NOTA[n.status].classe}>{STATUS_NOTA[n.status].rotulo}</span>
                      {n.status === "pendente" && n.itens_sem_produto > 0 && (
                        <small> · {n.itens_sem_produto} sem produto</small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

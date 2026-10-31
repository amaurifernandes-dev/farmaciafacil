import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { EscopoInventario, Inventario } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { reais } from "../../formato";
import { useLojas } from "../../lojas";
import { cuidaDoEstoque, useSessao } from "../../sessao";

export const STATUS_INVENTARIO = {
  aberto: { texto: "Contando", classe: "ok" },
  finalizado: { texto: "Finalizado", classe: "etiqueta-neutra" },
  cancelado: { texto: "Cancelado", classe: "erro-etiqueta" },
};

export function quando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** Inventários da farmácia: abrir uma contagem e acompanhar as que já foram feitas. */
export default function Inventarios() {
  const { sessao } = useSessao();
  const pode = cuidaDoEstoque(sessao);
  const lojas = useLojas();
  const navegar = useNavigate();
  const [lista, setLista] = useState<Inventario[] | null>(null);
  const [lojaId, setLojaId] = useState("");
  const [descricao, setDescricao] = useState("Inventário geral");
  const [escopo, setEscopo] = useState<EscopoInventario>("parcial");
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Inventario[]>("/inventarios")
      .then(setLista)
      .catch((e) => setErro(mensagem(e)));
  }, []);

  useEffect(() => {
    if (!lojaId && lojas.length) setLojaId(lojas[0].id);
  }, [lojas, lojaId]);

  async function abrir(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      const novo = await api<Inventario>("/inventarios", { corpo: { loja_id: lojaId || null, descricao, escopo } });
      navegar(`/estoque/inventario/${novo.id}`);
    } catch (falha) {
      setErro(mensagem(falha));
    }
  }

  const abertos = lista?.filter((i) => i.status === "aberto") ?? [];

  return (
    <div className="pagina">
      <p className="vazio">
        Conte o estoque da loja bipando os produtos com o celular ou com o leitor do caixa. No fim, o sistema mostra o
        que sobrou e o que faltou e acerta o saldo para o que foi contado.
      </p>

      {erro && <p className="erro">{erro}</p>}

      {abertos.map((i) => (
        <div key={i.id} className="cartao cartao-separado inventario-aberto">
          <div>
            <strong>{i.descricao}</strong> <span className="etiqueta ok">Contando</span>
            <span className="livro-detalhe">
              {i.loja_nome} · aberto por {i.aberto_por} em {quando(i.criado_em)}
            </span>
          </div>
          <span className="espaco" />
          <Link className="botao" to={`/inventario/${i.id}/contar`}>
            <Icone nome="celular" /> Contar
          </Link>
          {pode && (
            <Link className="botao-contorno" to={`/estoque/inventario/${i.id}`}>
              Ver diferenças
            </Link>
          )}
        </div>
      ))}

      {pode && (
        <form className="cartao cartao-separado formulario-inventario" onSubmit={abrir}>
          <h2>Abrir uma contagem</h2>
          <div className="linha-campos">
            <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} />
            <label>
              Nome
              <input value={descricao} onChange={(e) => setDescricao(e.target.value)} maxLength={80} required minLength={3} />
            </label>
          </div>
          <label className="opcao-escopo">
            <input type="radio" checked={escopo === "parcial"} onChange={() => setEscopo("parcial")} />
            <span>
              <strong>Parcial</strong> (uma prateleira, um corredor, uma marca): só muda o saldo do que for contado.
            </span>
          </label>
          <label className="opcao-escopo">
            <input type="radio" checked={escopo === "geral"} onChange={() => setEscopo("geral")} />
            <span>
              <strong>Geral</strong> (a loja inteira): o produto com saldo que ninguém contar fica com zero.
            </span>
          </label>
          <p className="nota">Controlados não entram: a diferença deles é lançada como perda com o motivo da Anvisa.</p>
          <div>
            <button type="submit" className="botao">
              Abrir contagem
            </button>
          </div>
        </form>
      )}

      <div className="cartao cartao-separado">
        <div className="cartao-cabecalho">
          <h2>Contagens</h2>
        </div>
        <table className="tabela">
          <thead>
            <tr>
              <th>Inventário</th>
              <th>Situação</th>
              <th className="num">Ajustados</th>
              <th className="num">Faltou</th>
              <th className="num">Sobrou</th>
            </tr>
          </thead>
          <tbody>
            {lista?.map((i) => (
              <tr key={i.id} className={pode ? "linha-clicavel" : ""} onClick={() => pode && navegar(`/estoque/inventario/${i.id}`)}>
                <td>
                  <strong>{i.descricao}</strong>
                  <span className="livro-detalhe">
                    {i.loja_nome} · {i.escopo === "geral" ? "geral" : "parcial"} · {quando(i.finalizado_em ?? i.criado_em)}
                  </span>
                </td>
                <td>
                  <span className={`etiqueta ${STATUS_INVENTARIO[i.status].classe}`}>{STATUS_INVENTARIO[i.status].texto}</span>
                </td>
                <td className="num">{i.produtos_ajustados ?? "-"}</td>
                <td className="num negativo-texto">{i.valor_falta ? reais(i.valor_falta) : "-"}</td>
                <td className="num">{i.valor_sobra ? reais(i.valor_sobra) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {lista?.length === 0 && <p className="lista-vazia">Nenhuma contagem ainda.</p>}
      </div>
    </div>
  );
}

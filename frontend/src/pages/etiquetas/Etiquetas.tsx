import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { EtiquetaItem, ListaEtiquetas, MotivoEtiqueta } from "../../api/tipos";
import Icone from "../../components/Icone";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";

export type Modelo = "pequena" | "codigo" | "oferta";

export const MODELOS: { valor: Modelo; nome: string; descricao: string }[] = [
  { valor: "pequena", nome: "Gôndola pequena", descricao: "4 por linha, para a beira da prateleira" },
  { valor: "codigo", nome: "Gôndola com código de barras", descricao: "3 por linha, com o código para conferir" },
  { valor: "oferta", nome: "Cartaz de oferta", descricao: "2 por folha na horizontal, para promoções" },
];

export const CHAVE_IMPRESSAO = "ff.etiquetas-impressao";

export interface Impressao {
  lojaId: string;
  modelo: Modelo;
  itens: (EtiquetaItem & { copias: number })[];
}

const MOTIVOS: Record<MotivoEtiqueta, { texto: string; classe: string }> = {
  nunca_impressa: { texto: "Nunca impressa", classe: "" },
  preco_subiu: { texto: "Preço subiu", classe: "erro-etiqueta" },
  preco_baixou: { texto: "Preço baixou", classe: "erro-etiqueta" },
  promocao_comecou: { texto: "Entrou em promoção", classe: "ok" },
  promocao_acabou: { texto: "Promoção acabou", classe: "erro-etiqueta" },
  promocao_mudou: { texto: "Promoção mudou", classe: "ok" },
};

function precoNaEtiqueta(preco: string, promocional: string | null, promocao: string | null) {
  if (promocional) {
    return (
      <>
        <s>{reais(preco)}</s> <strong>{reais(promocional)}</strong>
      </>
    );
  }
  return (
    <>
      <strong>{reais(preco)}</strong>
      {promocao && <span className="livro-detalhe">{promocao}</span>}
    </>
  );
}

/** Etiquetas de gôndola: o que imprimir e o que trocar quando o preço ou a promoção muda. */
export default function Etiquetas() {
  const lojas = useLojas();
  const [lojaId, setLojaId] = useState("");
  const [situacao, setSituacao] = useState<"trocar" | "todas">("trocar");
  const [busca, setBusca] = useState("");
  const [semEstoque, setSemEstoque] = useState(false);
  const [lista, setLista] = useState<ListaEtiquetas | null>(null);
  const [marcados, setMarcados] = useState<Record<string, number>>({});
  const [modelo, setModelo] = useState<Modelo>("pequena");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  function carregar(termo = busca) {
    const params = new URLSearchParams({ situacao, so_com_estoque: String(!semEstoque) });
    if (lojaId) params.set("loja_id", lojaId);
    if (termo.trim()) params.set("busca", termo.trim());
    api<ListaEtiquetas>(`/etiquetas?${params}`)
      .then((dados) => {
        setLista(dados);
        // Na lista do que trocar, já vem tudo marcado.
        setMarcados(situacao === "trocar" ? Object.fromEntries(dados.itens.map((i) => [i.produto_id, 1])) : {});
      })
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => carregar(), [lojaId, situacao, semEstoque]);

  // Volta da tela de impressão: recarrega para tirar o que já foi trocado.
  useEffect(() => {
    const ao = () => document.visibilityState === "visible" && carregar();
    document.addEventListener("visibilitychange", ao);
    return () => document.removeEventListener("visibilitychange", ao);
  });

  const escolhidos = lista?.itens.filter((i) => marcados[i.produto_id]) ?? [];
  const totalEtiquetas = escolhidos.reduce((soma, i) => soma + (marcados[i.produto_id] ?? 0), 0);
  const todosMarcados = !!lista && lista.itens.length > 0 && escolhidos.length === lista.itens.length;

  function alternar(item: EtiquetaItem) {
    setMarcados((atual) => {
      const novo = { ...atual };
      if (novo[item.produto_id]) delete novo[item.produto_id];
      else novo[item.produto_id] = 1;
      return novo;
    });
  }

  function imprimir() {
    if (!lista || escolhidos.length === 0) return;
    const impressao: Impressao = {
      lojaId: lista.loja_id,
      modelo,
      itens: escolhidos.map((i) => ({ ...i, copias: marcados[i.produto_id] })),
    };
    sessionStorage.setItem(CHAVE_IMPRESSAO, JSON.stringify(impressao));
    window.open("/etiquetas/imprimir", "_blank");
  }

  async function marcarTrocadas() {
    if (!lista || escolhidos.length === 0) return;
    try {
      await api("/etiquetas/impressas", { corpo: { loja_id: lista.loja_id, produto_ids: escolhidos.map((i) => i.produto_id) } });
      setAviso({ tipo: "ok", texto: `${escolhidos.length} etiqueta(s) marcadas como trocadas.` });
      carregar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Loja</p>
          <h1>Etiquetas de preço</h1>
          <p className="vazio">
            Quando um preço muda ou uma promoção começa ou acaba, a etiqueta da gôndola aparece aqui para trocar.
            Preço na gôndola diferente do caixa dá problema com o Procon.
          </p>
        </div>
        {lojas.length > 1 && (
          <label className="seletor-loja">
            Loja
            <select value={lojaId} onChange={(e) => setLojaId(e.target.value)}>
              {lojas.map((l) => (
                <option key={l.id} value={l.matriz ? "" : l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {lista && (
        <div className="indicadores indicadores-financeiro">
          <button type="button" className="cartao indicador" onClick={() => setSituacao("trocar")}>
            <small>Etiquetas para trocar</small>
            <strong>{lista.para_trocar}</strong>
            <span>{lista.para_trocar ? "imprima e troque na gôndola" : "tudo certo na gôndola"}</span>
          </button>
          <div className="cartao indicador">
            <small>Preço mudou</small>
            <strong>{lista.preco_mudou}</strong>
            <span>etiqueta com preço antigo</span>
          </div>
          <div className="cartao indicador">
            <small>Promoção</small>
            <strong>{lista.promocao}</strong>
            <span>começou, mudou ou acabou</span>
          </div>
          <div className="cartao indicador">
            <small>Nunca impressas</small>
            <strong>{lista.nunca_impressas}</strong>
            <span>produtos com estoque sem etiqueta</span>
          </div>
        </div>
      )}

      <nav className="abas abas-botoes">
        <button type="button" className={situacao === "trocar" ? "active" : ""} onClick={() => setSituacao("trocar")}>
          Para trocar
        </button>
        <button type="button" className={situacao === "todas" ? "active" : ""} onClick={() => setSituacao("todas")}>
          Todos os produtos
        </button>
      </nav>

      <form
        className="barra filtros-relatorio"
        onSubmit={(e) => {
          e.preventDefault();
          carregar();
        }}
      >
        <input placeholder="Buscar por nome ou código de barras" value={busca} onChange={(e) => setBusca(e.target.value)} />
        <button type="submit" className="botao-pequeno">
          Buscar
        </button>
        <label className="checkbox">
          <input type="checkbox" checked={semEstoque} onChange={(e) => setSemEstoque(e.target.checked)} />
          Incluir produtos sem estoque
        </label>
      </form>

      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}

      <div className="cartao cartao-separado etiquetas-acoes">
        <label className="seletor-loja">
          Modelo
          <select value={modelo} onChange={(e) => setModelo(e.target.value as Modelo)}>
            {MODELOS.map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.nome}
              </option>
            ))}
          </select>
        </label>
        <small className="vazio">{MODELOS.find((m) => m.valor === modelo)?.descricao}</small>
        <span className="espaco" />
        <button type="button" className="botao" disabled={totalEtiquetas === 0} onClick={imprimir}>
          <Icone nome="etiqueta" />
          Imprimir {totalEtiquetas} etiqueta(s)
        </button>
        <button type="button" className="botao-pequeno" disabled={escolhidos.length === 0} onClick={marcarTrocadas}>
          Já troquei, marcar como trocadas
        </button>
      </div>

      {lista && (
        <div className="cartao cartao-separado">
          <table className="tabela">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Marcar todos"
                    checked={todosMarcados}
                    onChange={() =>
                      setMarcados(todosMarcados ? {} : Object.fromEntries(lista.itens.map((i) => [i.produto_id, marcados[i.produto_id] || 1])))
                    }
                  />
                </th>
                <th>Produto</th>
                <th className="num">Na gôndola</th>
                <th className="num">Agora</th>
                <th>Por quê</th>
                <th className="num">Cópias</th>
              </tr>
            </thead>
            <tbody>
              {lista.itens.map((i) => (
                <tr key={i.produto_id} className={marcados[i.produto_id] ? "" : "inativo"}>
                  <td>
                    <input type="checkbox" checked={!!marcados[i.produto_id]} onChange={() => alternar(i)} />
                  </td>
                  <td onClick={() => alternar(i)}>
                    {i.nome} {i.apresentacao && <small className="vazio">{i.apresentacao}</small>}
                    <span className="livro-detalhe">
                      {i.ean ?? "sem código"} · estoque {Number(i.saldo).toLocaleString("pt-BR")}
                    </span>
                  </td>
                  <td className="num">
                    {i.impressa ? (
                      <>
                        {precoNaEtiqueta(i.impressa.preco, i.impressa.preco_promocional, i.impressa.promocao)}
                        <span className="livro-detalhe">impressa em {data(i.impressa.impressa_em)}</span>
                      </>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="num">
                    {precoNaEtiqueta(i.preco, i.preco_promocional, i.preco_promocional ? null : i.promocao)}
                    {i.preco_promocional && i.promocao && <span className="livro-detalhe">{i.promocao}</span>}
                    {i.promocao_fim && <span className="livro-detalhe">até {data(i.promocao_fim)}</span>}
                  </td>
                  <td>{i.motivo ? <span className={`etiqueta ${MOTIVOS[i.motivo].classe}`}>{MOTIVOS[i.motivo].texto}</span> : <span className="vazio">Certa</span>}</td>
                  <td className="num">
                    <input
                      className="campo-copias"
                      type="number"
                      min={0}
                      max={50}
                      value={marcados[i.produto_id] ?? 0}
                      onChange={(e) => {
                        const copias = Math.max(0, Math.min(50, Number(e.target.value) || 0));
                        setMarcados((atual) => {
                          const novo = { ...atual };
                          if (copias) novo[i.produto_id] = copias;
                          else delete novo[i.produto_id];
                          return novo;
                        });
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {lista.itens.length === 0 && (
            <p className="lista-vazia">
              {situacao === "trocar"
                ? "Nenhuma etiqueta para trocar. Todas as gôndolas estão com o preço certo."
                : "Nenhum produto encontrado."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

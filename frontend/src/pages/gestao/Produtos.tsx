import { useEffect, useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { PaginaProdutos, Produto } from "../../api/tipos";
import { reais } from "../../formato";
import { ehGerente, useSessao } from "../../sessao";

type Formulario = {
  ean: string;
  nome: string;
  apresentacao: string;
  fabricante: string;
  preco_venda: string;
  estoque_minimo: string;
  tipo: Produto["tipo"];
  controla_lote: boolean;
  ncm: string;
  registro_ms: string;
};

const VAZIO: Formulario = {
  ean: "",
  nome: "",
  apresentacao: "",
  fabricante: "",
  preco_venda: "",
  estoque_minimo: "0",
  tipo: "medicamento",
  controla_lote: true,
  ncm: "",
  registro_ms: "",
};

function paraFormulario(p: Produto): Formulario {
  return {
    ean: p.ean ?? "",
    nome: p.nome,
    apresentacao: p.apresentacao ?? "",
    fabricante: p.fabricante ?? "",
    preco_venda: p.preco_venda,
    estoque_minimo: p.estoque_minimo,
    tipo: p.tipo,
    controla_lote: p.controla_lote,
    ncm: p.ncm ?? "",
    registro_ms: p.registro_ms ?? "",
  };
}

/** Campos de texto vazios viram null; preço aceita vírgula. */
function paraApi(f: Formulario) {
  const ouNulo = (valor: string) => valor.trim() || null;
  return {
    ean: ouNulo(f.ean),
    nome: f.nome.trim(),
    apresentacao: ouNulo(f.apresentacao),
    fabricante: ouNulo(f.fabricante),
    preco_venda: f.preco_venda.replace(",", "."),
    estoque_minimo: f.estoque_minimo.replace(",", ".") || "0",
    tipo: f.tipo,
    controla_lote: f.controla_lote,
    ncm: ouNulo(f.ncm),
    registro_ms: ouNulo(f.registro_ms),
  };
}

export default function Produtos() {
  const { sessao } = useSessao();
  const podeEditar = ehGerente(sessao);
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState<PaginaProdutos | null>(null);
  const [editando, setEditando] = useState<Produto | "novo" | null>(null);
  const [form, setForm] = useState<Formulario>(VAZIO);
  const [erro, setErro] = useState("");

  async function carregar(termo = busca) {
    try {
      setPagina(await api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(termo)}&por_pagina=50`));
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  useEffect(() => {
    carregar("");
  }, []);

  function abrir(produto: Produto | "novo") {
    setEditando(produto);
    setForm(produto === "novo" ? VAZIO : paraFormulario(produto));
    setErro("");
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    try {
      if (editando === "novo") await api("/produtos", { corpo: paraApi(form) });
      else if (editando) await api(`/produtos/${editando.id}`, { metodo: "PATCH", corpo: paraApi(form) });
      setEditando(null);
      carregar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  function campo<K extends keyof Formulario>(nome: K, valor: Formulario[K]) {
    setForm((atual) => ({ ...atual, [nome]: valor }));
  }

  return (
    <div className="pagina">
      <h1>Produtos</h1>
      <form
        className="barra"
        onSubmit={(e) => {
          e.preventDefault();
          carregar();
        }}
      >
        <input placeholder="Buscar por nome ou código de barras" value={busca} onChange={(e) => setBusca(e.target.value)} />
        <button type="submit">Buscar</button>
        {podeEditar && (
          <button type="button" onClick={() => abrir("novo")}>
            Novo produto
          </button>
        )}
      </form>

      {editando && (
        <form className="cartao formulario" onSubmit={salvar}>
          <h2>{editando === "novo" ? "Novo produto" : `Editar ${editando.nome}`}</h2>
          <label>
            Código de barras (EAN)
            <input value={form.ean} onChange={(e) => campo("ean", e.target.value)} inputMode="numeric" />
          </label>
          <label>
            Nome *
            <input value={form.nome} onChange={(e) => campo("nome", e.target.value)} required autoFocus />
          </label>
          <label>
            Apresentação
            <input value={form.apresentacao} onChange={(e) => campo("apresentacao", e.target.value)} placeholder="ex.: 20 comprimidos" />
          </label>
          <label>
            Fabricante
            <input value={form.fabricante} onChange={(e) => campo("fabricante", e.target.value)} />
          </label>
          <label>
            Preço de venda (R$) *
            <input value={form.preco_venda} onChange={(e) => campo("preco_venda", e.target.value)} required />
          </label>
          <label>
            Estoque mínimo
            <input value={form.estoque_minimo} onChange={(e) => campo("estoque_minimo", e.target.value)} />
          </label>
          <label>
            Tipo
            <select value={form.tipo} onChange={(e) => campo("tipo", e.target.value as Produto["tipo"])}>
              <option value="medicamento">Medicamento</option>
              <option value="perfumaria">Perfumaria</option>
              <option value="outros">Outros</option>
            </select>
          </label>
          <label>
            NCM
            <input value={form.ncm} onChange={(e) => campo("ncm", e.target.value)} inputMode="numeric" />
          </label>
          <label>
            Registro MS
            <input value={form.registro_ms} onChange={(e) => campo("registro_ms", e.target.value)} />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={form.controla_lote} onChange={(e) => campo("controla_lote", e.target.checked)} />
            Controla lote e validade
          </label>
          {erro && <p className="erro">{erro}</p>}
          <div className="acoes">
            <button type="submit">Salvar</button>
            <button type="button" onClick={() => setEditando(null)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {!editando && erro && <p className="erro">{erro}</p>}

      <table className="tabela">
        <thead>
          <tr>
            <th>EAN</th>
            <th>Produto</th>
            <th>Tipo</th>
            <th className="num">Preço</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {pagina?.itens.map((p) => (
            <tr key={p.id}>
              <td>{p.ean ?? "-"}</td>
              <td>
                {p.nome} {p.apresentacao && <small>{p.apresentacao}</small>}
              </td>
              <td>{p.tipo}</td>
              <td className="num">{reais(p.preco_venda)}</td>
              <td>{podeEditar && <button onClick={() => abrir(p)}>Editar</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {pagina && <p className="rodape">{pagina.total} produto(s)</p>}
    </div>
  );
}

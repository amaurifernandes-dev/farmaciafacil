import { useEffect, useState, type FormEvent } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ListaControle, PaginaProdutos, Produto } from "../../api/tipos";
import { reais } from "../../formato";
import { cuidaDoEstoque, useSessao } from "../../sessao";

type Formulario = {
  ean: string;
  nome: string;
  apresentacao: string;
  fabricante: string;
  preco_venda: string;
  estoque_minimo: string;
  tipo: Produto["tipo"];
  controla_lote: boolean;
  vende_online: boolean;
  ncm: string;
  cest: string;
  cfop: string;
  icms_situacao_tributaria: string;
  registro_ms: string;
  controle: ListaControle | "";
  embalagem_sngpc: Produto["embalagem_sngpc"];
};

/** As listas da Portaria 344/98 que a farmácia vende, e o antibiótico (RDC 20/2011). */
export const LISTAS_CONTROLE: { valor: ListaControle; nome: string }[] = [
  { valor: "ATB", nome: "Antibiótico (receita em 2 vias, vale 10 dias)" },
  { valor: "C1", nome: "C1 - Controle especial (receita em 2 vias)" },
  { valor: "C2", nome: "C2 - Retinoides (notificação especial)" },
  { valor: "C4", nome: "C4 - Antirretrovirais" },
  { valor: "C5", nome: "C5 - Anabolizantes" },
  { valor: "B1", nome: "B1 - Psicotrópicos (notificação azul)" },
  { valor: "B2", nome: "B2 - Anorexígenos (notificação azul)" },
  { valor: "A1", nome: "A1 - Entorpecentes (notificação amarela)" },
  { valor: "A2", nome: "A2 - Entorpecentes (notificação amarela)" },
  { valor: "A3", nome: "A3 - Psicotrópicos (notificação amarela)" },
];

const VAZIO: Formulario = {
  ean: "",
  nome: "",
  apresentacao: "",
  fabricante: "",
  preco_venda: "",
  estoque_minimo: "0",
  tipo: "medicamento",
  controla_lote: true,
  vende_online: false,
  ncm: "",
  cest: "",
  cfop: "",
  icms_situacao_tributaria: "",
  registro_ms: "",
  controle: "",
  embalagem_sngpc: "caixa",
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
    vende_online: p.vende_online,
    ncm: p.ncm ?? "",
    cest: p.cest ?? "",
    cfop: p.cfop ?? "",
    icms_situacao_tributaria: p.icms_situacao_tributaria ?? "",
    registro_ms: p.registro_ms ?? "",
    controle: p.controle ?? "",
    embalagem_sngpc: p.embalagem_sngpc,
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
    vende_online: f.vende_online,
    ncm: ouNulo(f.ncm),
    cest: ouNulo(f.cest),
    cfop: ouNulo(f.cfop),
    icms_situacao_tributaria: ouNulo(f.icms_situacao_tributaria),
    registro_ms: ouNulo(f.registro_ms),
    controle: f.controle || null,
    embalagem_sngpc: f.embalagem_sngpc,
  };
}

export default function Produtos() {
  const { sessao } = useSessao();
  const podeEditar = cuidaDoEstoque(sessao);
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
      <p className="sobretitulo">Cadastros</p>
      <h1>Produtos</h1>
      <p className="vazio">Preços, códigos de barras e dados fiscais dos produtos.</p>
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
            <select
              value={form.tipo}
              onChange={(e) => {
                const tipo = e.target.value as Produto["tipo"];
                // Remédio não vai para a loja online sem a farmácia marcar.
                setForm((f) => ({ ...f, tipo, vende_online: tipo !== "medicamento" }));
              }}
            >
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
            CEST
            <input value={form.cest} onChange={(e) => campo("cest", e.target.value)} inputMode="numeric" />
          </label>
          <label>
            CFOP <small>(vazio usa o padrão fiscal)</small>
            <input value={form.cfop} onChange={(e) => campo("cfop", e.target.value)} inputMode="numeric" />
          </label>
          <label>
            CSOSN / CST ICMS <small>(vazio usa o padrão fiscal)</small>
            <input
              value={form.icms_situacao_tributaria}
              onChange={(e) => campo("icms_situacao_tributaria", e.target.value)}
              inputMode="numeric"
            />
          </label>
          <label>
            Remédio controlado
            <select
              value={form.controle}
              onChange={(e) => {
                const controle = e.target.value as Formulario["controle"];
                // Controlado só sai no balcão, com a receita.
                setForm((f) => ({ ...f, controle, vende_online: controle ? false : f.vende_online }));
              }}
            >
              <option value="">Não é controlado</option>
              {LISTAS_CONTROLE.map((l) => (
                <option key={l.valor} value={l.valor}>
                  {l.nome}
                </option>
              ))}
            </select>
          </label>
          <label>
            Registro MS {form.controle && <small>(13 números, vai para o SNGPC)</small>}
            <input
              value={form.registro_ms}
              onChange={(e) => campo("registro_ms", e.target.value)}
              inputMode="numeric"
              required={!!form.controle}
            />
          </label>
          {form.controle && (
            <label>
              A Anvisa conta em
              <select
                value={form.embalagem_sngpc}
                onChange={(e) => campo("embalagem_sngpc", e.target.value as Formulario["embalagem_sngpc"])}
              >
                <option value="caixa">Caixas</option>
                <option value="frasco">Frascos</option>
              </select>
            </label>
          )}
          <label className="checkbox">
            <input type="checkbox" checked={form.controla_lote} onChange={(e) => campo("controla_lote", e.target.checked)} />
            Controla lote e validade
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.vende_online}
              disabled={!!form.controle}
              onChange={(e) => campo("vende_online", e.target.checked)}
            />
            Aparece na loja online <small>(remédio só se não precisar de receita)</small>
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
              <td>
                {p.tipo}
                {p.controle && <span className="selo selo-controle">{p.controle === "ATB" ? "Antibiótico" : p.controle}</span>}
              </td>
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

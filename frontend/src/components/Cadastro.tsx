import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { api, mensagem } from "../api/cliente";
import Icone from "./Icone";

// Tela de cadastro genérica: lista com busca e um formulário em janela.
// Cada cadastro só descreve os campos e as colunas.

export interface Campo {
  nome: string;
  rotulo: string;
  tipo?: "texto" | "email" | "data" | "senha" | "check" | "select" | "area";
  opcoes?: { valor: string; rotulo: string }[];
  obrigatorio?: boolean;
  /** Ocupa a linha inteira do formulário. */
  largo?: boolean;
  dica?: string;
  inputMode?: "numeric" | "tel" | "email";
  /** Só aparece ao criar (ex.: senha inicial). */
  soNoNovo?: boolean;
  /** Só aparece ao editar (ex.: ativo). */
  soNaEdicao?: boolean;
  /** Campo vazio na edição não é enviado (ex.: nova senha). */
  ignorarVazio?: boolean;
}

export interface Coluna<T> {
  titulo: string;
  valor: (registro: T) => ReactNode;
  classe?: string;
}

type Valores = Record<string, string | boolean>;

interface Props<T extends { id: string; ativo: boolean }> {
  titulo: string;
  descricao: string;
  /** Ex.: "/clientes". A lista pode vir paginada ({itens}) ou como array. */
  endpoint: string;
  rotuloNovo: string;
  campos: Campo[];
  colunas: Coluna<T>[];
  podeEditar: boolean;
  buscaPlaceholder?: string;
  semBusca?: boolean;
  aviso?: ReactNode;
  rodape?: ReactNode;
}

function valoresIniciais(campos: Campo[], registro?: Record<string, unknown>): Valores {
  return Object.fromEntries(
    campos.map((c) => {
      const atual = registro?.[c.nome];
      if (c.tipo === "check") return [c.nome, Boolean(atual ?? (c.nome === "ativo" ? true : false))];
      if (c.tipo === "select") return [c.nome, String(atual ?? c.opcoes?.[0]?.valor ?? "")];
      return [c.nome, atual == null ? "" : String(atual)];
    }),
  );
}

export default function Cadastro<T extends { id: string; ativo: boolean }>(props: Props<T>) {
  const { titulo, descricao, endpoint, rotuloNovo, campos, colunas, podeEditar } = props;
  const [busca, setBusca] = useState("");
  const [inativos, setInativos] = useState(false);
  const [registros, setRegistros] = useState<T[] | null>(null);
  const [editando, setEditando] = useState<T | "novo" | null>(null);
  const [erro, setErro] = useState("");

  async function carregar(termo = busca, comInativos = inativos) {
    try {
      const parametros = new URLSearchParams({ busca: termo, incluir_inativos: String(comInativos), por_pagina: "100" });
      const resposta = await api<T[] | { itens: T[] }>(`${endpoint}?${parametros}`);
      setRegistros(Array.isArray(resposta) ? resposta : resposta.itens);
      setErro("");
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  useEffect(() => {
    carregar("", false);
  }, [endpoint]);

  const visiveis = (registros ?? []).filter((r) => props.semBusca || inativos || r.ativo);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Cadastros</p>
          <h1>{titulo}</h1>
          <p className="vazio">{descricao}</p>
        </div>
        {podeEditar && (
          <button type="button" className="botao" onClick={() => setEditando("novo")}>
            <Icone nome="mais" /> {rotuloNovo}
          </button>
        )}
      </div>

      {props.aviso}

      <div className="cartao">
        {!props.semBusca && (
          <form
            className="barra"
            onSubmit={(e) => {
              e.preventDefault();
              carregar();
            }}
          >
            <input
              placeholder={props.buscaPlaceholder ?? "Buscar por nome ou documento"}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <button type="submit">Buscar</button>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={inativos}
                onChange={(e) => {
                  setInativos(e.target.checked);
                  carregar(busca, e.target.checked);
                }}
              />
              Mostrar inativos
            </label>
          </form>
        )}
        {erro && !editando && <p className="erro">{erro}</p>}
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                {colunas.map((c) => (
                  <th key={c.titulo} className={c.classe}>
                    {c.titulo}
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((r) => (
                <tr key={r.id} className={r.ativo ? "" : "inativo"}>
                  {colunas.map((c) => (
                    <td key={c.titulo} className={c.classe}>
                      {c.valor(r)}
                    </td>
                  ))}
                  <td className="num">
                    {podeEditar && (
                      <button type="button" className="botao-pequeno" onClick={() => setEditando(r)}>
                        Editar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {registros && visiveis.length === 0 && (
          <p className="lista-vazia">Nenhum cadastro encontrado. Comece adicionando o primeiro.</p>
        )}
        {registros && visiveis.length > 0 && <p className="rodape">{visiveis.length} registro(s)</p>}
      </div>

      {props.rodape}

      {editando && (
        <FormularioCadastro
          titulo={editando === "novo" ? rotuloNovo : `Editar ${titulo.toLowerCase()}`}
          campos={campos.filter((c) => (editando === "novo" ? !c.soNaEdicao : !c.soNoNovo))}
          registro={editando === "novo" ? undefined : (editando as unknown as Record<string, unknown>)}
          aoFechar={() => setEditando(null)}
          aoSalvar={async (valores) => {
            if (editando === "novo") await api(endpoint, { corpo: valores });
            else await api(`${endpoint}/${editando.id}`, { metodo: "PATCH", corpo: valores });
            setEditando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}

interface PropsFormulario {
  titulo: string;
  campos: Campo[];
  registro?: Record<string, unknown>;
  aoFechar: () => void;
  aoSalvar: (valores: Record<string, unknown>) => Promise<void>;
  observacao?: ReactNode;
}

export function FormularioCadastro({ titulo, campos, registro, aoFechar, aoSalvar, observacao }: PropsFormulario) {
  const [valores, setValores] = useState<Valores>(() => valoresIniciais(campos, registro));
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    setErro("");
    // Texto vazio vai como null, para limpar o campo no servidor.
    const corpo: Record<string, unknown> = {};
    for (const campo of campos) {
      const valor = valores[campo.nome];
      if (campo.ignorarVazio && valor === "") continue;
      corpo[campo.nome] = typeof valor === "string" ? valor.trim() || null : valor;
    }
    try {
      await aoSalvar(corpo);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Janela titulo={titulo} aoFechar={aoFechar}>
      <form className="campos" onSubmit={salvar}>
        {campos.map((campo) => (
          <CampoFormulario
            key={campo.nome}
            campo={campo}
            valor={valores[campo.nome]}
            mudar={(v) => setValores((atual) => ({ ...atual, [campo.nome]: v }))}
          />
        ))}
        {observacao && <div className="largo vazio">{observacao}</div>}
        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit" disabled={salvando}>
            {salvando ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </form>
    </Janela>
  );
}

function CampoFormulario({ campo, valor, mudar }: { campo: Campo; valor: string | boolean; mudar: (v: string | boolean) => void }) {
  const classe = campo.largo || campo.tipo === "area" ? "largo" : "";
  if (campo.tipo === "check") {
    return (
      <label className={`checkbox caixa-marcacao ${classe}`}>
        <input type="checkbox" checked={Boolean(valor)} onChange={(e) => mudar(e.target.checked)} />
        <span>
          {campo.rotulo}
          {campo.dica && <small>{campo.dica}</small>}
        </span>
      </label>
    );
  }
  const rotulo = `${campo.rotulo}${campo.obrigatorio ? " *" : ""}`;
  return (
    <label className={classe}>
      {rotulo}
      {campo.tipo === "select" ? (
        <select value={String(valor)} onChange={(e) => mudar(e.target.value)}>
          {campo.opcoes?.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </select>
      ) : campo.tipo === "area" ? (
        <textarea value={String(valor)} onChange={(e) => mudar(e.target.value)} rows={3} />
      ) : (
        <input
          type={{ email: "email", data: "date", senha: "password" }[campo.tipo as string] ?? "text"}
          value={String(valor)}
          onChange={(e) => mudar(e.target.value)}
          required={campo.obrigatorio}
          inputMode={campo.inputMode}
          autoComplete={campo.tipo === "senha" ? "new-password" : "off"}
        />
      )}
      {campo.dica && <small>{campo.dica}</small>}
    </label>
  );
}

/** Janela modal com <dialog>, que já cuida do Esc e do foco. */
export function Janela({ titulo, aoFechar, children }: { titulo: string; aoFechar: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialogo = ref.current;
    dialogo?.showModal();
    return () => dialogo?.close();
  }, []);
  return (
    <dialog ref={ref} className="janela" onCancel={aoFechar}>
      <div className="cartao-cabecalho">
        <h2>{titulo}</h2>
        <button type="button" className="botao-icone" onClick={aoFechar} title="Fechar">
          <Icone nome="x" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

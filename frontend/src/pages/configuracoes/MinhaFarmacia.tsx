import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Loja } from "../../api/tipos";
import { FormularioCadastro, type Campo } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import { ehAdmin, useSessao } from "../../sessao";
import { CAMPOS_ENDERECO, documento, telefone } from "./campos";

const CAMPOS: Campo[] = [
  { nome: "nome", rotulo: "Nome da loja no sistema", obrigatorio: true, dica: "Ex.: Matriz, Filial Centro" },
  { nome: "nome_fantasia", rotulo: "Nome fantasia", obrigatorio: true },
  { nome: "razao_social", rotulo: "Razão social", obrigatorio: true, largo: true },
  { nome: "cnpj", rotulo: "CNPJ", obrigatorio: true, inputMode: "numeric" },
  { nome: "inscricao_estadual", rotulo: "Inscrição estadual" },
  { nome: "telefone", rotulo: "Telefone", inputMode: "tel" },
  { nome: "email", rotulo: "E-mail", tipo: "email" },
  ...CAMPOS_ENDERECO.map((c) => (c.nome === "uf" ? { ...c, obrigatorio: true } : c)),
  {
    nome: "codigo_municipio",
    rotulo: "Código do município (IBGE)",
    inputMode: "numeric",
    dica: "7 números. O contador sabe; vai no SPED Fiscal",
  },
  { nome: "responsavel_tecnico", rotulo: "Farmacêutico responsável" },
  { nome: "crf", rotulo: "CRF / UF" },
  {
    nome: "responsavel_cpf",
    rotulo: "CPF do farmacêutico",
    inputMode: "numeric",
    dica: "Vai no arquivo do SNGPC como quem transmite",
  },
];

export default function MinhaFarmacia() {
  const { sessao } = useSessao();
  const podeEditar = ehAdmin(sessao);
  const [lojas, setLojas] = useState<Loja[] | null>(null);
  const [editando, setEditando] = useState<Loja | "nova" | null>(null);
  const [erro, setErro] = useState("");

  function carregar() {
    api<Loja[]>("/lojas")
      .then(setLojas)
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(carregar, []);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Configurações</p>
          <h1>Minha farmácia</h1>
          <p className="vazio">Dados da farmácia e das lojas. Cada loja tem o seu CNPJ e os seus caixas.</p>
        </div>
        {podeEditar && (
          <button type="button" className="botao" onClick={() => setEditando("nova")}>
            <Icone nome="mais" /> Cadastrar outra loja
          </button>
        )}
      </div>
      {erro && <p className="erro">{erro}</p>}

      <div className="lojas">
        {lojas?.map((loja) => (
          <section key={loja.id} className={`cartao loja ${loja.ativo ? "" : "inativo"}`}>
            <div className="cartao-cabecalho">
              <div>
                <span className="etiqueta">{loja.matriz ? "Matriz" : "Filial"}</span>
                <h2>{loja.nome}</h2>
              </div>
              {podeEditar && (
                <button type="button" className="botao-pequeno" onClick={() => setEditando(loja)}>
                  <Icone nome="lapis" tamanho={14} /> Editar
                </button>
              )}
            </div>
            <dl className="dados">
              <dt>Nome fantasia</dt>
              <dd>{loja.nome_fantasia}</dd>
              <dt>Razão social</dt>
              <dd>{loja.razao_social}</dd>
              <dt>CNPJ</dt>
              <dd>{documento(loja.cnpj)}</dd>
              <dt>Inscrição estadual</dt>
              <dd>{loja.inscricao_estadual ?? "-"}</dd>
              <dt>Endereço</dt>
              <dd>
                {[loja.endereco, loja.bairro, loja.cidade].filter(Boolean).join(", ") || "-"} / {loja.uf}
              </dd>
              <dt>Telefone</dt>
              <dd>{telefone(loja.telefone)}</dd>
              <dt>Responsável técnico</dt>
              <dd>{loja.responsavel_tecnico ? `${loja.responsavel_tecnico} (${loja.crf ?? "CRF não informado"})` : "-"}</dd>
              <dt>Caixa</dt>
              <dd>{loja.modo_caixa === "mono" ? "Monocaixa" : "Multicaixa"}</dd>
            </dl>
            {!loja.ativo && <p className="vazio">Loja desativada</p>}
          </section>
        ))}
      </div>
      <p className="nota">
        Por enquanto o estoque é um só para todas as lojas. Os caixas, os PDVs e as vendas já ficam separados por loja.
      </p>

      {editando && (
        <FormularioCadastro
          titulo={editando === "nova" ? "Cadastrar outra loja" : `Editar ${editando.nome}`}
          campos={
            editando === "nova" || editando.matriz
              ? CAMPOS
              : [...CAMPOS, { nome: "ativo", rotulo: "Loja ativa", tipo: "check" }]
          }
          registro={editando === "nova" ? { nome: `Filial ${lojas?.length ?? ""}`.trim() } : (editando as unknown as Record<string, unknown>)}
          observacao={
            editando !== "nova" && editando.matriz
              ? "Os dados da matriz também são o nome da farmácia no sistema."
              : "A filial tem o próprio CNPJ, os próprios PDVs e emite as próprias notas."
          }
          aoFechar={() => setEditando(null)}
          aoSalvar={async (valores) => {
            if (editando === "nova") await api("/lojas", { corpo: valores });
            else await api(`/lojas/${editando.id}`, { metodo: "PATCH", corpo: valores });
            setEditando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}

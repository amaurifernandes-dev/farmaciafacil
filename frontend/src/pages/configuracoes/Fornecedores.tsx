import Cadastro, { type Campo } from "../../components/Cadastro";
import { cuidaDoEstoque, useSessao } from "../../sessao";
import { CAMPOS_ENDERECO, documento, telefone } from "./campos";

interface Fornecedor {
  id: string;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string | null;
  contato: string | null;
  telefone: string | null;
  ativo: boolean;
}

const CAMPOS: Campo[] = [
  { nome: "razao_social", rotulo: "Razão social", obrigatorio: true },
  { nome: "nome_fantasia", rotulo: "Nome fantasia" },
  { nome: "cnpj", rotulo: "CNPJ", inputMode: "numeric" },
  { nome: "inscricao_estadual", rotulo: "Inscrição estadual" },
  { nome: "contato", rotulo: "Nome do contato" },
  { nome: "telefone", rotulo: "Telefone", inputMode: "tel" },
  { nome: "email", rotulo: "E-mail", tipo: "email", largo: true },
  ...CAMPOS_ENDERECO,
  { nome: "observacoes", rotulo: "Observações", tipo: "area" },
  { nome: "ativo", rotulo: "Fornecedor ativo", tipo: "check", soNaEdicao: true },
];

export default function Fornecedores() {
  const { sessao } = useSessao();
  return (
    <Cadastro<Fornecedor>
      titulo="Fornecedores"
      descricao="Distribuidoras e laboratórios de quem a farmácia compra."
      endpoint="/fornecedores"
      rotuloNovo="Novo fornecedor"
      campos={CAMPOS}
      podeEditar={cuidaDoEstoque(sessao)}
      buscaPlaceholder="Buscar por nome ou CNPJ"
      colunas={[
        {
          titulo: "Fornecedor",
          valor: (f) => (
            <>
              <strong>{f.nome_fantasia ?? f.razao_social}</strong>
              {f.nome_fantasia && <small> {f.razao_social}</small>}
            </>
          ),
        },
        { titulo: "CNPJ", valor: (f) => documento(f.cnpj) },
        { titulo: "Contato", valor: (f) => f.contato ?? "-" },
        { titulo: "Telefone", valor: (f) => telefone(f.telefone) },
      ]}
    />
  );
}

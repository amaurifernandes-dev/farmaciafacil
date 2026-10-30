import Cadastro, { type Campo } from "../../components/Cadastro";
import { reais } from "../../formato";
import { CAMPOS_ENDERECO, documento, telefone } from "./campos";

interface Cliente {
  id: string;
  nome: string;
  cpf: string | null;
  telefone: string | null;
  email: string | null;
  aceita_ofertas: boolean;
  limite_credito: string | null;
  ativo: boolean;
}

const CAMPOS: Campo[] = [
  { nome: "nome", rotulo: "Nome completo", obrigatorio: true, largo: true },
  { nome: "cpf", rotulo: "CPF (opcional)", inputMode: "numeric" },
  { nome: "data_nascimento", rotulo: "Data de nascimento", tipo: "data" },
  { nome: "telefone", rotulo: "Telefone / WhatsApp", inputMode: "tel" },
  { nome: "email", rotulo: "E-mail", tipo: "email" },
  ...CAMPOS_ENDERECO,
  {
    nome: "limite_credito",
    rotulo: "Limite para comprar a prazo (R$)",
    inputMode: "numeric",
    dica: "Deixe vazio se o cliente não compra fiado.",
  },
  { nome: "observacoes", rotulo: "Observações", tipo: "area" },
  {
    nome: "aceita_ofertas",
    rotulo: "Autoriza receber ofertas e descontos",
    tipo: "check",
    largo: true,
    dica: "Marque só se o cliente pediu. A data da autorização fica registrada (LGPD).",
  },
  { nome: "ativo", rotulo: "Cadastro ativo", tipo: "check", soNaEdicao: true },
];

export default function Clientes() {
  return (
    <Cadastro<Cliente>
      titulo="Clientes"
      descricao="O cadastro é opcional: só peça os dados que o cliente quiser informar."
      endpoint="/clientes"
      rotuloNovo="Novo cliente"
      campos={CAMPOS}
      podeEditar
      buscaPlaceholder="Buscar por nome, CPF ou telefone"
      colunas={[
        { titulo: "Nome", valor: (c) => <strong>{c.nome}</strong> },
        { titulo: "Telefone", valor: (c) => telefone(c.telefone) },
        { titulo: "CPF", valor: (c) => documento(c.cpf) },
        {
          titulo: "Fiado",
          valor: (c) => (Number(c.limite_credito) > 0 ? `até ${reais(c.limite_credito!)}` : "-"),
        },
        { titulo: "Ofertas", valor: (c) => (c.aceita_ofertas ? <span className="etiqueta ok">Autorizou</span> : "-") },
      ]}
    />
  );
}

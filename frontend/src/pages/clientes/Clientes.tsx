import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/cliente";
import type { Cliente, Convenio } from "../../api/tipos";
import Cadastro, { type Campo } from "../../components/Cadastro";
import { data } from "../../formato";
import { CAMPOS_ENDERECO, documento, telefone } from "../configuracoes/campos";

/** Empresas conveniadas ativas, para o cadastro do cliente. */
export function useConvenios(): Convenio[] {
  const [convenios, setConvenios] = useState<Convenio[]>([]);
  useEffect(() => {
    api<Convenio[]>("/convenios")
      .then(setConvenios)
      .catch(() => setConvenios([]));
  }, []);
  return convenios;
}

/** Os campos do cliente, com os do convênio quando a farmácia tem empresas conveniadas. */
export function camposCliente(convenios: Convenio[]): Campo[] {
  if (convenios.length === 0) return CAMPOS_CLIENTE;
  const indice = CAMPOS_CLIENTE.findIndex((c) => c.nome === "observacoes");
  const doConvenio: Campo[] = [
    {
      nome: "convenio_id",
      rotulo: "Convênio (empresa onde trabalha)",
      tipo: "select",
      opcoes: [{ valor: "", rotulo: "Não é de convênio" }, ...convenios.map((c) => ({ valor: c.id, rotulo: c.nome }))],
    },
    { nome: "convenio_matricula", rotulo: "Matrícula na empresa" },
    {
      nome: "convenio_limite",
      rotulo: "Limite no convênio (R$)",
      inputMode: "numeric",
      dica: "Vazio: usa o limite padrão da empresa.",
    },
  ];
  return [...CAMPOS_CLIENTE.slice(0, indice), ...doConvenio, ...CAMPOS_CLIENTE.slice(indice)];
}

export const CAMPOS_CLIENTE: Campo[] = [
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
  const convenios = useConvenios();
  const nomes = Object.fromEntries(convenios.map((c) => [c.id, c.nome]));
  return (
    <Cadastro<Cliente>
      titulo="Clientes"
      descricao="Quem compra com você, o que leva e quantos pontos tem. O cadastro é opcional: só peça o que o cliente quiser informar."
      endpoint="/clientes"
      rotuloNovo="Novo cliente"
      campos={camposCliente(convenios)}
      sobretitulo="Relacionamento"
      filtros={[
        { valor: "aniversariantes", rotulo: "Aniversariantes do mês" },
        { valor: "sumidos", rotulo: "Sem comprar há 60 dias" },
      ]}
      acoes={(c) => (
        <Link to={`/clientes/${c.id}`} className="botao-pequeno">
          Ver ficha
        </Link>
      )}
      podeEditar
      buscaPlaceholder="Buscar por nome, CPF ou telefone"
      colunas={[
        {
          titulo: "Nome",
          valor: (c) => (
            <Link to={`/clientes/${c.id}`} className="link-forte">
              {c.nome}
            </Link>
          ),
        },
        { titulo: "Telefone", valor: (c) => telefone(c.telefone) },
        { titulo: "CPF", valor: (c) => documento(c.cpf) },
        { titulo: "Aniversário", valor: (c) => (c.data_nascimento ? data(c.data_nascimento).slice(0, 5) : "-") },
        { titulo: "Última compra", valor: (c) => data(c.ultima_compra ?? null) },
        ...(convenios.length
          ? [{ titulo: "Convênio", valor: (c: Cliente) => (c.convenio_id ? nomes[c.convenio_id] ?? "-" : "-") }]
          : []),
        { titulo: "Pontos", valor: (c) => (c.pontos ? c.pontos.toLocaleString("pt-BR") : "-"), classe: "num" },
        { titulo: "Ofertas", valor: (c) => (c.aceita_ofertas ? <span className="etiqueta ok">Autorizou</span> : "-") },
      ]}
    />
  );
}

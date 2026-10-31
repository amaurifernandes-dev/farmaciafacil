import type { Papel } from "../../api/tipos";
import Cadastro, { type Campo } from "../../components/Cadastro";
import { NOMES_PAPEIS } from "../../sessao";

interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: Papel;
  ativo: boolean;
  recebe_comissao: boolean;
  crf: string | null;
}

const PERFIS: { papel: Papel; descricao: string }[] = [
  { papel: "admin", descricao: "tudo, inclusive usuários, lojas e configurações" },
  { papel: "gerente", descricao: "operação, caixas, PDVs, cancelamentos e descontos maiores" },
  { papel: "farmaceutico", descricao: "produtos, estoque, vendas e caixa" },
  { papel: "caixa", descricao: "abre o caixa, recebe e fecha" },
  { papel: "atendente", descricao: "monta pré-vendas e cadastra clientes" },
  { papel: "estoque", descricao: "produtos, fornecedores e entradas de estoque" },
];

const CAMPOS: Campo[] = [
  { nome: "nome", rotulo: "Nome completo", obrigatorio: true },
  { nome: "email", rotulo: "E-mail (login)", tipo: "email", obrigatorio: true },
  {
    nome: "papel",
    rotulo: "Perfil de acesso",
    tipo: "select",
    opcoes: PERFIS.map((p) => ({ valor: p.papel, rotulo: NOMES_PAPEIS[p.papel] })),
  },
  { nome: "senha", rotulo: "Senha inicial", tipo: "senha", obrigatorio: true, soNoNovo: true, dica: "Mínimo de 8 caracteres" },
  {
    nome: "senha",
    rotulo: "Nova senha",
    tipo: "senha",
    soNaEdicao: true,
    ignorarVazio: true,
    dica: "Deixe em branco para manter a atual",
  },
  { nome: "crf", rotulo: "CRF (só farmacêutico)", dica: "Ex.: SP 12345. Vai na declaração dos serviços farmacêuticos" },
  { nome: "recebe_comissao", rotulo: "Recebe comissão sobre o que vende", tipo: "check" },
  { nome: "ativo", rotulo: "Usuário ativo", tipo: "check", soNaEdicao: true },
];

export default function Usuarios() {
  return (
    <Cadastro<Usuario>
      titulo="Usuários"
      descricao="Quem acessa o sistema e o que cada pessoa pode fazer."
      endpoint="/usuarios"
      rotuloNovo="Novo usuário"
      campos={CAMPOS}
      podeEditar
      semBusca
      colunas={[
        { titulo: "Nome", valor: (u) => <strong>{u.nome}</strong> },
        { titulo: "E-mail", valor: (u) => u.email },
        { titulo: "Perfil", valor: (u) => NOMES_PAPEIS[u.papel] + (u.crf ? ` · CRF ${u.crf}` : "") },
        { titulo: "Comissão", valor: (u) => (u.recebe_comissao ? "Recebe" : "Não recebe") },
        { titulo: "Situação", valor: (u) => (u.ativo ? "Ativo" : "Inativo") },
      ]}
      rodape={
        <div className="cartao espaco-acima">
          <h2>Perfis de acesso</h2>
          <ul className="lista-simples">
            {PERFIS.map((p) => (
              <li key={p.papel}>
                <strong>{NOMES_PAPEIS[p.papel]}:</strong> {p.descricao}
              </li>
            ))}
          </ul>
        </div>
      }
    />
  );
}

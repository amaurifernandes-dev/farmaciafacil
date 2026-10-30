import { NavLink, Outlet, useLocation } from "react-router-dom";

import type { Sessao } from "../api/tipos";
import { cuidaDoEstoque, ehAdmin, ehGerente, NOMES_PAPEIS, useSessao } from "../sessao";
import Icone, { type NomeIcone } from "./Icone";

interface ItemMenu {
  para: string;
  rotulo: string;
  icone: NomeIcone;
  pode?: (sessao: Sessao | null) => boolean;
  /** Fica marcado também nas páginas abaixo deste caminho. */
  agrupa?: boolean;
}

const MENU: ItemMenu[] = [
  { para: "/", rotulo: "Visão geral", icone: "painel" },
  { para: "/vendas", rotulo: "Vendas / PDV", icone: "carrinho", agrupa: true },
  { para: "/caixas", rotulo: "Caixas", icone: "caixa" },
  { para: "/estoque", rotulo: "Estoque", icone: "pacote", agrupa: true },
  { para: "/compras", rotulo: "Compras", icone: "caminhao", agrupa: true, pode: cuidaDoEstoque },
  { para: "/financeiro", rotulo: "Financeiro", icone: "dinheiro", agrupa: true, pode: ehGerente },
  { para: "/configuracoes", rotulo: "Configurações", icone: "engrenagem", agrupa: true },
];

export const CONFIGURACOES: (ItemMenu & { descricao: string })[] = [
  { para: "/configuracoes/clientes", rotulo: "Clientes", icone: "pessoa", descricao: "Cadastro opcional e autorização de ofertas" },
  { para: "/configuracoes/fornecedores", rotulo: "Fornecedores", icone: "caminhao", descricao: "Distribuidoras e contatos de compra" },
  { para: "/configuracoes/produtos", rotulo: "Produtos", icone: "pacote", descricao: "Preços, códigos de barras e dados fiscais" },
  { para: "/configuracoes/usuarios", rotulo: "Usuários", icone: "pessoas", descricao: "Quem acessa o sistema e o que pode fazer", pode: ehAdmin },
  { para: "/configuracoes/farmacia", rotulo: "Minha farmácia", icone: "loja", descricao: "Dados da farmácia, matriz e filiais" },
  { para: "/configuracoes/gerais", rotulo: "Configurações gerais", icone: "ajustes", descricao: "Monocaixa ou multicaixa, descontos e alertas" },
];

function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

function ativo(item: ItemMenu, pathname: string): boolean {
  return item.agrupa ? pathname === item.para || pathname.startsWith(`${item.para}/`) : pathname === item.para;
}

export default function Layout() {
  const { sessao, sair } = useSessao();
  const { pathname } = useLocation();
  const itens = MENU.filter((item) => !item.pode || item.pode(sessao));
  const subitens = CONFIGURACOES.filter((item) => !item.pode || item.pode(sessao));
  const atual =
    subitens.find((item) => pathname.startsWith(item.para)) ?? itens.find((item) => ativo(item, pathname)) ?? itens[0];
  const emConfiguracoes = pathname.startsWith("/configuracoes");

  return (
    <div className="layout">
      <aside className="lateral">
        <div className="marca">
          <span className="marca-icone">
            <Icone nome="mais" />
          </span>
          <span>
            farmácia<strong>fácil</strong>
          </span>
        </div>
        <p className="lateral-titulo">Principal</p>
        <nav>
          {itens.map((item) => (
            <div key={item.para} className="menu-grupo">
              <NavLink to={item.para} className={() => (ativo(item, pathname) ? "active" : "")}>
                <Icone nome={item.icone} />
                {item.rotulo}
              </NavLink>
              {item.para === "/configuracoes" && emConfiguracoes && (
                <div className="submenu">
                  {subitens.map((sub) => (
                    <NavLink key={sub.para} to={sub.para}>
                      {sub.rotulo}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>
        <p className="lateral-rodape">FarmáciaFácil v0.2</p>
      </aside>
      <div className="principal">
        <header className="topo">
          <span className="trilha">
            Workspace / {emConfiguracoes && atual.para !== "/configuracoes" && "Configurações / "}
            <strong>{atual.rotulo}</strong>
          </span>
          {sessao && (
            <span className="usuario">
              <span className="avatar">{iniciais(sessao.nome)}</span>
              <span>
                <strong>{sessao.nome}</strong>
                <small>{NOMES_PAPEIS[sessao.papel]}</small>
              </span>
              <button type="button" className="botao-icone" onClick={sair} title="Sair">
                <Icone nome="sair" />
              </button>
            </span>
          )}
        </header>
        <main className="conteudo">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

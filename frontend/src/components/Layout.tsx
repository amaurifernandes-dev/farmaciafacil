import { NavLink, Outlet, useLocation } from "react-router-dom";

import { ehGerente, useSessao } from "../sessao";
import Icone, { type NomeIcone } from "./Icone";

interface ItemMenu {
  para: string;
  rotulo: string;
  icone: NomeIcone;
  soGerente?: boolean;
}

const MENU: ItemMenu[] = [
  { para: "/", rotulo: "Visão geral", icone: "painel" },
  { para: "/pdv", rotulo: "Vendas / PDV", icone: "carrinho" },
  { para: "/produtos", rotulo: "Produtos", icone: "pacote" },
  { para: "/estoque/entrada", rotulo: "Entrada de estoque", icone: "entrada", soGerente: true },
  { para: "/estoque/alertas", rotulo: "Alertas", icone: "alerta" },
];

const PAPEIS = { admin: "Administrador", gerente: "Gerente", caixa: "Operador de caixa" };

function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

export default function Layout() {
  const { sessao, sair } = useSessao();
  const { pathname } = useLocation();
  const itens = MENU.filter((item) => !item.soGerente || ehGerente(sessao));
  const atual = itens.find((item) => item.para === pathname) ?? itens[0];

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
            <NavLink key={item.para} to={item.para} end>
              <Icone nome={item.icone} />
              {item.rotulo}
            </NavLink>
          ))}
        </nav>
        <p className="lateral-rodape">FarmáciaFácil v0.1</p>
      </aside>
      <div className="principal">
        <header className="topo">
          <span className="trilha">
            Workspace / <strong>{atual.rotulo}</strong>
          </span>
          {sessao && (
            <span className="usuario">
              <span className="avatar">{iniciais(sessao.nome)}</span>
              <span>
                <strong>{sessao.nome}</strong>
                <small>{PAPEIS[sessao.papel]}</small>
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

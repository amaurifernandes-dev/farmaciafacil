import { NavLink, Outlet } from "react-router-dom";

import { ehGerente, useSessao } from "../sessao";

export default function Layout() {
  const { sessao, sair } = useSessao();
  return (
    <div className="layout">
      <header className="topo">
        <strong>FarmáciaFácil</strong>
        <nav>
          <NavLink to="/pdv">PDV</NavLink>
          <NavLink to="/produtos">Produtos</NavLink>
          {ehGerente(sessao) && <NavLink to="/estoque/entrada">Entrada de estoque</NavLink>}
          <NavLink to="/estoque/alertas">Alertas</NavLink>
        </nav>
        <span className="usuario">
          {sessao?.nome} <button onClick={sair}>Sair</button>
        </span>
      </header>
      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}

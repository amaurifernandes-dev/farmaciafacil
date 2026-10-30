import { NavLink, Outlet } from "react-router-dom";

import { cuidaDoEstoque, useSessao } from "../../sessao";

/** Abas do estoque: alertas de validade e mínimo, e entrada de mercadoria. */
export default function Estoque() {
  const { sessao } = useSessao();
  return (
    <div>
      <nav className="abas">
        <NavLink to="/estoque" end>
          Alertas
        </NavLink>
        {cuidaDoEstoque(sessao) && <NavLink to="/estoque/entrada">Entrada de mercadoria</NavLink>}
      </nav>
      <Outlet />
    </div>
  );
}

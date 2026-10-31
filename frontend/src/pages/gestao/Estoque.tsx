import { NavLink, Outlet } from "react-router-dom";

import { cuidaDoEstoque, useSessao } from "../../sessao";

/** Abas do estoque: alertas, saldo em cada loja, entrada manual e transferência entre lojas. */
export default function Estoque() {
  const { sessao } = useSessao();
  return (
    <div>
      <nav className="abas">
        <NavLink to="/estoque" end>
          Alertas
        </NavLink>
        <NavLink to="/estoque/saldos">Saldo por loja</NavLink>
        <NavLink to="/estoque/inventario">Inventário</NavLink>
        {cuidaDoEstoque(sessao) && (
          <>
            <NavLink to="/estoque/entrada">Entrada manual</NavLink>
            <NavLink to="/estoque/transferencia">Transferir entre lojas</NavLink>
          </>
        )}
      </nav>
      <Outlet />
    </div>
  );
}

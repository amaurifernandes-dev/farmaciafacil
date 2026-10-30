import { NavLink, Outlet, useLocation } from "react-router-dom";

/** Abas de compras: notas de entrada pelo XML e sugestão do que comprar. */
export default function Compras() {
  const { pathname } = useLocation();
  const emNotas = pathname === "/compras" || pathname.startsWith("/compras/notas");
  return (
    <div>
      <nav className="abas">
        <NavLink to="/compras" className={emNotas ? "active" : ""} end>
          Notas de entrada
        </NavLink>
        <NavLink to="/compras/sugestao">Sugestão de compras</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}

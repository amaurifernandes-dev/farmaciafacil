import { NavLink, Outlet } from "react-router-dom";

/** Abas do financeiro: contas a pagar, contas a receber e fluxo de caixa. */
export default function Financeiro() {
  return (
    <div>
      <nav className="abas">
        <NavLink to="/financeiro" end>
          Contas a pagar
        </NavLink>
        <NavLink to="/financeiro/receber">Contas a receber</NavLink>
        <NavLink to="/financeiro/fluxo">Fluxo de caixa</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}

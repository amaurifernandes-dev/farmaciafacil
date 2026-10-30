import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Alertas from "./pages/gestao/Alertas";
import Entrada from "./pages/gestao/Entrada";
import Produtos from "./pages/gestao/Produtos";
import Inicio from "./pages/Inicio";
import Login from "./pages/Login";
import Pdv from "./pages/pdv/Pdv";
import { useSessao } from "./sessao";

function Protegido({ children }: { children: ReactNode }) {
  const { sessao } = useSessao();
  return sessao ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/pdv" element={<Protegido><Pdv /></Protegido>} />
      <Route element={<Protegido><Layout /></Protegido>}>
        <Route path="/" element={<Inicio />} />
        <Route path="/produtos" element={<Produtos />} />
        <Route path="/estoque/entrada" element={<Entrada />} />
        <Route path="/estoque/alertas" element={<Alertas />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

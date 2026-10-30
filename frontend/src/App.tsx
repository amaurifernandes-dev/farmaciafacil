import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Caixas from "./pages/caixas/Caixas";
import Compras from "./pages/compras/Compras";
import Nota from "./pages/compras/Nota";
import Notas from "./pages/compras/Notas";
import Sugestao from "./pages/compras/Sugestao";
import Clientes from "./pages/clientes/Clientes";
import FichaCliente from "./pages/clientes/Ficha";
import Fornecedores from "./pages/configuracoes/Fornecedores";
import Gerais from "./pages/configuracoes/Gerais";
import ConfiguracoesInicio from "./pages/configuracoes/Inicio";
import MinhaFarmacia from "./pages/configuracoes/MinhaFarmacia";
import Produtos from "./pages/configuracoes/Produtos";
import Usuarios from "./pages/configuracoes/Usuarios";
import Alertas from "./pages/gestao/Alertas";
import Entrada from "./pages/gestao/Entrada";
import Contas from "./pages/financeiro/Contas";
import Financeiro from "./pages/financeiro/Financeiro";
import Fluxo from "./pages/financeiro/Fluxo";
import Estoque from "./pages/gestao/Estoque";
import Saldos from "./pages/gestao/Saldos";
import Transferencia from "./pages/gestao/Transferencia";
import Inicio from "./pages/Inicio";
import Login from "./pages/Login";
import Pdv from "./pages/pdv/Pdv";
import Faltas from "./pages/faltas/Faltas";
import AcompanharPedido from "./pages/loja/AcompanharPedido";
import LojaOnline from "./pages/loja/LojaOnline";
import Pedidos from "./pages/pedidos/Pedidos";
import Promocoes from "./pages/promocoes/Promocoes";
import Relatorios from "./pages/relatorios/Relatorios";
import FechamentoFiscal from "./pages/fiscal/FechamentoFiscal";
import PreVenda from "./pages/vendas/PreVenda";
import Vendas from "./pages/vendas/Vendas";
import { cuidaDoEstoque, ehAdmin, ehGerente, useSessao } from "./sessao";

function Protegido({ children }: { children: ReactNode }) {
  const { sessao } = useSessao();
  return sessao ? children : <Navigate to="/login" replace />;
}

function SoAdmin({ children }: { children: ReactNode }) {
  const { sessao } = useSessao();
  return ehAdmin(sessao) ? children : <Navigate to="/configuracoes" replace />;
}

function SoGerente({ children }: { children: ReactNode }) {
  const { sessao } = useSessao();
  return ehGerente(sessao) ? children : <Navigate to="/" replace />;
}

function SoEstoque({ children }: { children: ReactNode }) {
  const { sessao } = useSessao();
  return cuidaDoEstoque(sessao) ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Loja online: pública, sem login */}
      <Route path="/loja/:endereco" element={<LojaOnline />} />
      <Route path="/loja/:endereco/pedido/:codigo" element={<AcompanharPedido />} />
      <Route path="/pdv" element={<Protegido><Pdv /></Protegido>} />
      <Route element={<Protegido><Layout /></Protegido>}>
        <Route path="/" element={<Inicio />} />
        <Route path="/vendas" element={<Vendas />} />
        <Route path="/vendas/pre-venda" element={<PreVenda />} />
        <Route path="/caixas" element={<Caixas />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/clientes/:id" element={<FichaCliente />} />
        <Route path="/estoque" element={<Estoque />}>
          <Route index element={<Alertas />} />
          <Route path="saldos" element={<Saldos />} />
          <Route path="entrada" element={<Entrada />} />
          <Route path="transferencia" element={<Transferencia />} />
        </Route>
        <Route path="/compras" element={<SoEstoque><Compras /></SoEstoque>}>
          <Route index element={<Notas />} />
          <Route path="sugestao" element={<Sugestao />} />
          <Route path="notas/:id" element={<Nota />} />
        </Route>
        <Route path="/financeiro" element={<SoGerente><Financeiro /></SoGerente>}>
          <Route index element={<Contas key="pagar" tipo="pagar" />} />
          <Route path="receber" element={<Contas key="receber" tipo="receber" />} />
          <Route path="fluxo" element={<Fluxo />} />
        </Route>
        <Route path="/faltas" element={<Faltas />} />
        <Route path="/pedidos" element={<Pedidos />} />
        <Route path="/promocoes" element={<SoGerente><Promocoes /></SoGerente>} />
        <Route path="/relatorios" element={<SoGerente><Relatorios /></SoGerente>} />
        <Route path="/fiscal" element={<SoGerente><FechamentoFiscal /></SoGerente>} />
        <Route path="/configuracoes" element={<ConfiguracoesInicio />} />
        <Route path="/configuracoes/fornecedores" element={<Fornecedores />} />
        <Route path="/configuracoes/produtos" element={<Produtos />} />
        <Route path="/configuracoes/usuarios" element={<SoAdmin><Usuarios /></SoAdmin>} />
        <Route path="/configuracoes/farmacia" element={<MinhaFarmacia />} />
        <Route path="/configuracoes/gerais" element={<Gerais />} />
        {/* Endereços antigos */}
        <Route path="/produtos" element={<Navigate to="/configuracoes/produtos" replace />} />
        <Route path="/estoque/alertas" element={<Navigate to="/estoque" replace />} />
        <Route path="/configuracoes/clientes" element={<Navigate to="/clientes" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

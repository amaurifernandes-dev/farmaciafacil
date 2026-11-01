import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { ehAdmin, NOMES_PAPEIS, useSessao } from "../sessao";
import { ativa, GRUPOS, type Grupo, telaAtual, telasDe } from "../telas";
import Assistente from "./assistente/Assistente";
import { useAssistente } from "./assistente/visivel";
import BuscaTelas from "./BuscaTelas";
import Icone from "./Icone";

const CHAVE_ABERTOS = "ff.menu.abertos";
// Na primeira vez, só o dia a dia fica aberto; os outros grupos abrem com um clique (e a escolha fica lembrada).
const ABERTOS_PADRAO: Grupo[] = ["dia"];

function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

function lerAbertos(): Grupo[] {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ABERTOS) ?? "null");
    return Array.isArray(salvo) ? salvo : ABERTOS_PADRAO;
  } catch {
    return ABERTOS_PADRAO;
  }
}

export default function Layout() {
  const { sessao, sair } = useSessao();
  const { pathname } = useLocation();
  const telas = telasDe(sessao);
  const noMenu = telas.filter((t) => !t.aba);
  const atual = telaAtual(telas, pathname);
  const [abertos, setAbertos] = useState<Grupo[]>(lerAbertos);
  const [buscando, setBuscando] = useState(false);
  const [menuAberto, setMenuAberto] = useState(false);
  const assistente = useAssistente(sessao);

  // Ctrl+K (ou Cmd+K no Mac) abre a busca de telas de qualquer lugar.
  useEffect(() => {
    function tecla(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setBuscando((b) => !b);
      }
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  // No celular, escolher uma tela fecha o menu.
  useEffect(() => {
    setMenuAberto(false);
  }, [pathname]);

  function alternarGrupo(grupo: Grupo) {
    const novos = abertos.includes(grupo) ? abertos.filter((g) => g !== grupo) : [...abertos, grupo];
    setAbertos(novos);
    try {
      localStorage.setItem(CHAVE_ABERTOS, JSON.stringify(novos));
    } catch {
      // só não lembra a escolha
    }
  }

  const grupoAtual = atual?.grupo;
  const trilhaGrupo = GRUPOS.find((g) => g.id === grupoAtual)?.rotulo;

  return (
    <div className="layout">
      <aside className={menuAberto ? "lateral aberta" : "lateral"}>
        <div className="lateral-topo">
          <Link to="/" className="marca">
            <span className="marca-icone">
              <Icone nome="mais" />
            </span>
            <span>
              farmácia<strong>fácil</strong>
            </span>
          </Link>
          <button
            type="button"
            className="botao-icone menu-celular"
            aria-expanded={menuAberto}
            aria-controls="menu-principal"
            onClick={() => setMenuAberto((a) => !a)}
          >
            <Icone nome={menuAberto ? "x" : "menu"} />
            <span>Menu</span>
          </button>
        </div>
        <button type="button" className="buscar-tela" onClick={() => setBuscando(true)}>
          <Icone nome="busca" tamanho={16} />
          <span>Buscar tela</span>
          <kbd>Ctrl K</kbd>
        </button>
        <nav id="menu-principal" aria-label="Telas">
          {GRUPOS.map((grupo) => {
            const itens = noMenu.filter((t) => t.grupo === grupo.id);
            if (!itens.length) return null;
            // O grupo da tela aberta fica sempre aberto, para a pessoa ver onde está.
            const aberto = grupo.id === grupoAtual || abertos.includes(grupo.id);
            return (
              <div key={grupo.id} className="menu-secao">
                <button
                  type="button"
                  className={aberto ? "menu-secao-titulo aberta" : "menu-secao-titulo"}
                  aria-expanded={aberto}
                  onClick={() => alternarGrupo(grupo.id)}
                  disabled={grupo.id === grupoAtual}
                  title={grupo.id === grupoAtual ? "Você está numa tela deste grupo" : undefined}
                >
                  <span>{grupo.rotulo}</span>
                  <Icone nome="abaixo" tamanho={14} />
                </button>
                {aberto &&
                  itens.map((t) => (
                    <NavLink
                      key={`${t.para}-${t.rotulo}`}
                      to={t.para}
                      className={() => (ativa(t, pathname) || atual?.para.startsWith(`${t.para}/`) ? "active" : "")}
                    >
                      <Icone nome={t.icone} />
                      {t.rotulo}
                    </NavLink>
                  ))}
              </div>
            );
          })}
        </nav>
        <p className="lateral-rodape">FarmáciaFácil v0.3</p>
      </aside>
      <div className="principal">
        <header className="topo">
          <span className="trilha">
            {trilhaGrupo && `${trilhaGrupo} / `}
            <strong>{atual?.rotulo ?? "FarmáciaFácil"}</strong>
          </span>
          <span className="topo-direita">
            {assistente.disponivel ? (
              <button
                type="button"
                className={assistente.visivel ? "interruptor-ia ligado" : "interruptor-ia"}
                role="switch"
                aria-checked={assistente.visivel}
                onClick={assistente.alternar}
                title={assistente.visivel ? "Esconder o assistente de IA" : "Mostrar o assistente de IA"}
              >
                <Icone nome="brilho" tamanho={16} />
                <span className="interruptor-rotulo">Assistente IA</span>
                <span className="interruptor-trilho" aria-hidden="true">
                  <span />
                </span>
              </button>
            ) : (
              ehAdmin(sessao) &&
              assistente.status &&
              !assistente.status.ligado && (
                <Link to="/configuracoes/gerais#assistente" className="interruptor-ia desligado" title={assistente.status.mensagem ?? ""}>
                  <Icone nome="brilho" tamanho={16} />
                  <span className="interruptor-rotulo">IA sem chave</span>
                </Link>
              )
            )}
            {sessao && (
              <span className="usuario">
                <span className="avatar">{iniciais(sessao.nome)}</span>
                <span className="usuario-nome">
                  <strong>{sessao.nome}</strong>
                  <small>{NOMES_PAPEIS[sessao.papel]}</small>
                </span>
                <button type="button" className="botao-icone" onClick={sair} title="Sair">
                  <Icone nome="sair" />
                </button>
              </span>
            )}
          </span>
        </header>
        <main className="conteudo">
          <Outlet />
        </main>
      </div>
      {assistente.visivel && <Assistente abrir={assistente.abrirAgora} />}
      {buscando && <BuscaTelas telas={telas} aoFechar={() => setBuscando(false)} />}
    </div>
  );
}

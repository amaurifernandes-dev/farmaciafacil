import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Configuracoes } from "../../api/tipos";
import Icone from "../../components/Icone";
import { useInstalacao } from "../../instalacao";
import { avisarModulos, estaLigado, type InfoModulo, MODULOS } from "../../modulos";
import { useSessao } from "../../sessao";

/** Gerenciamento de telas: o administrador liga e desliga funções inteiras para todos, inclusive para si. */
export default function Telas() {
  const { sessao } = useSessao();
  const instalacao = useInstalacao();
  const [desligados, setDesligados] = useState<string[] | null>(null);
  const [salvando, setSalvando] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  useEffect(() => {
    api<Configuracoes>("/configuracoes")
      .then((c) => setDesligados(c.modulos_desligados ?? []))
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }, []);

  async function alternar(modulo: InfoModulo) {
    if (!desligados || !sessao) return;
    const desligar = !desligados.includes(modulo.id);
    const nova = desligar ? [...desligados, modulo.id] : desligados.filter((m) => m !== modulo.id);
    setSalvando(modulo.id);
    setAviso(null);
    try {
      const salvo = await api<Configuracoes>("/configuracoes", { metodo: "PATCH", corpo: { modulos_desligados: nova } });
      const lista = salvo.modulos_desligados ?? [];
      setDesligados(lista);
      avisarModulos(sessao.farmacia_id, lista);
      setAviso({
        tipo: "ok",
        texto: desligar
          ? `${modulo.rotulo} desligado. Sumiu das telas de todos.`
          : `${modulo.rotulo} ligado. Já aparece para quem tem acesso.`,
      });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    } finally {
      setSalvando(null);
    }
  }

  const ligados = desligados ? MODULOS.filter((m) => estaLigado(desligados, m.id)).length : 0;

  return (
    <div className="pagina">
      <p className="sobretitulo">Configurações</p>
      <div className="pagina-titulo">
        <div>
          <h1>Gerenciamento de telas</h1>
          <p className="vazio">
            Escolha o que a sua farmácia usa. Uma função desligada some do menu, da busca e da tela inicial de todo mundo,
            inclusive do administrador. Nada é apagado: ao ligar de novo, tudo volta como estava.
          </p>
        </div>
        {desligados && (
          <span className="etiqueta">
            {ligados} de {MODULOS.length} ligadas
          </span>
        )}
      </div>
      {aviso && (
        <p className={`${aviso.tipo} espaco-acima`} role="status">
          {aviso.texto}
        </p>
      )}

      {desligados && (
        <div className="grade-modulos espaco-acima">
          {MODULOS.map((m) => {
            const proprio = !desligados.includes(m.id);
            const semBase = m.depende && desligados.includes(m.depende);
            const semInternet = m.id === "loja_online" && instalacao && !instalacao.loja_online;
            const ligado = proprio && !semBase;
            const base = MODULOS.find((b) => b.id === m.depende);
            return (
              <section key={m.id} className={ligado ? "cartao modulo" : "cartao modulo modulo-off"}>
                <div className="modulo-topo">
                  <h2>{m.rotulo}</h2>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={proprio}
                    aria-label={`${proprio ? "Desligar" : "Ligar"} ${m.rotulo}`}
                    className={proprio ? "interruptor-ia ligado" : "interruptor-ia"}
                    disabled={salvando !== null}
                    onClick={() => void alternar(m)}
                  >
                    <span className="interruptor-rotulo">{salvando === m.id ? "Salvando..." : proprio ? "Ligado" : "Desligado"}</span>
                    <span className="interruptor-trilho" aria-hidden="true">
                      <span />
                    </span>
                  </button>
                </div>
                <p>{m.descricao}</p>
                <small className="vazio">Aparece em: {m.aparece}</small>
                {semBase && base && (
                  <small className="modulo-aviso">
                    <Icone nome="alerta" tamanho={14} /> Precisa de “{base.rotulo}” ligado para funcionar.
                  </small>
                )}
                {semInternet && (
                  <small className="modulo-aviso">
                    <Icone nome="alerta" tamanho={14} /> Com o sistema instalado na farmácia, a loja online não fica na internet.
                  </small>
                )}
              </section>
            );
          })}
        </div>
      )}
      <p className="nota espaco-acima">
        O básico não desliga: vendas e caixa, produtos, estoque, compras, clientes, financeiro, relatórios e configurações.
        O assistente de IA é ligado e desligado em Configurações gerais.
      </p>
    </div>
  );
}

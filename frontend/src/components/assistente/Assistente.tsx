import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import { quantidade, reais } from "../../formato";
import Icone from "../Icone";
import {
  type Conversa,
  CONVERSA_VAZIA,
  economia,
  type GuiaAtivo,
  guiaNestaTela,
  lerConversa,
  lerGuia,
  marcarPasso,
  salvarConversa,
  salvarGuia,
} from "./conversa";
import type { Cartao, CartaoGuia, Fala, RespostaAssistente } from "./tipos";
import { calar, falar, ouvir, temMicrofone } from "./voz";

const SUGESTOES = [
  "Mostra os protetores solares mais baratos e em promoção",
  "Abre uma pré-venda com 2 dipironas",
  "Quero cadastrar um cliente",
  "Como faço para incluir os produtos que chegaram do fornecedor?",
];

const CHAVE_LER = "ff.assistente.ler";

function lerPreferencia(): boolean {
  try {
    return localStorage.getItem(CHAVE_LER) === "1";
  } catch {
    return false;
  }
}

/** Botão "Assistente" em todas as telas da gestão, a conversa e o passo a passo do guia aberto. */
export default function Assistente() {
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const [aberto, setAberto] = useState(false);
  const [ligado, setLigado] = useState<boolean | null>(null);
  const [conversa, setConversa] = useState<Conversa>(() => lerConversa());
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [ouvindo, setOuvindo] = useState(false);
  const [lerEmVoz, setLerEmVoz] = useState(lerPreferencia);
  const [guia, setGuia] = useState<GuiaAtivo | null>(() => lerGuia());
  const pararDeOuvir = useRef<(() => void) | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  const microfone = temMicrofone();

  useEffect(() => {
    if (!aberto || ligado !== null) return;
    api<{ ligado: boolean }>("/assistente/status")
      .then((r) => setLigado(r.ligado))
      .catch(() => setLigado(true)); // sem resposta: deixa tentar, o erro aparece na conversa
  }, [aberto, ligado]);

  useEffect(() => {
    salvarConversa(conversa);
  }, [conversa]);
  useEffect(() => {
    salvarGuia(guia);
  }, [guia]);
  useEffect(() => {
    // Sem devolver nada: em navegadores novos o scrollIntoView devolve uma Promise.
    fim.current?.scrollIntoView({ block: "end" });
  }, [conversa.falas.length, pensando, aberto]);
  useEffect(() => {
    if (aberto) campo.current?.focus();
  }, [aberto]);
  useEffect(() => () => {
    pararDeOuvir.current?.();
  }, []);

  function alternarLeitura() {
    const novo = !lerEmVoz;
    setLerEmVoz(novo);
    if (!novo) calar();
    try {
      localStorage.setItem(CHAVE_LER, novo ? "1" : "0");
    } catch {
      // só não lembra a escolha
    }
  }

  async function enviar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || pensando) return;
    const antes = conversa;
    const falas: Fala[] = [...antes.falas, { de: "eu", texto: limpa }];
    setConversa({ ...antes, falas });
    setTexto("");
    setPensando(true);
    try {
      const r = await api<RespostaAssistente>("/assistente", {
        corpo: { historico: antes.historico, mensagem: limpa },
      });
      setConversa({ historico: r.historico, falas: [...falas, { de: "assistente", texto: r.resposta, cartoes: r.cartoes }] });
      if (lerEmVoz) falar(r.resposta);
    } catch (erro) {
      setConversa({ historico: antes.historico, falas: [...falas, { de: "assistente", texto: mensagem(erro), erro: true }] });
    } finally {
      setPensando(false);
    }
  }

  function alternarMicrofone() {
    if (ouvindo) {
      pararDeOuvir.current?.();
      return;
    }
    calar();
    setOuvindo(true);
    pararDeOuvir.current = ouvir(
      (parcial) => setTexto(parcial),
      (final, erro) => {
        setOuvindo(false);
        pararDeOuvir.current = null;
        if (final) void enviar(final);
        else if (erro) setConversa((c) => ({ ...c, falas: [...c.falas, { de: "assistente", texto: erro, erro: true }] }));
      },
    );
  }

  function novaConversa() {
    calar();
    setConversa(CONVERSA_VAZIA);
    setTexto("");
  }

  function comecar(cartao: CartaoGuia) {
    setGuia({ ...cartao, feitos: [] });
    setAberto(false);
    navegar(cartao.rota);
  }

  return (
    <>
      {guiaNestaTela(guia, pathname) && guia && !aberto && (
        <GuiaNaTela guia={guia} aoMarcar={(i) => setGuia(marcarPasso(guia, i))} aoFechar={() => setGuia(null)} />
      )}

      {!aberto && (
        <button type="button" className="assistente-botao" onClick={() => setAberto(true)} title="Assistente">
          <Icone nome="brilho" />
          <span>Assistente</span>
        </button>
      )}

      {aberto && (
        <aside className="assistente" aria-label="Assistente">
          <header className="assistente-topo">
            <span className="assistente-titulo">
              <span className="assistente-marca">
                <Icone nome="brilho" />
              </span>
              <span>
                <strong>Assistente</strong>
                <small>Procure produtos, abra pré-venda, cadastre cliente ou pergunte como fazer</small>
              </span>
            </span>
            <span className="assistente-acoes">
              {conversa.falas.length > 0 && (
                <button type="button" className="botao-pequeno" onClick={novaConversa}>
                  Nova conversa
                </button>
              )}
              <button type="button" className="botao-icone" onClick={() => setAberto(false)} title="Fechar">
                <Icone nome="x" />
              </button>
            </span>
          </header>

          <div className="assistente-conversa">
            {ligado === false && (
              <p className="aviso-conferencia">
                O assistente ainda não foi ligado neste sistema. Peça para quem cuida do servidor colocar a chave da
                Anthropic (ANTHROPIC_API_KEY).
              </p>
            )}
            {conversa.falas.length === 0 && (
              <div className="assistente-boas-vindas">
                <p>Olá! Fale ou digite o que precisa. Por exemplo:</p>
                {SUGESTOES.map((s) => (
                  <button key={s} type="button" className="assistente-sugestao" onClick={() => void enviar(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            {conversa.falas.map((f, i) => (
              <div key={i} className={`assistente-fala assistente-${f.de}${f.erro ? " assistente-erro" : ""}`}>
                {f.texto && <p className="assistente-balao">{f.texto}</p>}
                {f.cartoes?.map((c, j) => (
                  <CartaoAssistente
                    key={j}
                    cartao={c}
                    aoComecar={comecar}
                    aoPedir={(p) => void enviar(p)}
                    aoAbrir={() => setAberto(false)}
                  />
                ))}
              </div>
            ))}
            {pensando && (
              <div className="assistente-fala assistente-assistente">
                <p className="assistente-balao assistente-pensando" aria-label="Pensando">
                  <span />
                  <span />
                  <span />
                </p>
              </div>
            )}
            <div ref={fim} />
          </div>

          <form
            className="assistente-entrada"
            onSubmit={(e) => {
              e.preventDefault();
              void enviar(texto);
            }}
          >
            <textarea
              ref={campo}
              rows={2}
              value={texto}
              placeholder={ouvindo ? "Ouvindo... pode falar" : "Digite aqui ou use o microfone"}
              disabled={ligado === false}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void enviar(texto);
                }
              }}
            />
            <div className="assistente-botoes">
              <label className="assistente-ler">
                <input type="checkbox" checked={lerEmVoz} onChange={alternarLeitura} />
                Ler respostas em voz alta
              </label>
              {microfone && (
                <button
                  type="button"
                  className={`assistente-microfone${ouvindo ? " ouvindo" : ""}`}
                  onClick={alternarMicrofone}
                  disabled={ligado === false || pensando}
                  title={ouvindo ? "Parar de ouvir" : "Falar"}
                >
                  <Icone nome="microfone" />
                </button>
              )}
              <button type="submit" className="botao" disabled={!texto.trim() || pensando || ligado === false}>
                Enviar
              </button>
            </div>
          </form>
        </aside>
      )}
    </>
  );
}

function CartaoAssistente({
  cartao,
  aoComecar,
  aoPedir,
  aoAbrir,
}: {
  cartao: Cartao;
  aoComecar: (c: CartaoGuia) => void;
  aoPedir: (texto: string) => void;
  aoAbrir: () => void;
}) {
  if (cartao.tipo === "produtos") {
    if (cartao.itens.length === 0) return <p className="assistente-cartao vazio">Nenhum produto encontrado.</p>;
    return (
      <ul className="assistente-cartao assistente-produtos">
        {cartao.itens.map((p) => {
          const desconto = economia(p.preco, p.preco_final);
          return (
            <li key={p.produto_id}>
              <span className="assistente-produto">
                <strong>{p.nome}</strong>
                <small>
                  {[
                    p.apresentacao,
                    p.fabricante,
                    Number(p.estoque) > 0 ? `${quantidade(p.estoque)} em estoque` : "sem estoque",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
                {p.promocao && (
                  <span className="assistente-promo">
                    {p.promocao}
                    {p.so_clientes && " · só cliente cadastrado"}
                  </span>
                )}
              </span>
              <span className="assistente-preco">
                {desconto > 0 && <s>{reais(p.preco)}</s>}
                <strong>{reais(p.preco_final)}</strong>
                <button type="button" className="botao-pequeno" onClick={() => aoPedir(`Coloca 1 ${p.nome} na pré-venda`)}>
                  Pré-venda
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    );
  }
  if (cartao.tipo === "pre_venda") {
    return (
      <div className="assistente-cartao">
        <p className="assistente-cartao-titulo">
          <Icone nome="recibo" /> Pré-venda nº {cartao.numero} · {reais(cartao.total_com_promocoes)}
        </p>
        <ul className="assistente-lista">
          {cartao.itens.map((i, n) => (
            <li key={n}>
              {quantidade(i.quantidade)}x {i.descricao} <span>{reais(i.total)}</span>
            </li>
          ))}
        </ul>
        {cartao.total_com_promocoes !== cartao.total && (
          <p className="assistente-dica">
            Preço de tabela {reais(cartao.total)}. O caixa aplica as promoções ao receber.
          </p>
        )}
        <p className="assistente-dica">O cliente paga no caixa com o número {cartao.numero} (F7 no PDV).</p>
        <Link to="/vendas/pre-venda" className="botao-contorno" onClick={aoAbrir}>
          Ver pré-vendas
        </Link>
      </div>
    );
  }
  if (cartao.tipo === "cliente") {
    return (
      <div className="assistente-cartao">
        <p className="assistente-cartao-titulo">
          <Icone nome="pessoa" /> Cliente cadastrado: {cartao.nome}
        </p>
        <Link to={`/clientes/${cartao.id}`} className="botao-contorno" onClick={aoAbrir}>
          Abrir ficha do cliente
        </Link>
      </div>
    );
  }
  return (
    <div className="assistente-cartao">
      <p className="assistente-cartao-titulo">{cartao.titulo}</p>
      <ol className="assistente-passos">
        {cartao.passos.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ol>
      <button type="button" className="botao" onClick={() => aoComecar(cartao)}>
        Começar <Icone nome="seta" />
      </button>
    </div>
  );
}

function GuiaNaTela({
  guia,
  aoMarcar,
  aoFechar,
}: {
  guia: GuiaAtivo;
  aoMarcar: (indice: number) => void;
  aoFechar: () => void;
}) {
  const pronto = guia.feitos.length === guia.passos.length;
  return (
    <section className="guia-na-tela" aria-label="Passo a passo">
      <header>
        <strong>{guia.titulo}</strong>
        <button type="button" className="botao-icone" onClick={aoFechar} title="Fechar passo a passo">
          <Icone nome="x" />
        </button>
      </header>
      <ol>
        {guia.passos.map((p, i) => (
          <li key={i} className={guia.feitos.includes(i) ? "feito" : ""}>
            <label>
              <input type="checkbox" checked={guia.feitos.includes(i)} onChange={() => aoMarcar(i)} />
              <span>{p}</span>
            </label>
          </li>
        ))}
      </ol>
      {pronto && (
        <p className="ok">
          Tudo feito!{" "}
          <button type="button" className="botao-pequeno" onClick={aoFechar}>
            Fechar
          </button>
        </p>
      )}
    </section>
  );
}

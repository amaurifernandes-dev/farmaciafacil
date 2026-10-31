import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ErroApi, mensagem } from "../../api/cliente";
import type { FormaPedido, LojaPublica, PedidoPublico, ProdutoPublico } from "../../api/tipos";
import Icone from "../../components/Icone";
import { reais } from "../../formato";

interface ItemSacola {
  id: string;
  nome: string;
  preco: number; // da unidade, já com a promoção que aparece na vitrine
  quantidade: number;
  maximo: number;
  leveEPague: boolean;
}

function formas(pixNoSite: boolean): { valor: FormaPedido; nome: string }[] {
  return [
    { valor: "pix", nome: pixNoSite ? "Pix agora, pelo QR Code" : "Pix (na entrega ou no balcão)" },
    { valor: "cartao", nome: "Cartão (na entrega ou no balcão)" },
    { valor: "dinheiro", nome: "Dinheiro" },
  ];
}

/** Taxa da entrega em reais, ou null enquanto o cliente não escolheu o bairro. */
export function taxaDaEntrega(loja: LojaPublica, bairro: string, valorItens: number): number | null {
  if (loja.entrega_gratis_acima !== null && valorItens >= Number(loja.entrega_gratis_acima)) return 0;
  if (loja.bairros.length === 0) return Number(loja.entrega_taxa);
  const achado = loja.bairros.find((b) => b.bairro === bairro);
  return achado ? Number(achado.taxa) : null;
}

function chaveSacola(endereco: string) {
  return `ff.loja.${endereco}`;
}

function lerSacola(endereco: string): ItemSacola[] {
  try {
    return JSON.parse(localStorage.getItem(chaveSacola(endereco)) ?? "[]") as ItemSacola[];
  } catch {
    return [];
  }
}

/** Link do WhatsApp da farmácia, com a mensagem pronta. */
export function whatsappDaLoja(numero: string | null, texto: string): string | null {
  let digitos = (numero ?? "").replace(/\D/g, "");
  if (digitos.length < 10) return null;
  if (digitos.length <= 11) digitos = `55${digitos}`;
  return `https://wa.me/${digitos}?text=${encodeURIComponent(texto)}`;
}

export function CabecalhoLoja({ loja, endereco }: { loja: LojaPublica; endereco: string }) {
  const whatsapp = whatsappDaLoja(loja.whatsapp, `Olá! Vim pela loja online da ${loja.nome}.`);
  return (
    <header className="vitrine-topo">
      <div className="vitrine-largura">
        <a href={`/loja/${endereco}`} className="vitrine-marca">
          <span className="vitrine-logo">
            <Icone nome="mais" tamanho={18} />
          </span>
          <span>
            <strong>{loja.nome}</strong>
            {loja.cidade && (
              <small>
                {loja.endereco ? `${loja.endereco} · ` : ""}
                {loja.cidade}/{loja.uf}
              </small>
            )}
          </span>
        </a>
        {whatsapp && (
          <a className="vitrine-whatsapp" href={whatsapp} target="_blank" rel="noreferrer">
            Falar no WhatsApp
          </a>
        )}
      </div>
    </header>
  );
}

export default function LojaOnline() {
  const { endereco = "" } = useParams();
  const navegar = useNavigate();
  const [loja, setLoja] = useState<LojaPublica | null | undefined>(undefined);
  const [produtos, setProdutos] = useState<ProdutoPublico[]>([]);
  const [total, setTotal] = useState(0);
  const [busca, setBusca] = useState("");
  const [sacola, setSacola] = useState<ItemSacola[]>(() => lerSacola(endereco));
  const [fechando, setFechando] = useState(false);

  useEffect(() => {
    api<LojaPublica>(`/loja/${endereco}`)
      .then((dados) => {
        setLoja(dados);
        document.title = dados.nome;
      })
      .catch((e) => setLoja(e instanceof ErroApi && e.status === 404 ? null : undefined));
  }, [endereco]);

  useEffect(() => {
    const espera = setTimeout(() => {
      const params = new URLSearchParams({ por_pagina: "48" });
      if (busca.trim()) params.set("busca", busca.trim());
      api<{ produtos: ProdutoPublico[]; total: number }>(`/loja/${endereco}/produtos?${params}`)
        .then((c) => {
          setProdutos(c.produtos);
          setTotal(c.total);
        })
        .catch(() => setProdutos([]));
    }, busca ? 300 : 0);
    return () => clearTimeout(espera);
  }, [endereco, busca]);

  useEffect(() => {
    try {
      localStorage.setItem(chaveSacola(endereco), JSON.stringify(sacola));
    } catch {
      /* sem armazenamento: a sacola vale só enquanto a página estiver aberta */
    }
  }, [endereco, sacola]);

  function mudar(produto: ProdutoPublico, delta: number) {
    setSacola((atual) => {
      const item = atual.find((i) => i.id === produto.id);
      const quantidade = Math.min((item?.quantidade ?? 0) + delta, produto.maximo);
      if (quantidade <= 0) return atual.filter((i) => i.id !== produto.id);
      const novo: ItemSacola = {
        id: produto.id,
        nome: produto.apresentacao ? `${produto.nome} ${produto.apresentacao}` : produto.nome,
        preco: Number(produto.preco_promocional ?? produto.preco),
        quantidade,
        maximo: produto.maximo,
        leveEPague: !!produto.promocao && !produto.preco_promocional,
      };
      return item ? atual.map((i) => (i.id === produto.id ? novo : i)) : [...atual, novo];
    });
  }

  const quantidadeNaSacola = (id: string) => sacola.find((i) => i.id === id)?.quantidade ?? 0;
  const estimado = sacola.reduce((soma, i) => soma + i.preco * i.quantidade, 0);
  const unidades = sacola.reduce((soma, i) => soma + i.quantidade, 0);

  if (loja === undefined) return <div className="vitrine"><p className="vitrine-largura vazio">Carregando...</p></div>;
  if (loja === null) {
    return (
      <div className="vitrine">
        <div className="vitrine-largura vitrine-aviso">
          <h1>Loja não encontrada</h1>
          <p className="vazio">Confira o endereço. Se a farmácia desligou a loja online, fale com ela pelo telefone.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="vitrine">
      <CabecalhoLoja loja={loja} endereco={endereco} />
      <main className="vitrine-largura">
        {loja.mensagem && <p className="vitrine-recado">{loja.mensagem}</p>}
        <div className="vitrine-busca">
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar produto ou marca" />
          <small>
            {loja.entrega
              ? `Retire na loja ou receba em casa${Number(loja.entrega_minimo) > 0 ? ` (pedido mínimo de ${reais(loja.entrega_minimo)} para entrega)` : ""}.`
              : "Faça o pedido e retire na loja."}{" "}
            {loja.entrega && loja.entrega_gratis_acima !== null && `Entrega grátis acima de ${reais(loja.entrega_gratis_acima)}. `}
            {loja.pix ? "Pague com Pix na hora ou quando receber." : "Você paga quando receber."}
          </small>
        </div>

        <div className="vitrine-grade">
          {produtos.map((p) => {
            const naSacola = quantidadeNaSacola(p.id);
            return (
              <article key={p.id} className="vitrine-produto">
                {p.promocao && <span className="vitrine-selo">{p.promocao}</span>}
                <h3>{p.nome}</h3>
                <p className="vazio">
                  {p.apresentacao}
                  {p.fabricante && ` · ${p.fabricante}`}
                </p>
                <div className="vitrine-preco">
                  {p.preco_promocional ? (
                    <>
                      <s>{reais(p.preco)}</s>
                      <strong>{reais(p.preco_promocional)}</strong>
                    </>
                  ) : (
                    <strong>{reais(p.preco)}</strong>
                  )}
                </div>
                {naSacola === 0 ? (
                  <button className="vitrine-botao" onClick={() => mudar(p, 1)}>
                    Adicionar
                  </button>
                ) : (
                  <div className="vitrine-quantidade">
                    <button className="vitrine-botao-claro" onClick={() => mudar(p, -1)} aria-label="Tirar um">
                      −
                    </button>
                    <span>{naSacola}</span>
                    <button
                      className="vitrine-botao-claro"
                      onClick={() => mudar(p, 1)}
                      disabled={naSacola >= p.maximo}
                      aria-label="Mais um"
                    >
                      +
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
        {produtos.length === 0 && <p className="vazio vitrine-aviso">Nenhum produto encontrado.</p>}
        {total > produtos.length && (
          <p className="vazio">Mostrando {produtos.length} de {total}. Use a busca para achar o que precisa.</p>
        )}
      </main>

      {unidades > 0 && !fechando && (
        <div className="vitrine-barra">
          <div className="vitrine-largura">
            <span>
              {unidades} {unidades === 1 ? "item" : "itens"} · <strong>{reais(estimado, false)}</strong>
            </span>
            <button className="vitrine-botao" onClick={() => setFechando(true)}>
              Ver pedido e finalizar
            </button>
          </div>
        </div>
      )}

      {fechando && (
        <FecharPedido
          endereco={endereco}
          loja={loja}
          sacola={sacola}
          estimado={estimado}
          aoMudar={setSacola}
          aoVoltar={() => setFechando(false)}
          aoConcluir={(pedido) => {
            setSacola([]);
            navegar(`/loja/${endereco}/pedido/${pedido.codigo}`);
          }}
        />
      )}
    </div>
  );
}

function FecharPedido({
  endereco,
  loja,
  sacola,
  estimado,
  aoMudar,
  aoVoltar,
  aoConcluir,
}: {
  endereco: string;
  loja: LojaPublica;
  sacola: ItemSacola[];
  estimado: number;
  aoMudar: (sacola: ItemSacola[]) => void;
  aoVoltar: () => void;
  aoConcluir: (pedido: PedidoPublico) => void;
}) {
  const [nome, setNome] = useState("");
  const [telefone, setTelefone] = useState("");
  const [entrega, setEntrega] = useState(false);
  const [enderecoEntrega, setEnderecoEntrega] = useState("");
  const [bairro, setBairro] = useState("");
  const [forma, setForma] = useState<FormaPedido>("pix");
  const [troco, setTroco] = useState("");
  const [observacao, setObservacao] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const temLevePague = useMemo(() => sacola.some((i) => i.leveEPague), [sacola]);
  const abaixoDoMinimo = entrega && estimado < Number(loja.entrega_minimo);
  const taxa = entrega ? taxaDaEntrega(loja, bairro, estimado) : 0;
  const faltaGratis =
    entrega && loja.entrega_gratis_acima !== null && taxa !== 0 ? Number(loja.entrega_gratis_acima) - estimado : 0;

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      const pedido = await api<PedidoPublico>(`/loja/${endereco}/pedidos`, {
        corpo: {
          itens: sacola.map((i) => ({ produto_id: i.id, quantidade: String(i.quantidade) })),
          nome: nome.trim(),
          telefone: telefone.trim(),
          entrega,
          endereco: entrega ? enderecoEntrega.trim() : null,
          bairro: entrega && bairro ? bairro : null,
          forma_pagamento: forma,
          troco_para: forma === "dinheiro" && troco.trim() ? troco.replace(".", "").replace(",", ".") : null,
          observacao: observacao.trim() || null,
        },
      });
      aoConcluir(pedido);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="vitrine-fundo" onClick={aoVoltar}>
      <form className="vitrine-painel" onSubmit={enviar} onClick={(e) => e.stopPropagation()}>
        <div className="vitrine-painel-topo">
          <h2>Seu pedido</h2>
          <button type="button" className="vitrine-fechar" onClick={aoVoltar} aria-label="Voltar">
            <Icone nome="x" />
          </button>
        </div>
        <ul className="vitrine-itens">
          {sacola.map((i) => (
            <li key={i.id}>
              <span>
                {i.quantidade}× {i.nome}
              </span>
              <span>{reais(i.preco * i.quantidade, false)}</span>
              <button
                type="button"
                className="vitrine-tirar"
                onClick={() => aoMudar(sacola.filter((x) => x.id !== i.id))}
              >
                tirar
              </button>
            </li>
          ))}
        </ul>
        {entrega && (
          <p className="vitrine-subtotal">
            <span>Produtos {reais(estimado, false)}</span>
            <span>
              Entrega {taxa === null ? "(escolha o bairro)" : taxa === 0 ? "grátis" : reais(taxa, false)}
            </span>
          </p>
        )}
        <p className="vitrine-total">
          Total <strong>{reais(estimado + (taxa ?? 0), false)}</strong>
        </p>
        {temLevePague && <p className="vazio">O desconto do leve e pague entra no total confirmado.</p>}

        <label>
          Seu nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} required minLength={2} autoComplete="name" />
        </label>
        <label>
          Celular (WhatsApp)
          <input
            value={telefone}
            onChange={(e) => setTelefone(e.target.value)}
            required
            inputMode="tel"
            autoComplete="tel"
            placeholder="(11) 98888-7777"
          />
        </label>

        <div className="vitrine-opcoes">
          <label className={!entrega ? "marcada" : ""}>
            <input type="radio" checked={!entrega} onChange={() => setEntrega(false)} /> Retirar na loja
          </label>
          {loja.entrega && (
            <label className={entrega ? "marcada" : ""}>
              <input type="radio" checked={entrega} onChange={() => setEntrega(true)} /> Receber em casa
            </label>
          )}
        </div>
        {entrega && (
          <label>
            Endereço para entrega
            <input
              value={enderecoEntrega}
              onChange={(e) => setEnderecoEntrega(e.target.value)}
              required
              autoComplete="street-address"
              placeholder="Rua, número, bairro e complemento"
            />
            {loja.entrega_area && <small>Entregamos em: {loja.entrega_area}</small>}
          </label>
        )}
        {entrega && loja.bairros.length > 0 && (
          <label>
            Bairro
            <select value={bairro} onChange={(e) => setBairro(e.target.value)} required>
              <option value="">Escolha o bairro</option>
              {loja.bairros.map((b) => (
                <option key={b.bairro} value={b.bairro}>
                  {b.bairro} · {Number(b.taxa) === 0 ? "entrega grátis" : `entrega ${reais(b.taxa, false)}`}
                </option>
              ))}
            </select>
            <small>Não achou o seu? Fale com a farmácia pelo WhatsApp.</small>
          </label>
        )}
        {faltaGratis > 0 && (
          <p className="vitrine-dica">Faltam {reais(faltaGratis, false)} para a entrega sair grátis.</p>
        )}
        {abaixoDoMinimo && (
          <p className="erro">Para entrega, o pedido mínimo é {reais(loja.entrega_minimo)}.</p>
        )}

        <label>
          Como vai pagar
          <select value={forma} onChange={(e) => setForma(e.target.value as FormaPedido)}>
            {formas(loja.pix).map((f) => (
              <option key={f.valor} value={f.valor}>
                {f.nome}
              </option>
            ))}
          </select>
        </label>
        {forma === "pix" && loja.pix && (
          <p className="vitrine-dica">Depois de enviar, aparece o QR Code e o código "copia e cola" do Pix.</p>
        )}
        {forma === "dinheiro" && (
          <label>
            Troco para quanto? (opcional)
            <input value={troco} onChange={(e) => setTroco(e.target.value)} inputMode="decimal" placeholder="ex.: 100" />
          </label>
        )}
        <label>
          Observação (opcional)
          <input value={observacao} onChange={(e) => setObservacao(e.target.value)} maxLength={300} />
        </label>

        {erro && <p className="erro">{erro}</p>}
        <button className="vitrine-botao vitrine-enviar" disabled={enviando || sacola.length === 0 || abaixoDoMinimo}>
          {enviando ? "Enviando..." : "Enviar pedido"}
        </button>
        <p className="vazio vitrine-letra-miuda">
          A farmácia confere o pedido e avisa pelo WhatsApp. Remédios que precisam de receita não são vendidos por aqui.
        </p>
      </form>
    </div>
  );
}

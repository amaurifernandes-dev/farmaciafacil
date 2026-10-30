import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, lerChaveTerminal, mensagem } from "../../api/cliente";
import type { Loja, PaginaProdutos, PreVenda as TipoPreVenda, Produto } from "../../api/tipos";
import Icone from "../../components/Icone";
import { reais } from "../../formato";
import { lerQuantidade, paraCentavos } from "../pdv/carrinho";

interface Item {
  produto: Produto;
  quantidade: string;
}

function totalItem(item: Item): number {
  return Math.round((paraCentavos(item.produto.preco_venda) ?? 0) * (lerQuantidade(item.quantidade) ?? 0));
}

/** Pré-venda: o atendente monta no balcão e o cliente paga no caixa. */
export default function PreVenda() {
  const [termo, setTermo] = useState("");
  const [resultados, setResultados] = useState<Produto[]>([]);
  const [itens, setItens] = useState<Item[]>([]);
  const [cpf, setCpf] = useState("");
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [lojaId, setLojaId] = useState("");
  const [enviada, setEnviada] = useState<TipoPreVenda | null>(null);
  const [erro, setErro] = useState("");
  const busca = useRef<HTMLInputElement>(null);
  // Num PDV registrado, a loja é a dele; sem registro, pergunta se houver mais de uma.
  const temTerminal = Boolean(lerChaveTerminal());

  useEffect(() => {
    api<Loja[]>("/lojas")
      .then((l) => {
        const ativas = l.filter((loja) => loja.ativo);
        setLojas(ativas);
        setLojaId(ativas[0]?.id ?? "");
      })
      .catch(() => setLojas([]));
  }, []);

  async function buscar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    const texto = termo.trim();
    if (!texto) return;
    try {
      const pagina = await api<PaginaProdutos>(`/produtos?busca=${encodeURIComponent(texto)}&por_pagina=20`);
      if (pagina.itens.length === 1 && /^\d{8,14}$/.test(texto)) {
        // Código de barras bipado: já entra direto.
        adicionar(pagina.itens[0]);
        setTermo("");
        return;
      }
      setResultados(pagina.itens);
      if (pagina.itens.length === 0) setErro(`Nenhum produto encontrado para "${texto}"`);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  function adicionar(produto: Produto) {
    setItens((atual) => {
      const existente = atual.findIndex((i) => i.produto.id === produto.id);
      if (existente < 0) return [...atual, { produto, quantidade: "1" }];
      return atual.map((item, i) =>
        i === existente ? { ...item, quantidade: String((lerQuantidade(item.quantidade) ?? 0) + 1) } : item,
      );
    });
    setResultados([]);
    setTermo("");
    busca.current?.focus();
  }

  async function enviar() {
    setErro("");
    const invalido = itens.find((i) => lerQuantidade(i.quantidade) === null);
    if (invalido) return setErro(`Quantidade inválida em ${invalido.produto.nome}`);
    try {
      const pre = await api<TipoPreVenda>("/pre-vendas", {
        corpo: {
          itens: itens.map((i) => ({ produto_id: i.produto.id, quantidade: String(lerQuantidade(i.quantidade)) })),
          cliente_cpf: cpf || null,
          loja_id: temTerminal ? null : lojaId || null,
        },
      });
      setEnviada(pre);
      setItens([]);
      setCpf("");
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  const total = itens.reduce((soma, item) => soma + totalItem(item), 0);

  if (enviada) {
    return (
      <div className="pagina">
        <section className="cartao confirmacao">
          <p className="sobretitulo">Pré-venda enviada ao caixa</p>
          <p className="numero-grande">Nº {enviada.numero}</p>
          <p>
            Total de <strong>{reais(enviada.total)}</strong>. Informe o número ao cliente para pagar no caixa.
          </p>
          <div className="acoes">
            <button type="button" onClick={() => setEnviada(null)} autoFocus>
              Nova pré-venda
            </button>
            <Link to="/vendas" className="botao-contorno">
              Voltar para vendas
            </Link>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">
            <Link to="/vendas">Vendas</Link> / Pré-venda
          </p>
          <h1>Nova pré-venda</h1>
          <p className="vazio">Monte o pedido no balcão e encaminhe para o caixa receber.</p>
        </div>
      </div>

      <div className="inicio-grade">
        <section className="cartao">
          <h2>Adicionar produtos</h2>
          <form className="barra espaco-acima" onSubmit={buscar}>
            <input
              ref={busca}
              placeholder="Bipe o código de barras ou digite o nome"
              value={termo}
              onChange={(e) => setTermo(e.target.value)}
              autoFocus
            />
            <button type="submit">Buscar</button>
          </form>
          {erro && <p className="erro">{erro}</p>}
          <ul className="lista-produtos">
            {resultados.map((p) => (
              <li key={p.id}>
                <span>
                  <strong>{p.nome}</strong> {p.apresentacao && <small>{p.apresentacao}</small>}
                </span>
                <button type="button" className="botao-pequeno" onClick={() => adicionar(p)}>
                  {reais(p.preco_venda)} <Icone nome="mais" tamanho={14} />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="cartao">
          <h2>Pedido</h2>
          {itens.length === 0 ? (
            <p className="lista-vazia">Nenhum item adicionado.</p>
          ) : (
            <ul className="lista-produtos">
              {itens.map((item, indice) => (
                <li key={item.produto.id}>
                  <span>
                    <strong>{item.produto.nome}</strong>
                    <small> {reais(totalItem(item), true)}</small>
                  </span>
                  <span className="acoes">
                    <input
                      className="quantidade"
                      value={item.quantidade}
                      inputMode="decimal"
                      aria-label={`Quantidade de ${item.produto.nome}`}
                      onChange={(e) =>
                        setItens((atual) =>
                          atual.map((it, i) => (i === indice ? { ...it, quantidade: e.target.value } : it)),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="botao-icone"
                      title="Remover"
                      onClick={() => setItens((atual) => atual.filter((_, i) => i !== indice))}
                    >
                      <Icone nome="lixo" tamanho={16} />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <label className="espaco-acima">
            CPF na nota (opcional)
            <input value={cpf} onChange={(e) => setCpf(e.target.value)} inputMode="numeric" />
          </label>
          {!temTerminal && lojas.length > 1 && (
            <label className="espaco-acima">
              Loja
              <select value={lojaId} onChange={(e) => setLojaId(e.target.value)}>
                {lojas.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.nome}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="total-grande">{reais(total, true)}</p>
          <button type="button" className="botao largura-total" disabled={itens.length === 0} onClick={enviar}>
            Encaminhar ao caixa <Icone nome="seta" />
          </button>
        </section>
      </div>
    </div>
  );
}

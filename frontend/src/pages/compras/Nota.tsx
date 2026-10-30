import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { ItemNotaEntrada, NotaEntrada, Produto } from "../../api/tipos";
import BuscaProduto from "../../components/BuscaProduto";
import { Janela } from "../../components/Cadastro";
import { data, quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";
import { STATUS_NOTA } from "./Notas";

/** Conferência da nota importada: liga cada item a um produto do sistema e confirma a entrada. */
export default function Nota() {
  const { id } = useParams();
  const lojas = useLojas();
  const [nota, setNota] = useState<NotaEntrada | null>(null);
  const [escolhendo, setEscolhendo] = useState<ItemNotaEntrada | null>(null);
  const [cadastrando, setCadastrando] = useState<ItemNotaEntrada | null>(null);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");

  const carregar = useCallback(() => {
    api<NotaEntrada>(`/compras/notas/${id}`)
      .then(setNota)
      .catch((e) => setErro(mensagem(e)));
  }, [id]);

  useEffect(carregar, [carregar]);

  async function atualizar(item: ItemNotaEntrada, dados: Record<string, unknown>) {
    setErro("");
    try {
      setNota(await api<NotaEntrada>(`/compras/notas/${id}/itens/${item.id}`, { metodo: "PATCH", corpo: dados }));
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  async function acao(caminho: "confirmar" | "cancelar") {
    setErro("");
    try {
      const atualizada = await api<NotaEntrada>(`/compras/notas/${id}/${caminho}`, { corpo: {} });
      setNota(atualizada);
      setOk(caminho === "confirmar" ? "Pronto! Os produtos já estão no estoque." : "Nota cancelada.");
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  if (!nota) return erro ? <p className="erro">{erro}</p> : <p>Carregando...</p>;

  const pendente = nota.status === "pendente";
  const loja = lojas.find((l) => l.id === nota.loja_id);

  return (
    <div className="pagina">
      <p className="sobretitulo">
        <Link to="/compras">Notas de entrada</Link>
      </p>
      <div className="pagina-titulo">
        <div>
          <h1>
            Nota {nota.numero} <span className={STATUS_NOTA[nota.status].classe}>{STATUS_NOTA[nota.status].rotulo}</span>
          </h1>
          <p className="vazio">
            {nota.fornecedor_nome} · emitida em {data(nota.emitida_em)}
            {loja && ` · entra no estoque de ${loja.nome}`}
          </p>
        </div>
        {pendente && (
          <div className="acoes">
            <button type="button" className="botao-secundario" onClick={() => acao("cancelar")}>
              Cancelar nota
            </button>
            <button className="botao" disabled={nota.itens_sem_produto > 0} onClick={() => acao("confirmar")}>
              Confirmar entrada no estoque
            </button>
          </div>
        )}
      </div>

      {pendente && nota.itens_sem_produto > 0 && (
        <p className="aviso-conferencia">
          {nota.itens_sem_produto === 1 ? "1 item ainda não foi ligado" : `${nota.itens_sem_produto} itens ainda não foram ligados`} a
          um produto do sistema. Na próxima nota deste fornecedor o sistema já reconhece sozinho.
        </p>
      )}
      {erro && <p className="erro">{erro}</p>}
      {ok && <p className="ok">{ok}</p>}

      <section className="cartao espaco-acima">
        <div className="tabela-rolagem">
          <table className="tabela tabela-nota">
            <thead>
              <tr>
                <th>Item da nota</th>
                <th>Produto no sistema</th>
                <th className="num">Na nota</th>
                <th className="num">Un. por embalagem</th>
                <th className="num">Entra no estoque</th>
                <th>Lote</th>
                <th>Validade</th>
                <th className="num">Custo por un.</th>
              </tr>
            </thead>
            <tbody>
              {nota.itens.map((item) => (
                <LinhaItem
                  key={item.id}
                  item={item}
                  editavel={pendente}
                  aoAtualizar={(dados) => atualizar(item, dados)}
                  aoEscolher={() => setEscolhendo(item)}
                  aoCadastrar={() => setCadastrando(item)}
                />
              ))}
            </tbody>
          </table>
        </div>
        <dl className="dados">
          <dt>Valor dos produtos</dt>
          <dd>{reais(nota.valor_produtos)}</dd>
          <dt>Valor total da nota</dt>
          <dd>
            <strong>{reais(nota.valor_total)}</strong>
          </dd>
          <dt>Chave de acesso</dt>
          <dd className="chave">{nota.chave}</dd>
        </dl>
      </section>

      {escolhendo && (
        <Janela titulo="Qual produto é este?" aoFechar={() => setEscolhendo(null)}>
          <p className="vazio">
            Na nota: <strong>{escolhendo.descricao}</strong>
            {escolhendo.ean && ` · código ${escolhendo.ean}`}
          </p>
          <BuscaProduto
            autoFocus
            inicial={escolhendo.descricao.split(" ").slice(0, 2).join(" ")}
            aoEscolher={(produto) => {
              atualizar(escolhendo, { produto_id: produto.id });
              setEscolhendo(null);
            }}
          />
          <p className="nota">
            Não achou?{" "}
            <button
              type="button"
              className="botao-pequeno"
              onClick={() => {
                setCadastrando(escolhendo);
                setEscolhendo(null);
              }}
            >
              Cadastrar produto novo
            </button>
          </p>
        </Janela>
      )}

      {cadastrando && (
        <NovoProduto
          item={cadastrando}
          aoFechar={() => setCadastrando(null)}
          aoCriar={(produto) => {
            atualizar(cadastrando, { produto_id: produto.id });
            setCadastrando(null);
          }}
        />
      )}
    </div>
  );
}

function LinhaItem({
  item,
  editavel,
  aoAtualizar,
  aoEscolher,
  aoCadastrar,
}: {
  item: ItemNotaEntrada;
  editavel: boolean;
  aoAtualizar: (dados: Record<string, unknown>) => void;
  aoEscolher: () => void;
  aoCadastrar: () => void;
}) {
  const [fator, setFator] = useState(String(item.fator));
  const [lote, setLote] = useState(item.numero_lote ?? "");
  const [validade, setValidade] = useState(item.validade ?? "");
  const precisaLote = item.produto_controla_lote !== false;

  useEffect(() => {
    setFator(String(item.fator));
    setLote(item.numero_lote ?? "");
    setValidade(item.validade ?? "");
  }, [item]);

  const unidades = Number(item.quantidade) * item.fator;
  const custo = Number(item.valor_unitario) / item.fator;

  return (
    <tr className={item.produto_id ? "" : "sem-produto"}>
      <td>
        {item.descricao}
        <br />
        <small>
          cód. {item.codigo_fornecedor}
          {item.ean && ` · ${item.ean}`}
        </small>
      </td>
      <td>
        {item.produto_id ? (
          <>
            {item.produto_nome}
            {editavel && (
              <>
                <br />
                <button type="button" className="botao-pequeno" onClick={aoEscolher}>
                  Trocar
                </button>
              </>
            )}
          </>
        ) : editavel ? (
          <div className="acoes">
            <button type="button" className="botao-pequeno" onClick={aoEscolher}>
              Escolher produto
            </button>
            <button type="button" className="botao-pequeno" onClick={aoCadastrar}>
              Cadastrar novo
            </button>
          </div>
        ) : (
          <small>sem produto</small>
        )}
      </td>
      <td className="num">
        {quantidade(item.quantidade)} <small>{item.unidade}</small>
      </td>
      <td className="num">
        {editavel ? (
          <input
            className="quantidade"
            value={fator}
            inputMode="numeric"
            onChange={(e) => setFator(e.target.value)}
            onBlur={() => Number(fator) >= 1 && Number(fator) !== item.fator && aoAtualizar({ fator: Number(fator) })}
          />
        ) : (
          item.fator
        )}
      </td>
      <td className="num">
        <strong>{quantidade(unidades)}</strong>
      </td>
      <td>
        {!precisaLote ? (
          <small>sem lote</small>
        ) : editavel ? (
          <input
            value={lote}
            size={10}
            onChange={(e) => setLote(e.target.value)}
            onBlur={() => lote !== (item.numero_lote ?? "") && aoAtualizar({ numero_lote: lote || null })}
          />
        ) : (
          item.numero_lote
        )}
      </td>
      <td>
        {!precisaLote ? (
          ""
        ) : editavel ? (
          <input
            type="date"
            value={validade}
            onChange={(e) => setValidade(e.target.value)}
            onBlur={() => validade !== (item.validade ?? "") && aoAtualizar({ validade: validade || null })}
          />
        ) : (
          data(item.validade)
        )}
      </td>
      <td className="num">{reais(custo, false)}</td>
    </tr>
  );
}

function NovoProduto({
  item,
  aoFechar,
  aoCriar,
}: {
  item: ItemNotaEntrada;
  aoFechar: () => void;
  aoCriar: (produto: Produto) => void;
}) {
  const custo = Number(item.valor_unitario) / item.fator;
  const [nome, setNome] = useState(item.descricao);
  const [preco, setPreco] = useState("");
  const [tipo, setTipo] = useState<Produto["tipo"]>(item.registro_ms ? "medicamento" : "outros");
  const [controlaLote, setControlaLote] = useState(Boolean(item.registro_ms || item.numero_lote));
  const [erro, setErro] = useState("");

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    try {
      const produto = await api<Produto>("/produtos", {
        corpo: {
          nome: nome.trim(),
          // Com fator maior que 1, o código da nota é da embalagem fechada, não da unidade vendida.
          ean: item.fator === 1 && item.ean && item.ean.length <= 14 ? item.ean : null,
          ncm: item.ncm,
          cest: item.cest,
          registro_ms: item.registro_ms,
          tipo,
          controla_lote: controlaLote,
          preco_venda: preco.replace(",", "."),
          preco_custo: custo.toFixed(2),
        },
      });
      aoCriar(produto);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Cadastrar produto novo" aoFechar={aoFechar}>
      <form onSubmit={salvar}>
        <fieldset className="campos">
          <label className="largo">
            Nome
            <input value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={200} />
          </label>
          <label>
            Preço de venda (R$)
            <input value={preco} onChange={(e) => setPreco(e.target.value)} required autoFocus inputMode="decimal" />
            <small>Custo nesta nota: {reais(custo, false)} por unidade</small>
          </label>
          <label>
            Tipo
            <select value={tipo} onChange={(e) => setTipo(e.target.value as Produto["tipo"])}>
              <option value="medicamento">Medicamento</option>
              <option value="perfumaria">Perfumaria</option>
              <option value="outros">Outros</option>
            </select>
          </label>
          <label className="checkbox caixa-marcacao largo">
            <input type="checkbox" checked={controlaLote} onChange={(e) => setControlaLote(e.target.checked)} />
            <span>
              Controla lote e validade
              <small>Obrigatório para medicamentos.</small>
            </span>
          </label>
          <p className="nota largo">Código de barras, NCM, CEST e registro MS vêm da nota. Dá para completar depois em Produtos.</p>
        </fieldset>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes direita espaco-acima">
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            Voltar
          </button>
          <button type="submit" className="botao">
            Cadastrar e usar nesta nota
          </button>
        </div>
      </form>
    </Janela>
  );
}

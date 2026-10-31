import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import qrcode from "qrcode-generator";

import { api, baixar, mensagem } from "../../api/cliente";
import type { InventarioDetalhe, ItemInventario } from "../../api/tipos";
import Icone from "../../components/Icone";
import { quantidade as fmtQtd, reais } from "../../formato";
import { quando, STATUS_INVENTARIO } from "./Inventarios";

type Filtro = "diferenca" | "todos" | "nao_contados";

function Diferenca({ valor, dinheiro = false }: { valor: string | null; dinheiro?: boolean }) {
  const n = Number(valor ?? 0);
  if (!n) return <span className="vazio">{dinheiro ? "-" : "0"}</span>;
  const texto = dinheiro ? reais(Math.abs(n).toFixed(2)) : fmtQtd(Math.abs(n));
  return <span className={n > 0 ? "positivo" : "negativo"}>{`${n > 0 ? "+" : "−"}${texto}`}</span>;
}

/** Revisão do inventário: o que foi contado, as diferenças e o botão de acertar o estoque. */
export default function Inventario() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [dados, setDados] = useState<InventarioDetalhe | null>(null);
  const [filtro, setFiltro] = useState<Filtro>("diferenca");
  const [confirmar, setConfirmar] = useState<"finalizar" | "cancelar" | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  function carregar() {
    api<InventarioDetalhe>(`/inventarios/${id}`)
      .then(setDados)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(carregar, [id]);

  // Atualiza sozinho enquanto a equipe conta.
  useEffect(() => {
    if (dados?.status !== "aberto") return;
    const t = setInterval(carregar, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dados?.status, id]);

  const endereco = `${window.location.origin}/inventario/${id}/contar`;
  const qr = useMemo(() => {
    const codigo = qrcode(0, "M");
    codigo.addData(endereco);
    codigo.make();
    return codigo.createDataURL(4, 2);
  }, [endereco]);

  if (!dados) return aviso ? <p className="erro">{aviso.texto}</p> : <p>Carregando...</p>;

  async function encerrar(acao: "finalizar" | "cancelar") {
    try {
      await api(`/inventarios/${id}/${acao}`, { corpo: {} });
      setConfirmar(null);
      setAviso({
        tipo: "ok",
        texto: acao === "finalizar" ? "Pronto! O estoque agora é o que foi contado." : "Contagem cancelada. O estoque não mudou.",
      });
      carregar();
    } catch (e) {
      setConfirmar(null);
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  const r = dados.resumo;
  const aberto = dados.status === "aberto";
  const todos: ItemInventario[] = [...dados.itens, ...(dados.nao_contados ?? [])];
  const linhas =
    filtro === "diferenca"
      ? todos.filter((i) => Number(i.diferenca ?? 0) !== 0)
      : filtro === "nao_contados"
        ? todos.filter((i) => !i.contado)
        : todos;
  linhas.sort((a, b) => Math.abs(Number(b.valor_diferenca ?? 0)) - Math.abs(Number(a.valor_diferenca ?? 0)));

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">
            <Link to="/estoque/inventario">Inventário</Link> · {dados.loja_nome}
          </p>
          <h1>
            {dados.descricao} <span className={`etiqueta ${STATUS_INVENTARIO[dados.status].classe}`}>{STATUS_INVENTARIO[dados.status].texto}</span>
          </h1>
          <p className="vazio">
            {dados.escopo === "geral" ? "Geral: o que ninguém contar fica com zero." : "Parcial: só muda o saldo do que foi contado."}{" "}
            Aberto por {dados.aberto_por} em {quando(dados.criado_em)}
            {dados.finalizado_em && ` · finalizado por ${dados.finalizado_por} em ${quando(dados.finalizado_em)}`}.
          </p>
        </div>
        <div className="acoes-titulo">
          <button type="button" className="botao-pequeno" onClick={() => baixar(`/inventarios/${id}/planilha`).catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }))}>
            Planilha
          </button>
          {aberto && (
            <Link className="botao" to={`/inventario/${id}/contar`}>
              <Icone nome="celular" /> Contar
            </Link>
          )}
        </div>
      </div>

      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}

      <div className="indicadores indicadores-financeiro">
        <div className="cartao indicador">
          <small>Produtos contados</small>
          <strong>{r.produtos_contados}</strong>
          <span>{fmtQtd(r.unidades_contadas)} unidades</span>
        </div>
        <div className="cartao indicador">
          <small>{aberto ? "Vai faltar" : "Faltou"}</small>
          <strong className="negativo-texto">{reais(dados.valor_falta ?? r.valor_falta ?? "0")}</strong>
          <span>pelo preço de custo</span>
        </div>
        <div className="cartao indicador">
          <small>{aberto ? "Vai sobrar" : "Sobrou"}</small>
          <strong>{reais(dados.valor_sobra ?? r.valor_sobra ?? "0")}</strong>
          <span>{r.sem_custo ? `${r.sem_custo} produto(s) sem custo no cadastro` : "pelo preço de custo"}</span>
        </div>
        <div className="cartao indicador">
          <small>{aberto ? "Com diferença" : "Ajustados"}</small>
          <strong>{aberto ? r.com_diferenca : dados.produtos_ajustados}</strong>
          <span>{r.nao_contados ? `${r.nao_contados} com saldo sem contar` : "produtos"}</span>
        </div>
      </div>

      {aberto && (
        <div className="cartao cartao-separado inventario-celular">
          <img src={qr} alt="QR Code para contar pelo celular" />
          <div>
            <h2>Conte pelo celular</h2>
            <p className="vazio">
              Aponte a câmera do celular para o código ao lado e entre com o seu usuário. Cada pessoa pode contar uma parte da
              loja ao mesmo tempo. Quem conta não vê o saldo do sistema, para contar de verdade.
            </p>
            <code>{endereco}</code>
          </div>
        </div>
      )}

      <nav className="abas abas-botoes">
        <button type="button" className={filtro === "diferenca" ? "active" : ""} onClick={() => setFiltro("diferenca")}>
          Com diferença
        </button>
        <button type="button" className={filtro === "todos" ? "active" : ""} onClick={() => setFiltro("todos")}>
          Todos
        </button>
        {(dados.nao_contados?.length ?? 0) > 0 && (
          <button type="button" className={filtro === "nao_contados" ? "active" : ""} onClick={() => setFiltro("nao_contados")}>
            Não contados ({dados.nao_contados?.length})
          </button>
        )}
      </nav>

      <div className="cartao cartao-separado">
        <table className="tabela">
          <thead>
            <tr>
              <th>Produto</th>
              <th className="num">Contado</th>
              <th className="num">Sistema</th>
              <th className="num">Diferença</th>
              <th className="num">Custo</th>
              <th className="num">Valor</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((i) => (
              <tr key={i.produto_id} className={i.contado ? "" : "inativo"}>
                <td>
                  {i.nome} {i.apresentacao && <small className="vazio">{i.apresentacao}</small>}
                  <span className="livro-detalhe">
                    {i.ean ?? "sem código"}
                    {!i.contado && " · ninguém contou: vai para zero"}
                  </span>
                </td>
                <td className="num">{fmtQtd(i.quantidade)}</td>
                <td className="num">{i.saldo_sistema !== null ? fmtQtd(i.saldo_sistema) : "-"}</td>
                <td className="num">
                  <Diferenca valor={i.diferenca} />
                </td>
                <td className="num">{i.custo_unitario ? reais(i.custo_unitario) : <span className="vazio">sem custo</span>}</td>
                <td className="num">
                  <Diferenca valor={i.valor_diferenca} dinheiro />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {linhas.length === 0 && (
          <p className="lista-vazia">{filtro === "diferenca" ? "Nenhuma diferença até agora: o contado bate com o sistema." : "Nada contado ainda."}</p>
        )}
        <p className="nota">
          O sistema guarda o saldo na hora em que cada produto é contado. Assim, o que for vendido durante a contagem não vira
          diferença.
        </p>
      </div>

      {aberto && (
        <div className="cartao cartao-separado inventario-fim">
          {confirmar ? (
            <>
              <p>
                {confirmar === "finalizar"
                  ? `O estoque de ${r.com_diferenca ?? 0} produto(s) vai mudar para o que foi contado${r.nao_contados ? `, e ${r.nao_contados} produto(s) que ninguém contou vão para zero` : ""}. Não dá para desfazer.`
                  : "A contagem vai ser descartada e o estoque fica como está."}
              </p>
              <button type="button" className="botao" onClick={() => encerrar(confirmar)}>
                {confirmar === "finalizar" ? "Sim, acertar o estoque" : "Sim, cancelar"}
              </button>
              <button type="button" className="botao-pequeno" onClick={() => setConfirmar(null)}>
                Voltar
              </button>
            </>
          ) : (
            <>
              <p className="vazio">Terminou de contar? Confira as diferenças acima e acerte o estoque.</p>
              <span className="espaco" />
              <button type="button" className="botao-pequeno" onClick={() => setConfirmar("cancelar")}>
                Cancelar contagem
              </button>
              <button type="button" className="botao" disabled={r.produtos_contados === 0} onClick={() => setConfirmar("finalizar")}>
                Finalizar e acertar o estoque
              </button>
            </>
          )}
        </div>
      )}
      {!aberto && (
        <p>
          <button type="button" className="botao-pequeno" onClick={() => navegar("/estoque/inventario")}>
            Voltar para os inventários
          </button>
        </p>
      )}
    </div>
  );
}

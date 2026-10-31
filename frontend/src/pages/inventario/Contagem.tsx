import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { InventarioDetalhe, ItemInventario, Produto } from "../../api/tipos";
import BuscaProduto from "../../components/BuscaProduto";
import Icone from "../../components/Icone";
import { quantidade as fmtQtd } from "../../formato";
import { cuidaDoEstoque, useSessao } from "../../sessao";
import { abrirCamera, avisarLeitura, filtroRepetidas, type Parar } from "./leitorCamera";

type Leitura = { tipo: "ok"; item: ItemInventario; somado: string } | { tipo: "erro"; texto: string };

/** Tela de contagem, feita para o celular: bipa pela câmera, pelo leitor ou digita o código. */
export default function Contagem() {
  const { id } = useParams();
  const { sessao } = useSessao();
  const [inventario, setInventario] = useState<InventarioDetalhe | null>(null);
  const [erro, setErro] = useState("");
  const [codigo, setCodigo] = useState("");
  const [porLeitura, setPorLeitura] = useState("1");
  const [leitura, setLeitura] = useState<Leitura | null>(null);
  const [camera, setCamera] = useState(false);
  const [erroCamera, setErroCamera] = useState("");
  const [buscar, setBuscar] = useState(false);
  const [editando, setEditando] = useState<{ produtoId: string; valor: string } | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const parar = useRef<Parar | null>(null);
  const campo = useRef<HTMLInputElement>(null);
  const repetida = useRef(filtroRepetidas());
  const ocupado = useRef(false);

  const recarregar = useCallback(() => {
    api<InventarioDetalhe>(`/inventarios/${id}`)
      .then(setInventario)
      .catch((e) => setErro(mensagem(e)));
  }, [id]);

  useEffect(recarregar, [recarregar]);

  const contar = useCallback(
    async (corpo: { codigo?: string; produto_id?: string; quantidade?: string; modo?: "somar" | "definir" }) => {
      const somado = corpo.quantidade ?? (porLeitura.replace(",", ".") || "1");
      try {
        const item = await api<ItemInventario>(`/inventarios/${id}/contar`, { corpo: { quantidade: somado, ...corpo } });
        setLeitura({ tipo: "ok", item, somado: corpo.modo === "definir" ? "" : somado });
        avisarLeitura(true);
        recarregar();
      } catch (e) {
        setLeitura({ tipo: "erro", texto: mensagem(e) });
        avisarLeitura(false);
      }
    },
    [id, porLeitura, recarregar],
  );

  // A câmera chama a leitura a cada quadro: uma de cada vez e sem repetir a mesma caixa.
  const contarRef = useRef(contar);
  contarRef.current = contar;
  const aoLerCamera = useCallback((lido: string) => {
    if (ocupado.current || !repetida.current(lido)) return;
    ocupado.current = true;
    void contarRef.current({ codigo: lido }).finally(() => {
      ocupado.current = false;
    });
  }, []);

  useEffect(() => {
    if (!camera || !video.current) return;
    let cancelado = false;
    setErroCamera("");
    abrirCamera(video.current, aoLerCamera)
      .then((p) => {
        if (cancelado) p();
        else parar.current = p;
      })
      .catch((e) => {
        setErroCamera(e instanceof Error ? e.message : String(e));
        setCamera(false);
      });
    return () => {
      cancelado = true;
      parar.current?.();
      parar.current = null;
    };
  }, [camera, aoLerCamera]);

  function enviarCodigo(e: React.FormEvent) {
    e.preventDefault();
    const lido = codigo.trim();
    if (!lido) return;
    setCodigo("");
    void contar({ codigo: lido });
    campo.current?.focus();
  }

  async function remover(item: ItemInventario) {
    try {
      await api(`/inventarios/${id}/itens/${item.produto_id}`, { metodo: "DELETE" });
      recarregar();
    } catch (e) {
      setLeitura({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (erro) return <p className="erro contagem">{erro}</p>;
  if (!inventario) return <p className="contagem">Carregando...</p>;

  const encerrado = inventario.status !== "aberto";
  const contados = inventario.itens.filter((i) => i.contado);

  return (
    <div className="contagem">
      <header className="contagem-topo">
        <Link to={cuidaDoEstoque(sessao) ? `/estoque/inventario/${id}` : "/estoque/inventario"} aria-label="Voltar">
          <Icone nome="voltar" />
        </Link>
        <div>
          <strong>{inventario.descricao}</strong>
          <small>
            {inventario.loja_nome} · {inventario.resumo.produtos_contados} produto(s), {fmtQtd(inventario.resumo.unidades_contadas)} un.
          </small>
        </div>
      </header>

      {encerrado ? (
        <p className="erro">Esta contagem já foi encerrada.</p>
      ) : (
        <>
          <div className={`contagem-camera ${camera ? "ligada" : ""}`}>
            <video ref={video} muted playsInline />
            {camera && <div className="contagem-mira" />}
          </div>
          <button type="button" className={camera ? "botao-contorno contagem-botao" : "botao contagem-botao"} onClick={() => setCamera(!camera)}>
            <Icone nome="camera" /> {camera ? "Desligar a câmera" : "Ler com a câmera"}
          </button>
          {erroCamera && <p className="erro">{erroCamera}</p>}

          <form className="contagem-codigo" onSubmit={enviarCodigo}>
            <input
              ref={campo}
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              placeholder="Código de barras"
              inputMode="numeric"
              autoFocus={!camera}
              aria-label="Código de barras"
            />
            <button type="submit" className="botao">
              Contar
            </button>
          </form>

          <div className="contagem-por-leitura">
            <span>Cada leitura soma</span>
            <button type="button" className="botao-pequeno" onClick={() => setPorLeitura(String(Math.max(1, Number(porLeitura) - 1)))}>
              −
            </button>
            <input
              value={porLeitura}
              onChange={(e) => setPorLeitura(e.target.value.replace(/[^\d,]/g, ""))}
              inputMode="decimal"
              aria-label="Quantidade por leitura"
            />
            <button type="button" className="botao-pequeno" onClick={() => setPorLeitura(String(Number(porLeitura) + 1))}>
              +
            </button>
            <span>un.</span>
          </div>

          {leitura && (
            <div className={`contagem-leitura ${leitura.tipo}`} role="status">
              {leitura.tipo === "ok" ? (
                <>
                  <span>
                    {leitura.somado ? `+${fmtQtd(leitura.somado)} ` : ""}
                    {leitura.item.nome} {leitura.item.apresentacao}
                  </span>
                  <strong>{fmtQtd(leitura.item.quantidade)}</strong>
                </>
              ) : (
                <span>{leitura.texto}</span>
              )}
            </div>
          )}

          {buscar ? (
            <div className="contagem-busca">
              <BuscaProduto
                autoFocus
                aoEscolher={(p: Produto) => {
                  setBuscar(false);
                  void contar({ produto_id: p.id });
                }}
              />
            </div>
          ) : (
            <button type="button" className="botao-pequeno" onClick={() => setBuscar(true)}>
              Produto sem código? Buscar pelo nome
            </button>
          )}
        </>
      )}

      <h2 className="contagem-titulo">Já contados</h2>
      {contados.length === 0 && <p className="vazio">Nada contado ainda. Comece bipando um produto.</p>}
      <ul className="contagem-lista">
        {contados.map((item) => (
          <li key={item.produto_id}>
            <div>
              <strong>{item.nome}</strong>
              <small>{[item.apresentacao, item.ean].filter(Boolean).join(" · ")}</small>
            </div>
            {editando?.produtoId === item.produto_id ? (
              <form
                className="contagem-editar"
                onSubmit={(e) => {
                  e.preventDefault();
                  void contar({ produto_id: item.produto_id, quantidade: editando.valor.replace(",", ".") || "0", modo: "definir" });
                  setEditando(null);
                }}
              >
                <input autoFocus inputMode="decimal" value={editando.valor} onChange={(e) => setEditando({ ...editando, valor: e.target.value })} aria-label={`Total de ${item.nome}`} />
                <button type="submit" className="botao-pequeno">
                  OK
                </button>
              </form>
            ) : (
              <div className="contagem-acoes">
                {!encerrado && (
                  <button type="button" className="botao-pequeno" aria-label={`Tirar um de ${item.nome}`} onClick={() => void contar({ produto_id: item.produto_id, quantidade: "-1" })}>
                    −
                  </button>
                )}
                <button
                  type="button"
                  className="contagem-qtd"
                  disabled={encerrado}
                  onClick={() => setEditando({ produtoId: item.produto_id, valor: fmtQtd(item.quantidade) })}
                  title="Tocar para corrigir o total"
                >
                  {fmtQtd(item.quantidade)}
                </button>
                {!encerrado && (
                  <>
                    <button type="button" className="botao-pequeno" aria-label={`Somar um em ${item.nome}`} onClick={() => void contar({ produto_id: item.produto_id, quantidade: "1" })}>
                      +
                    </button>
                    <button type="button" className="botao-pequeno" aria-label={`Apagar ${item.nome}`} onClick={() => void remover(item)}>
                      <Icone nome="lixo" tamanho={14} />
                    </button>
                  </>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="nota">
        Toque no número para corrigir o total. Várias pessoas podem contar ao mesmo tempo, cada uma no seu celular.
      </p>
    </div>
  );
}

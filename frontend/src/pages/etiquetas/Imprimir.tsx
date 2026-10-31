import { useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { EtiquetaItem } from "../../api/tipos";
import { data, reais } from "../../formato";
import { barrasEan } from "./codigoDeBarras";
import { CHAVE_IMPRESSAO, MODELOS, type Impressao, type Modelo } from "./Etiquetas";

function lerImpressao(): Impressao | null {
  try {
    const salvo = sessionStorage.getItem(CHAVE_IMPRESSAO);
    return salvo ? (JSON.parse(salvo) as Impressao) : null;
  } catch {
    return null;
  }
}

function CodigoDeBarras({ codigo }: { codigo: string }) {
  const barras = barrasEan(codigo);
  if (!barras) return <span className="etq-codigo-texto">{codigo}</span>;
  // 9 módulos de margem de cada lado, como pede o padrão.
  const largura = barras.length + 18;
  return (
    <svg className="etq-barras" viewBox={`0 0 ${largura} 34`} preserveAspectRatio="none" role="img" aria-label={codigo}>
      {[...barras].map((b, i) => (b === "1" ? <rect key={i} x={i + 9} y={0} width={1} height={26} /> : null))}
      <text x={largura / 2} y={33} textAnchor="middle" fontSize={7}>
        {codigo}
      </text>
    </svg>
  );
}

function Etiqueta({ item, modelo }: { item: EtiquetaItem; modelo: Modelo }) {
  const promocional = item.preco_promocional;
  const precoFinal = promocional ?? item.preco;
  const [reaisInteiros, centavos] = Number(precoFinal).toFixed(2).split(".");
  return (
    <div className={`etq etq-${modelo} ${promocional || item.promocao ? "etq-promo" : ""}`}>
      {modelo === "oferta" && (promocional || item.promocao) && <div className="etq-faixa">Oferta</div>}
      <div className="etq-nome">{item.nome}</div>
      {item.apresentacao && <div className="etq-apresentacao">{item.apresentacao}</div>}
      {promocional && <div className="etq-de">De {reais(item.preco)}</div>}
      <div className="etq-preco">
        {promocional && <span className="etq-por">por </span>}
        <small>R$</small>
        {Number(reaisInteiros).toLocaleString("pt-BR")}
        <small>,{centavos}</small>
      </div>
      {!promocional && item.promocao && <div className="etq-leve">{item.promocao}</div>}
      {modelo === "oferta" && item.promocao_fim && <div className="etq-validade">Oferta válida até {data(item.promocao_fim)}</div>}
      {modelo === "codigo" && item.ean && <CodigoDeBarras codigo={item.ean} />}
    </div>
  );
}

/** Folha de etiquetas para imprimir (aberta numa aba nova pela tela de Etiquetas). */
export default function Imprimir() {
  const [impressao] = useState(lerImpressao);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [marcado, setMarcado] = useState(false);

  if (!impressao) return <p className="vazio etq-folha">Nada para imprimir. Escolha as etiquetas na tela Etiquetas de preço.</p>;

  const etiquetas = impressao.itens.flatMap((item) => Array.from({ length: item.copias }, () => item));
  const modelo = MODELOS.find((m) => m.valor === impressao.modelo);

  async function marcar() {
    if (!impressao) return;
    try {
      await api("/etiquetas/impressas", {
        corpo: { loja_id: impressao.lojaId, produto_ids: impressao.itens.map((i) => i.produto_id) },
      });
      setMarcado(true);
      setAviso({ tipo: "ok", texto: "Pronto! Essas etiquetas saíram da lista do que trocar. Pode fechar esta aba." });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  return (
    <div className="etq-folha">
      <div className="nao-imprimir etq-topo">
        <div>
          <strong>
            {etiquetas.length} etiqueta(s) · {modelo?.nome}
          </strong>
          <small>Use papel A4 e, na janela de impressão, deixe a escala em 100% (tamanho real).</small>
        </div>
        <button type="button" className="botao" onClick={() => window.print()}>
          Imprimir
        </button>
        <button type="button" className="botao-pequeno" disabled={marcado} onClick={marcar}>
          Já imprimi: marcar como trocadas
        </button>
        {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}
      </div>
      <div className={`etq-grade etq-grade-${impressao.modelo}`}>
        {etiquetas.map((item, i) => (
          <Etiqueta key={`${item.produto_id}-${i}`} item={item} modelo={impressao.modelo} />
        ))}
      </div>
    </div>
  );
}

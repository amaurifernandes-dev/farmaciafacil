import { useEffect, useState, type FormEvent } from "react";

import { api, baixar, mensagem } from "../../api/cliente";
import type { ResumoControlados, SaldoControlado } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, quantidade } from "../../formato";
import { useLojas } from "../../lojas";

/** Códigos de perda do SNGPC. */
export const MOTIVOS_PERDA: { codigo: number; nome: string }[] = [
  { codigo: 3, nome: "Vencimento" },
  { codigo: 2, nome: "Avaria (quebrou, amassou)" },
  { codigo: 1, nome: "Furto ou roubo" },
  { codigo: 10, nome: "Devolução ao fornecedor" },
  { codigo: 9, nome: "Recolhimento do fabricante" },
  { codigo: 4, nome: "Apreensão pela Vigilância Sanitária" },
  { codigo: 8, nome: "Desvio de qualidade" },
  { codigo: 6, nome: "Controle de qualidade" },
  { codigo: 5, nome: "Perda no processo" },
  { codigo: 7, nome: "Saiu da Portaria 344" },
];

const NOMES_TIPO: Record<string, string> = {
  entrada: "Entrada",
  venda: "Venda",
  perda: "Perda",
  transferencia: "Transferência",
  devolucao: "Devolução",
  ajuste: "Ajuste",
};

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function lista(valor: string): string {
  return valor === "ATB" ? "Antibiótico" : `Lista ${valor}`;
}

export default function Controlados() {
  const lojas = useLojas();
  const agora = new Date();
  const [inicio, setInicio] = useState(iso(new Date(agora.getFullYear(), agora.getMonth(), 1)));
  const [fim, setFim] = useState(iso(agora));
  const [lojaId, setLojaId] = useState("");
  const [resumo, setResumo] = useState<ResumoControlados | null>(null);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  const filtro = `inicio=${inicio}&fim=${fim}${lojaId ? `&loja_id=${lojaId}` : ""}`;

  useEffect(() => {
    if (!lojaId && lojas.length) setLojaId(lojas.find((l) => l.matriz)?.id ?? lojas[0].id);
  }, [lojas, lojaId]);

  useEffect(() => {
    if (!inicio || !fim) return;
    api<ResumoControlados>(`/controlados?${filtro}`)
      .then((dados) => {
        setResumo(dados);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }, [filtro, versao]);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Portaria 344 e antibióticos</p>
          <h1>Remédios controlados</h1>
          <p className="vazio">
            O livro de cada remédio controlado: o que entrou pela nota, o que saiu com receita e o que se perdeu. E os
            arquivos para mandar ao SNGPC da Anvisa.
          </p>
        </div>
      </div>

      <div className="barra filtros-relatorio">
        <label className="seletor-loja">
          De
          <input type="date" value={inicio} max={fim} onChange={(e) => setInicio(e.target.value)} />
        </label>
        <label className="seletor-loja">
          Até
          <input type="date" value={fim} min={inicio} max={iso(agora)} onChange={(e) => setFim(e.target.value)} />
        </label>
        {lojas.length > 1 && <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} />}
      </div>

      {erro && <p className="erro">{erro}</p>}
      {!resumo && !erro && <p className="vazio">Carregando...</p>}
      {resumo && (
        <>
          <Pendencias resumo={resumo} />
          <div className="indicadores indicadores-financeiro">
            <Indicador rotulo="Entradas" valor={resumo.totais.entradas} detalhe="caixas e frascos no período" />
            <Indicador rotulo="Vendas" valor={resumo.totais.vendas} detalhe="com receita" />
            <Indicador rotulo="Perdas" valor={resumo.totais.perdas} detalhe="com o motivo da Anvisa" />
            <Indicador rotulo="Transferências" valor={resumo.totais.transferencias} detalhe="para outras lojas" />
          </div>
          <Anvisa resumo={resumo} filtro={filtro} />
          <Saldos saldos={resumo.saldos} aoMudar={() => setVersao((v) => v + 1)} />
          <Livro resumo={resumo} />
        </>
      )}
    </div>
  );
}

function Indicador({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe: string }) {
  return (
    <div className="cartao indicador">
      <small>{rotulo}</small>
      <strong>{quantidade(valor)}</strong>
      <span>{detalhe}</span>
    </div>
  );
}

function Pendencias({ resumo }: { resumo: ResumoControlados }) {
  if (resumo.pendencias.length === 0) {
    return (
      <div className="cartao fechamento-ok">
        <Icone nome="entrada" />
        <div>
          <strong>Tudo certo para mandar à Anvisa</strong>
          <p>
            As movimentações de {data(resumo.inicio)} a {data(resumo.fim)} têm nota, receita ou motivo.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <h2>Acertar antes de mandar</h2>
      </div>
      <ul className="avisos">
        {resumo.pendencias.map((p) => (
          <li key={p.codigo}>
            <span className="aviso-icone">
              <Icone nome="alerta" />
            </span>
            <div>
              <p className="texto-pendencia">
                {p.bloqueia && <strong>Obrigatório: </strong>}
                {p.texto}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Anvisa({ resumo, filtro }: { resumo: ResumoControlados; filtro: string }) {
  const [baixando, setBaixando] = useState("");
  const [erro, setErro] = useState("");
  const bloqueado = resumo.pendencias.some((p) => p.bloqueia);

  async function arquivo(tipo: "sngpc" | "inventario") {
    setBaixando(tipo);
    setErro("");
    try {
      await baixar(tipo === "sngpc" ? `/controlados/sngpc?${filtro}` : `/controlados/inventario?loja_id=${resumo.loja_id}`);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setBaixando("");
    }
  }

  return (
    <div className="cartao cartao-separado">
      <div className="cartao-cabecalho">
        <h2>Mandar para o SNGPC</h2>
        <small>
          {data(resumo.inicio)} a {data(resumo.fim)}
        </small>
      </div>
      <p className="vazio">
        O farmacêutico entra no site do SNGPC com o login dele e envia o arquivo. Na primeira vez, mande o inventário
        (o saldo de hoje); depois, a movimentação de cada período, sem pular dias.
      </p>
      <div className="acoes">
        <button type="button" className="botao" disabled={!!baixando || bloqueado} onClick={() => arquivo("sngpc")}>
          <Icone nome="baixa" />
          {baixando === "sngpc" ? "Preparando..." : "Arquivo de movimentação (XML)"}
        </button>
        <button type="button" className="botao-pequeno" disabled={!!baixando || bloqueado} onClick={() => arquivo("inventario")}>
          {baixando === "inventario" ? "Preparando..." : "Inventário de hoje (XML)"}
        </button>
      </div>
      {bloqueado && <p className="nota">Resolva o que está marcado como obrigatório para liberar os arquivos.</p>}
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}

function Saldos({ saldos, aoMudar }: { saldos: SaldoControlado[]; aoMudar: () => void }) {
  const [perda, setPerda] = useState<SaldoControlado | null>(null);

  return (
    <div className="cartao cartao-separado">
      <div className="cartao-cabecalho">
        <h2>Saldo por lote</h2>
        <small>hoje</small>
      </div>
      {perda && (
        <Perda
          lote={perda}
          aoFechar={(salvou) => {
            setPerda(null);
            if (salvou) aoMudar();
          }}
        />
      )}
      <table className="tabela">
        <thead>
          <tr>
            <th>Remédio</th>
            <th>Lista</th>
            <th>Registro MS</th>
            <th>Lote</th>
            <th>Validade</th>
            <th className="num">Saldo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {saldos.map((s) => (
            <tr key={s.lote_id}>
              <td>{s.produto}</td>
              <td>{lista(s.lista)}</td>
              <td>{s.registro_ms ?? <span className="erro-texto">falta</span>}</td>
              <td>{s.lote}</td>
              <td>{data(s.validade)}</td>
              <td className="num">{quantidade(s.quantidade)}</td>
              <td className="num">
                <button type="button" className="botao-pequeno" onClick={() => setPerda(s)}>
                  Registrar perda
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {saldos.length === 0 && <p className="lista-vazia">Nenhum remédio controlado com saldo nesta loja.</p>}
    </div>
  );
}

function Perda({ lote, aoFechar }: { lote: SaldoControlado; aoFechar: (salvou: boolean) => void }) {
  const [qtd, setQtd] = useState("1");
  const [motivoSngpc, setMotivoSngpc] = useState(3);
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await api("/estoque/perdas", {
        corpo: { lote_id: lote.lote_id, quantidade: qtd, motivo_sngpc: motivoSngpc, motivo: motivo.trim() },
      });
      aoFechar(true);
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <form className="formulario cartao-interno" onSubmit={salvar}>
      <h2>
        Perda de {lote.produto} · lote {lote.lote}
      </h2>
      <label>
        Quantas caixas ou frascos
        <input value={qtd} onChange={(e) => setQtd(e.target.value.replace(/\D/g, ""))} inputMode="numeric" required autoFocus />
      </label>
      <label>
        Motivo para a Anvisa
        <select value={motivoSngpc} onChange={(e) => setMotivoSngpc(Number(e.target.value))}>
          {MOTIVOS_PERDA.map((m) => (
            <option key={m.codigo} value={m.codigo}>
              {m.nome}
            </option>
          ))}
        </select>
      </label>
      <label>
        O que aconteceu
        <input value={motivo} onChange={(e) => setMotivo(e.target.value)} required minLength={3} placeholder="ex.: caixa molhada" />
      </label>
      {erro && <p className="erro">{erro}</p>}
      <div className="acoes">
        <button type="submit">Registrar perda</button>
        <button type="button" onClick={() => aoFechar(false)}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function Livro({ resumo }: { resumo: ResumoControlados }) {
  return (
    <div className="cartao cartao-separado">
      <div className="cartao-cabecalho">
        <h2>Livro de controlados</h2>
        <small>{resumo.livro.length} movimento(s)</small>
      </div>
      <table className="tabela">
        <thead>
          <tr>
            <th>Data</th>
            <th>Remédio</th>
            <th>Lote</th>
            <th>Movimento</th>
            <th className="num">Entrou</th>
            <th className="num">Saiu</th>
            <th className="num">Saldo</th>
            <th>Documento</th>
          </tr>
        </thead>
        <tbody>
          {resumo.livro.map((l, i) => (
            <tr key={i}>
              <td>{new Date(l.data).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</td>
              <td>
                {l.produto}
                <span className="livro-detalhe">{lista(l.lista)}</span>
              </td>
              <td>{l.lote}</td>
              <td>
                <span className={`livro-tipo ${l.tipo}`}>{NOMES_TIPO[l.tipo] ?? l.tipo}</span>
              </td>
              <td className="num">{Number(l.entrada) ? quantidade(l.entrada) : ""}</td>
              <td className="num">{Number(l.saida) ? quantidade(l.saida) : ""}</td>
              <td className="num">{quantidade(l.saldo)}</td>
              <td>
                {l.documento}
                {l.receita && <span className="livro-detalhe">{l.receita}</span>}
                {l.pessoa && <span className="livro-detalhe">Para {l.pessoa}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {resumo.livro.length === 0 && <p className="lista-vazia">Nenhum movimento de controlado no período.</p>}
    </div>
  );
}

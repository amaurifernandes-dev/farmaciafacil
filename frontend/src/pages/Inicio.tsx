import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../api/cliente";
import type { Andamento, Painel, Sessao } from "../api/tipos";
import Icone, { type NomeIcone } from "../components/Icone";
import { data, quantidade, reais } from "../formato";
import { useModulos } from "../modulos";
import { ehGerente, podeReceber, useSessao } from "../sessao";
import { moduloDoEndereco } from "../telas";
import { BarraMeta, pct, Recado, SITUACOES } from "./metas/BarraMeta";

/** Se o endereço é de uma função ligada no Gerenciamento de telas (desligada, o quadro some). */
const LinkLigado = createContext<(para: string) => boolean>(() => true);

const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

/** Data ISO (AAAA-MM-DD) como Date local, sem cair no dia anterior por causa do fuso. */
function diaLocal(iso: string): Date {
  const [ano, mes, dia] = iso.split("-").map(Number);
  return new Date(ano, mes - 1, dia);
}

/** Variação percentual de hoje em relação a ontem; null quando ontem não teve venda. */
export function variacao(hoje: number, ontem: number): number | null {
  return ontem > 0 ? ((hoje - ontem) / ontem) * 100 : null;
}

export type Perfil = "gerencia" | "farmaceutico" | "estoque" | "balcao";

/** Qual painel cada perfil vê ao entrar. */
export function perfilDoPainel(sessao: Sessao | null): Perfil {
  if (ehGerente(sessao)) return "gerencia";
  if (sessao?.papel === "farmaceutico") return "farmaceutico";
  if (sessao?.papel === "estoque") return "estoque";
  return "balcao";
}

/** "há 5 min", "há 2 h": quanto tempo uma pré-venda está esperando. */
export function haQuanto(iso: string, agora: Date = new Date()): string {
  const minutos = Math.max(0, Math.floor((agora.getTime() - new Date(iso).getTime()) / 60000));
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  return horas < 24 ? `há ${horas} h` : `há ${Math.floor(horas / 24)} dia(s)`;
}

function saudacao(agora: Date = new Date()): string {
  const hora = agora.getHours();
  return hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
}

const hora = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const SUBTITULO: Record<Perfil, string> = {
  gerencia: "Os números da farmácia e o que precisa da sua decisão hoje.",
  farmaceutico: "Balcão, controlados e validades: o que pede a sua atenção hoje.",
  estoque: "O que repor, o que está vencendo e o que está chegando.",
  balcao: "Seu caixa, as pré-vendas esperando e as suas vendas de hoje.",
};

export default function Inicio() {
  const { sessao } = useSessao();
  const { ligado } = useModulos(sessao);
  const linkLigado = (para: string) => {
    const modulo = moduloDoEndereco(para);
    return !modulo || ligado(modulo);
  };
  const [painel, setPainel] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Painel>("/painel")
      .then(setPainel)
      .catch((e) => setErro(mensagem(e)));
  }, []);

  if (erro) return <p className="erro">{erro}</p>;
  if (!painel) return <p>Carregando...</p>;

  const perfil = perfilDoPainel(sessao);
  const primeiroNome = sessao?.nome.split(" ")[0] ?? "";
  const dataPorExtenso = diaLocal(painel.hoje).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <LinkLigado.Provider value={linkLigado}>
      <div className="inicio">
        <p className="sobretitulo">
          {dataPorExtenso} · {painel.farmacia}
        </p>
        <div className="inicio-titulo">
          <div>
            <h1>
              {saudacao()}, {primeiroNome}.
            </h1>
            <p className="vazio">{SUBTITULO[perfil]}</p>
          </div>
          <AcaoPrincipal perfil={perfil} painel={painel} sessao={sessao} />
        </div>

        {perfil === "gerencia" && <PainelGerencia painel={painel} />}
        {perfil === "farmaceutico" && <PainelFarmaceutico painel={painel} />}
        {perfil === "estoque" && <PainelEstoque painel={painel} />}
        {perfil === "balcao" && <PainelBalcao painel={painel} />}
      </div>
    </LinkLigado.Provider>
  );
}

function AcaoPrincipal({ perfil, painel, sessao }: { perfil: Perfil; painel: Painel; sessao: Sessao | null }) {
  if (perfil === "estoque")
    return (
      <Link to="/compras" className="botao">
        <Icone nome="entrada" /> Importar nota
      </Link>
    );
  if (podeReceber(sessao) && !painel.meu_caixa_aberto && perfil === "balcao")
    return (
      <Link to="/caixas" className="botao">
        <Icone nome="caixa" /> Abrir meu caixa
      </Link>
    );
  if (sessao?.papel === "atendente")
    return (
      <Link to="/vendas/pre-venda" className="botao">
        <Icone nome="mais" /> Nova pré-venda
      </Link>
    );
  return (
    <Link to="/vendas" className="botao">
      <Icone nome="mais" /> Nova venda
    </Link>
  );
}

// --- Painéis de cada perfil ---

function PainelGerencia({ painel }: { painel: Painel }) {
  const comparacao = variacao(Number(painel.vendas_hoje), Number(painel.vendas_ontem));
  const g = painel.gestao;
  return (
    <>
      <div className="indicadores espaco-acima">
        <Indicador titulo="Vendas de hoje" icone="dinheiro" valor={reais(painel.vendas_hoje)} para="/relatorios">
          {comparacao === null ? (
            "Sem vendas ontem para comparar"
          ) : (
            <span className={comparacao >= 0 ? "positivo" : "negativo"}>
              <Icone nome={comparacao >= 0 ? "subida" : "descida"} tamanho={12} />{" "}
              {Math.abs(comparacao).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% em relação a ontem
            </span>
          )}
        </Indicador>
        <Indicador titulo="Vendas realizadas" icone="recibo" valor={String(painel.quantidade_vendas_hoje)} para="/vendas">
          Ticket médio de {reais(painel.ticket_medio_hoje)}
        </Indicador>
        <Indicador titulo="Caixas abertos" icone="caixa" valor={String(painel.caixas_abertos)} para="/caixas">
          {painel.meu_caixa_aberto ? "Seu caixa está aberto" : "Seu caixa está fechado"}
        </Indicador>
        {g && (
          <Indicador
            titulo="Contas vencidas"
            icone="alerta"
            valor={reais(g.pagar_vencidas.total)}
            para="/financeiro"
            alerta={g.pagar_vencidas.quantidade > 0}
          >
            {g.pagar_vencidas.quantidade === 0
              ? "Nenhuma conta a pagar atrasada"
              : `${g.pagar_vencidas.quantidade} conta(s) a pagar atrasada(s)`}
            {g.pagar_hoje.quantidade > 0 && ` · ${reais(g.pagar_hoje.total)} vence hoje`}
          </Indicador>
        )}
      </div>

      <Metas painel={painel} link="/metas" />

      <div className="inicio-grade">
        <section className="cartao">
          <div className="cartao-cabecalho">
            <h2>Vendas da semana</h2>
            <small>Últimos 7 dias</small>
          </div>
          <GraficoSemana semana={painel.semana} />
          <div className="atalhos atalhos-4">
            <Atalho para="/relatorios" icone="grafico" rotulo="Relatórios" />
            <Atalho para="/financeiro" icone="dinheiro" rotulo="Financeiro" />
            <Atalho para="/compras/sugestao" icone="caminhao" rotulo="O que comprar" />
            <Atalho para="/promocoes" icone="etiqueta" rotulo="Promoções" />
          </div>
        </section>

        <section className="cartao">
          <h2>Precisa de atenção</h2>
          <Atencao painel={painel} />
        </section>
      </div>
    </>
  );
}

function PainelBalcao({ painel }: { painel: Painel }) {
  const { sessao } = useSessao();
  const b = painel.balcao;
  if (!b) return null;
  const recebe = podeReceber(sessao);
  return (
    <>
      <div className="indicadores espaco-acima">
        {recebe && <IndicadorMeuCaixa painel={painel} />}
        <Indicador titulo="Pré-vendas esperando" icone="carrinho" valor={String(b.pre_vendas_abertas)} para="/vendas">
          {b.pre_vendas_abertas === 0 ? "Ninguém esperando no caixa" : "Clientes aguardando para pagar"}
        </Indicador>
        <Indicador titulo="Minhas vendas hoje" icone="recibo" valor={String(b.minhas_vendas_hoje.quantidade)} para="/comissoes">
          {reais(b.minhas_vendas_hoje.total)} vendidos por você
        </Indicador>
        <Indicador titulo="Encomendas chegaram" icone="sino" valor={String(painel.encomendas_chegaram)} para="/faltas">
          {painel.encomendas_chegaram ? "Avise os clientes" : "Nada para avisar agora"}
        </Indicador>
      </div>

      <Metas painel={painel} />

      <div className="inicio-grade">
        <PreVendas painel={painel} />
        <section className="cartao">
          <h2>Acesso rápido</h2>
          <div className="atalhos">
            <Atalho para="/vendas/pre-venda" icone="mais" rotulo="Nova pré-venda" />
            {recebe && <Atalho para="/pdv" icone="caixa" rotulo="Ir para o caixa" />}
            <Atalho para="/clientes" icone="pessoa" rotulo="Clientes" />
            <Atalho para="/faltas" icone="sino" rotulo="Anotar falta" />
          </div>
          <h2>Precisa de atenção</h2>
          <Atencao painel={painel} />
        </section>
      </div>
    </>
  );
}

function PainelEstoque({ painel }: { painel: Painel }) {
  const e = painel.estoque;
  if (!e) return null;
  return (
    <>
      <div className="indicadores espaco-acima">
        <Indicador
          titulo="Abaixo do mínimo"
          icone="baixa"
          valor={String(painel.abaixo_do_minimo)}
          para="/estoque"
          alerta={painel.abaixo_do_minimo > 0}
        >
          Produtos para repor
        </Indicador>
        <Indicador
          titulo="Vencendo"
          icone="relogio"
          valor={String(painel.lotes_vencendo)}
          para="/estoque"
          alerta={painel.lotes_vencendo > 0}
        >
          Lotes que vencem em até {painel.dias_alerta_vencimento} dias
          {painel.lotes_vencidos > 0 && ` · ${painel.lotes_vencidos} já vencido(s)`}
        </Indicador>
        <Indicador titulo="Notas para conferir" icone="entrada" valor={String(e.notas_para_conferir)} para="/compras">
          {e.notas_para_conferir ? "Confira e dê entrada no estoque" : "Nenhuma nota esperando"}
        </Indicador>
        <Indicador titulo="Pedidos de compra" icone="caminhao" valor={String(e.pedidos_compra_abertos)} para="/compras/pedidos">
          {e.pedidos_compra_abertos ? "Esperando a nota do fornecedor" : "Nenhum pedido em aberto"}
        </Indicador>
      </div>

      <div className="grade-dupla">
        <ListaRepor painel={painel} />
        <ListaVencendo painel={painel} />
      </div>

      <section className="cartao espaco-acima">
        <h2>Acesso rápido</h2>
        <div className="atalhos atalhos-4">
          <Atalho para="/compras/sugestao" icone="caminhao" rotulo="O que comprar" />
          <Atalho para="/estoque/inventario" icone="pacote" rotulo="Inventário" />
          <Atalho para="/etiquetas" icone="etiqueta" rotulo="Etiquetas" />
          <Atalho para="/faltas" icone="sino" rotulo={`Encomendas (${e.encomendas_pendentes})`} />
        </div>
      </section>
    </>
  );
}

function PainelFarmaceutico({ painel }: { painel: Painel }) {
  const f = painel.farmacia_bloco;
  const b = painel.balcao;
  return (
    <>
      <div className="indicadores espaco-acima">
        <IndicadorMeuCaixa painel={painel} />
        <Indicador titulo="Pré-vendas esperando" icone="carrinho" valor={String(b?.pre_vendas_abertas ?? 0)} para="/vendas">
          {b?.pre_vendas_abertas ? "Clientes aguardando para pagar" : "Ninguém esperando no caixa"}
        </Indicador>
        <Indicador titulo="Controlados hoje" icone="remedio" valor={String(f?.controlados_hoje ?? 0)} para="/controlados">
          Vendas com receita retida
        </Indicador>
        <Indicador titulo="Serviços hoje" icone="estetoscopio" valor={String(f?.atendimentos_hoje ?? 0)} para="/servicos">
          Pressão, glicemia, injetáveis
        </Indicador>
      </div>

      <Metas painel={painel} />

      <div className="grade-dupla">
        <ListaVencendo painel={painel} />
        <section className="cartao">
          <h2>Precisa de atenção</h2>
          <Atencao painel={painel} />
        </section>
      </div>
      {b && b.pre_vendas.length > 0 && (
        <div className="espaco-acima">
          <PreVendas painel={painel} />
        </div>
      )}
    </>
  );
}

// --- Peças ---

function Indicador(props: {
  titulo: string;
  icone: NomeIcone;
  valor: string;
  children: ReactNode;
  para?: string;
  alerta?: boolean;
}) {
  const linkLigado = useContext(LinkLigado);
  if (props.para && !linkLigado(props.para)) return null;
  const conteudo = (
    <>
      <div className="cartao-cabecalho">
        <span>{props.titulo}</span>
        <Icone nome={props.icone} tamanho={16} />
      </div>
      <strong>{props.valor}</strong>
      <small>{props.children}</small>
    </>
  );
  const classe = `cartao indicador${props.alerta ? " indicador-alerta" : ""}`;
  return props.para ? (
    <Link to={props.para} className={`${classe} indicador-link`}>
      {conteudo}
    </Link>
  ) : (
    <div className={classe}>{conteudo}</div>
  );
}

function IndicadorMeuCaixa({ painel }: { painel: Painel }) {
  const caixa = painel.balcao?.meu_caixa;
  return caixa ? (
    <Indicador titulo="Meu caixa" icone="caixa" valor={reais(caixa.total)} para="/pdv">
      Aberto às {hora(caixa.aberto_em)} · {caixa.vendas} venda(s)
    </Indicador>
  ) : (
    <Indicador titulo="Meu caixa" icone="caixa" valor="Fechado" para="/caixas" alerta>
      Abra o caixa para começar a receber
    </Indicador>
  );
}

function Metas({ painel, link }: { painel: Painel; link?: string }) {
  const linkLigado = useContext(LinkLigado);
  if (!linkLigado("/metas")) return null;
  if (!painel.meta_farmacia && !painel.minha_meta) return null;
  return (
    <div className="metas-inicio">
      {painel.minha_meta && <CartaoMeta titulo="Sua meta do mês" andamento={painel.minha_meta} hoje={painel.hoje} />}
      {painel.meta_farmacia && (
        <CartaoMeta titulo="Meta da farmácia no mês" andamento={painel.meta_farmacia} hoje={painel.hoje} link={link} />
      )}
    </div>
  );
}

function PreVendas({ painel }: { painel: Painel }) {
  const b = painel.balcao;
  if (!b) return null;
  return (
    <section className="cartao">
      <div className="cartao-cabecalho">
        <h2>Pré-vendas esperando pagamento</h2>
        {b.pre_vendas_abertas > b.pre_vendas.length && <small>mostrando as {b.pre_vendas.length} mais antigas</small>}
      </div>
      {b.pre_vendas.length === 0 ? (
        <p className="vazio">Nenhuma pré-venda esperando. Quando o balcão separar os produtos, ela aparece aqui.</p>
      ) : (
        <ul className="lista-painel">
          {b.pre_vendas.map((p) => (
            <li key={p.id}>
              <span className="lista-painel-numero">nº {p.numero}</span>
              <span className="lista-painel-texto">
                {p.entrega ? "Entrega" : "Balcão"} <small>{haQuanto(p.criado_em)}</small>
              </span>
              <strong>{reais(p.total)}</strong>
            </li>
          ))}
        </ul>
      )}
      <Link to="/pdv" className="botao-contorno">
        Receber no caixa <Icone nome="seta" tamanho={14} />
      </Link>
    </section>
  );
}

function ListaRepor({ painel }: { painel: Painel }) {
  const itens = painel.estoque?.repor ?? [];
  return (
    <section className="cartao">
      <div className="cartao-cabecalho">
        <h2>O que repor primeiro</h2>
        <small>saldo / mínimo</small>
      </div>
      {itens.length === 0 ? (
        <p className="vazio">Nenhum produto abaixo do mínimo.</p>
      ) : (
        <ul className="lista-painel">
          {itens.map((p) => (
            <li key={`${p.produto_id}-${p.loja_nome}`}>
              <span className="lista-painel-texto">
                {p.nome} <small>{p.loja_nome}</small>
              </span>
              <strong className="falta-receber">
                {quantidade(p.saldo)} / {quantidade(p.estoque_minimo)}
              </strong>
            </li>
          ))}
        </ul>
      )}
      <Link to="/compras/sugestao" className="botao-contorno">
        Montar pedido de compra <Icone nome="seta" tamanho={14} />
      </Link>
    </section>
  );
}

function ListaVencendo({ painel }: { painel: Painel }) {
  const lotes = painel.estoque?.vencendo ?? [];
  return (
    <section className="cartao">
      <div className="cartao-cabecalho">
        <h2>Vencendo primeiro</h2>
        <small>até {painel.dias_alerta_vencimento} dias</small>
      </div>
      {lotes.length === 0 ? (
        <p className="vazio">Nenhum lote perto de vencer.</p>
      ) : (
        <ul className="lista-painel">
          {lotes.map((l) => (
            <li key={`${l.produto_id}-${l.numero_lote}-${l.loja_nome}`}>
              <span className="lista-painel-texto">
                {l.produto_nome}{" "}
                <small>
                  lote {l.numero_lote} · {quantidade(l.quantidade)} un. · {l.loja_nome}
                </small>
              </span>
              <span className={l.dias_para_vencer <= 30 ? "etiqueta etiqueta-alerta" : "etiqueta etiqueta-neutra"}>
                {l.dias_para_vencer === 0 ? "vence hoje" : `${l.dias_para_vencer} dias`} · {data(l.validade)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link to="/estoque" className="botao-contorno">
        Ver alertas do estoque <Icone nome="seta" tamanho={14} />
      </Link>
    </section>
  );
}

/** Dias que faltam no mês, contando hoje. */
function diasQueFaltam(hoje: string): number {
  const dia = diaLocal(hoje);
  return new Date(dia.getFullYear(), dia.getMonth() + 1, 0).getDate() - dia.getDate() + 1;
}

function CartaoMeta(props: { titulo: string; andamento: Andamento; hoje: string; link?: string }) {
  const a = props.andamento;
  const situacao = SITUACOES[a.situacao];
  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <span>{props.titulo}</span>
        <span className={`etiqueta ${situacao.classe}`}>{situacao.texto}</span>
      </div>
      <p>
        <strong className="valor-meta">{reais(a.vendido)}</strong> <span className="vazio">de {reais(a.meta ?? "0")} ({pct(a.percentual)})</span>
      </p>
      <BarraMeta andamento={a} grande />
      <small className="vazio">
        <Recado andamento={a} dias={diasQueFaltam(props.hoje)} />{" "}
        {props.link && <Link to={props.link}>Ver metas</Link>}
      </small>
    </div>
  );
}

function Atalho({ para, icone, rotulo }: { para: string; icone: NomeIcone; rotulo: string }) {
  const linkLigado = useContext(LinkLigado);
  if (!linkLigado(para)) return null;
  return (
    <Link to={para} className="atalho">
      <Icone nome={icone} tamanho={22} />
      {rotulo}
    </Link>
  );
}

function GraficoSemana({ semana }: { semana: Painel["semana"] }) {
  const maior = Math.max(...semana.map((d) => Number(d.total)), 0);
  return (
    <div className="grafico">
      {semana.map((dia, i) => {
        const total = Number(dia.total);
        const altura = maior > 0 ? Math.max((total / maior) * 100, 2) : 2;
        return (
          <div key={dia.data} className="grafico-coluna" title={`${reais(total, false)} em ${dia.quantidade} venda(s)`}>
            <div className="grafico-area">
              <div className={i === semana.length - 1 ? "barra-hoje" : "barra-dia"} style={{ height: `${altura}%` }} />
            </div>
            <span>{DIAS_SEMANA[diaLocal(dia.data).getDay()]}</span>
          </div>
        );
      })}
    </div>
  );
}

function Atencao({ painel }: { painel: Painel }) {
  const { sessao } = useSessao();
  const linkLigado = useContext(LinkLigado);
  const avisos: { icone: NomeIcone; titulo: string; texto: string; para: string }[] = [];
  const gerencia = ehGerente(sessao);
  const g = painel.gestao;
  if (g && g.envios_recusados > 0)
    avisos.push({
      icone: "alerta",
      titulo: `${g.envios_recusados} venda(s) sem internet recusada(s)`,
      texto: "O servidor não aceitou ao chegar. Resolva para o caixa fechar certo.",
      para: "/vendas-offline",
    });
  if (g?.pagar_semana && g.pagar_semana.quantidade > 0)
    avisos.push({
      icone: "recibo",
      titulo: `${reais(g.pagar_semana.total)} a pagar nos próximos dias`,
      texto: `${g.pagar_semana.quantidade} conta(s) vencem até o fim da semana. Veja o que pagar e copie os códigos dos boletos.`,
      para: "/financeiro",
    });
  if (g && g.receber_vencidas.quantidade > 0)
    avisos.push({
      icone: "dinheiro",
      titulo: `${reais(g.receber_vencidas.total)} a receber atrasado`,
      texto: `${g.receber_vencidas.quantidade} conta(s) de fiado ou convênio vencida(s).`,
      para: "/financeiro/receber",
    });
  if (painel.lotes_vencidos > 0 && painel.estoque)
    avisos.push({
      icone: "alerta",
      titulo: `${painel.lotes_vencidos} lote(s) vencido(s) com saldo`,
      texto: "Retire do estoque e registre a perda.",
      para: "/estoque",
    });
  if (gerencia && painel.lotes_vencendo > 0)
    avisos.push({
      icone: "relogio",
      titulo: `${painel.lotes_vencendo} lote(s) próximo(s) ao vencimento`,
      texto: `Revise os lotes com validade em até ${painel.dias_alerta_vencimento} dias.`,
      para: "/estoque",
    });
  if (gerencia && painel.abaixo_do_minimo > 0)
    avisos.push({
      icone: "baixa",
      titulo: `${painel.abaixo_do_minimo} produto(s) abaixo do mínimo`,
      texto: "Confira os produtos que precisam de reposição.",
      para: "/estoque",
    });
  if (painel.estoque && painel.estoque.notas_para_conferir > 0 && gerencia)
    avisos.push({
      icone: "entrada",
      titulo: `${painel.estoque.notas_para_conferir} nota(s) para conferir`,
      texto: "Notas importadas esperando a entrada no estoque.",
      para: "/compras",
    });
  if (painel.pedidos_novos > 0 && painel.balcao)
    avisos.push({
      icone: "recibo",
      titulo: `${painel.pedidos_novos} pedido(s) novo(s)`,
      texto: "Chegaram pela loja online ou foram anotados. Aceite para separar.",
      para: "/pedidos",
    });
  if (painel.encomendas_chegaram > 0 && painel.balcao)
    avisos.push({
      icone: "sino",
      titulo: `${painel.encomendas_chegaram} encomenda(s) chegaram`,
      texto: "Avise os clientes que o produto que pediram já está na loja.",
      para: "/faltas",
    });
  if (!painel.meu_caixa_aberto && podeReceber(sessao) && !gerencia)
    avisos.push({
      icone: "caixa",
      titulo: "Prepare seu caixa",
      texto: "Abra o caixa para iniciar os recebimentos.",
      para: "/caixas",
    });

  const visiveis = avisos.filter((a) => linkLigado(a.para));
  if (visiveis.length === 0) return <p className="vazio">Tudo em ordem por aqui.</p>;
  return (
    <ul className="avisos">
      {visiveis.map((aviso) => (
        <li key={aviso.titulo}>
          <span className="aviso-icone">
            <Icone nome={aviso.icone} tamanho={16} />
          </span>
          <div>
            <strong>{aviso.titulo}</strong>
            <p>{aviso.texto}</p>
            <Link to={aviso.para} className="botao-contorno">
              Ver detalhes <Icone nome="seta" tamanho={14} />
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}

import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../api/cliente";
import type { Painel } from "../api/tipos";
import Icone, { type NomeIcone } from "../components/Icone";
import { reais } from "../formato";
import { podeReceber, useSessao } from "../sessao";

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

export default function Inicio() {
  const { sessao } = useSessao();
  const [painel, setPainel] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Painel>("/painel")
      .then(setPainel)
      .catch((e) => setErro(mensagem(e)));
  }, []);

  if (erro) return <p className="erro">{erro}</p>;
  if (!painel) return <p>Carregando...</p>;

  const primeiroNome = sessao?.nome.split(" ")[0] ?? "";
  const dataPorExtenso = diaLocal(painel.hoje).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const comparacao = variacao(Number(painel.vendas_hoje), Number(painel.vendas_ontem));

  return (
    <div className="inicio">
      <p className="sobretitulo">{dataPorExtenso}</p>
      <div className="inicio-titulo">
        <div>
          <h1>Seu dia, sob controle.</h1>
          <p className="vazio">Bem-vindo, {primeiroNome}. Veja o que acontece na sua farmácia hoje.</p>
        </div>
        <Link to="/vendas" className="botao">
          <Icone nome="mais" /> Nova venda
        </Link>
      </div>

      <section className="destaque">
        <span className="selo">{painel.farmacia} • {painel.uf}</span>
        <h2>Mais cuidado. Menos complicação.</h2>
        <p>Vendas, estoque e atendimento em um só lugar.</p>
      </section>

      <div className="indicadores">
        <Indicador titulo="Vendas de hoje" icone="dinheiro" valor={reais(painel.vendas_hoje)}>
          {comparacao === null ? (
            "Sem vendas ontem para comparar"
          ) : (
            <span className={comparacao >= 0 ? "positivo" : "negativo"}>
              <Icone nome={comparacao >= 0 ? "subida" : "descida"} tamanho={12} />{" "}
              {Math.abs(comparacao).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% em relação a ontem
            </span>
          )}
        </Indicador>
        <Indicador titulo="Vendas realizadas" icone="recibo" valor={String(painel.quantidade_vendas_hoje)}>
          Ticket médio de {reais(painel.ticket_medio_hoje)}
        </Indicador>
        <Indicador titulo="Clientes cadastrados" icone="pessoa" valor={String(painel.clientes)}>
          {painel.produtos_ativos} produtos ativos no cadastro
        </Indicador>
        <Indicador titulo="Caixas abertos" icone="caixa" valor={String(painel.caixas_abertos)}>
          {painel.meu_caixa_aberto ? "Seu caixa está aberto" : "Seu caixa está fechado"}
        </Indicador>
      </div>

      <div className="inicio-grade">
        <section className="cartao">
          <div className="cartao-cabecalho">
            <h2>Acesso rápido</h2>
            <small>Sua rotina mais simples</small>
          </div>
          <div className="atalhos">
            <Atalho para="/vendas" icone="mais" rotulo="Nova venda" />
            <Atalho para="/clientes" icone="pessoa" rotulo="Clientes" />
            <Atalho para="/configuracoes/produtos" icone="pacote" rotulo="Produtos" />
            <Atalho para="/caixas" icone="caixa" rotulo="Gerenciar caixa" />
          </div>

          <div className="cartao-cabecalho">
            <h2>Vendas da semana</h2>
            <small>Últimos 7 dias</small>
          </div>
          <GraficoSemana semana={painel.semana} />
        </section>

        <section className="cartao">
          <h2>Precisa de atenção</h2>
          <Atencao painel={painel} />
        </section>
      </div>
    </div>
  );
}

function Indicador(props: { titulo: string; icone: NomeIcone; valor: string; children: ReactNode }) {
  return (
    <div className="cartao indicador">
      <div className="cartao-cabecalho">
        <span>{props.titulo}</span>
        <Icone nome={props.icone} tamanho={16} />
      </div>
      <strong>{props.valor}</strong>
      <small>{props.children}</small>
    </div>
  );
}

function Atalho({ para, icone, rotulo }: { para: string; icone: NomeIcone; rotulo: string }) {
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
  const avisos: { icone: NomeIcone; titulo: string; texto: string; para: string }[] = [];
  if (painel.lotes_vencidos > 0)
    avisos.push({
      icone: "alerta",
      titulo: `${painel.lotes_vencidos} lote(s) vencido(s) com saldo`,
      texto: "Retire do estoque e registre a perda.",
      para: "/estoque",
    });
  if (painel.lotes_vencendo > 0)
    avisos.push({
      icone: "relogio",
      titulo: `${painel.lotes_vencendo} lote(s) próximo(s) ao vencimento`,
      texto: `Revise os lotes com validade em até ${painel.dias_alerta_vencimento} dias.`,
      para: "/estoque",
    });
  if (painel.abaixo_do_minimo > 0)
    avisos.push({
      icone: "baixa",
      titulo: `${painel.abaixo_do_minimo} produto(s) abaixo do mínimo`,
      texto: "Confira os produtos que precisam de reposição.",
      para: "/estoque",
    });
  if (!painel.meu_caixa_aberto && podeReceber(sessao))
    avisos.push({
      icone: "caixa",
      titulo: "Prepare seu caixa",
      texto: "Abra o caixa para iniciar os recebimentos.",
      para: "/caixas",
    });

  if (avisos.length === 0) return <p className="vazio">Tudo em ordem por aqui.</p>;
  return (
    <ul className="avisos">
      {avisos.map((aviso) => (
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

import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { FichaCliente, MovimentoPontos } from "../../api/tipos";
import { FormularioCadastro, Janela } from "../../components/Cadastro";
import { data, quantidade, reais } from "../../formato";
import { ehGerente, useSessao } from "../../sessao";
import { documento, telefone } from "../configuracoes/campos";
import { camposCliente, useConvenios } from "./Clientes";

const NOMES_FORMA: Record<string, string> = {
  dinheiro: "Dinheiro",
  debito: "Débito",
  credito: "Crédito",
  pix: "Pix",
  prazo: "A prazo",
  convenio: "Convênio",
  popular: "Farmácia Popular",
};

const NOMES_MOVIMENTO: Record<MovimentoPontos["tipo"], string> = {
  ganho: "Ganhou na compra",
  resgate: "Trocou por desconto",
  estorno: "Venda cancelada",
  ajuste: "Ajuste manual",
  expirado: "Pontos expirados",
};

function idade(nascimento: string | null): string | null {
  if (!nascimento) return null;
  const [ano, mes, dia] = nascimento.split("-").map(Number);
  const hoje = new Date();
  let anos = hoje.getFullYear() - ano;
  if (hoje.getMonth() + 1 < mes || (hoje.getMonth() + 1 === mes && hoje.getDate() < dia)) anos -= 1;
  return `${anos} anos`;
}

function haQuantoTempo(dias: number | null): string {
  if (dias === null) return "Ainda não comprou";
  if (dias === 0) return "Comprou hoje";
  if (dias === 1) return "Comprou ontem";
  return `Há ${dias} dias`;
}

export default function Ficha() {
  const { id } = useParams();
  const { sessao } = useSessao();
  const convenios = useConvenios();
  const [ficha, setFicha] = useState<FichaCliente | null>(null);
  const [erro, setErro] = useState("");
  const [editando, setEditando] = useState(false);
  const [ajustando, setAjustando] = useState(false);

  function carregar() {
    api<FichaCliente>(`/clientes/${id}/ficha`)
      .then((f) => {
        setFicha(f);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(carregar, [id]);

  if (!ficha) {
    return (
      <div className="pagina">
        <p className="sobretitulo">
          <Link to="/clientes">Clientes</Link>
        </p>
        {erro ? <p className="erro">{erro}</p> : <p className="vazio">Carregando...</p>}
      </div>
    );
  }

  const { cliente, compras, pontos } = ficha;
  const aniversarioEsteMes =
    cliente.data_nascimento && Number(cliente.data_nascimento.slice(5, 7)) === new Date().getMonth() + 1;
  const contato = [telefone(cliente.telefone), cliente.email, cliente.cpf && `CPF ${documento(cliente.cpf)}`]
    .filter((p) => p && p !== "-")
    .join(" · ");

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">
            <Link to="/clientes">Clientes</Link> / Ficha
          </p>
          <h1>
            {cliente.nome} {!cliente.ativo && <span className="etiqueta">Inativo</span>}
          </h1>
          <p className="vazio">
            {contato || "Sem contato cadastrado"}
            {cliente.data_nascimento && (
              <>
                {" "}
                · Aniversário {data(cliente.data_nascimento).slice(0, 5)} ({idade(cliente.data_nascimento)})
                {aniversarioEsteMes && <span className="etiqueta ok">Faz aniversário este mês</span>}
              </>
            )}
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setEditando(true)}>
          Editar cadastro
        </button>
      </div>

      <div className="indicadores indicadores-financeiro">
        <div className="cartao indicador">
          <small>Total comprado</small>
          <strong>{reais(compras.total)}</strong>
          <small>
            {compras.quantidade} compra(s)
            {compras.quantidade > 0 && <> · ticket médio {reais(compras.ticket_medio)}</>}
          </small>
        </div>
        <div className={`cartao indicador ${(compras.dias_sem_comprar ?? 0) >= 60 ? "indicador-alerta" : ""}`}>
          <small>Última compra</small>
          <strong>{compras.ultima ? data(compras.ultima) : "-"}</strong>
          <small>{haQuantoTempo(compras.dias_sem_comprar)}</small>
        </div>
        <div className="cartao indicador">
          <small>Pontos</small>
          <strong>{pontos.saldo.toLocaleString("pt-BR")}</strong>
          <small>
            {!pontos.ativo
              ? "Programa de pontos desligado"
              : pontos.saldo > 0
                ? `Valem ${reais(pontos.valor)}${pontos.expiram_em ? ` · expiram em ${data(pontos.expiram_em)}` : ""}`
                : `Troca a partir de ${pontos.minimo_resgate} pontos`}
          </small>
        </div>
        <div className={`cartao indicador ${Number(ficha.fiado_vencido) > 0 ? "indicador-alerta" : ""}`}>
          <small>Fiado em aberto</small>
          <strong>{reais(ficha.fiado_em_aberto)}</strong>
          <small>
            {Number(ficha.fiado_vencido) > 0
              ? `${reais(ficha.fiado_vencido)} vencido`
              : Number(cliente.limite_credito) > 0
                ? `Limite de ${reais(cliente.limite_credito!)}`
                : "Não compra a prazo"}
          </small>
        </div>
      </div>

      <div className="ficha-colunas">
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>O que leva sempre</h2>
          </div>
          {ficha.produtos_frequentes.length === 0 ? (
            <p className="lista-vazia">Nenhuma compra com este cliente identificado ainda.</p>
          ) : (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th className="num">Vezes</th>
                  <th className="num">Qtd</th>
                  <th>Última</th>
                </tr>
              </thead>
              <tbody>
                {ficha.produtos_frequentes.map((p) => (
                  <tr key={p.produto_id}>
                    <td>{p.descricao}</td>
                    <td className="num">{p.vezes}</td>
                    <td className="num">{quantidade(p.quantidade)}</td>
                    <td>{data(p.ultima)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Últimas compras</h2>
          </div>
          {ficha.ultimas_compras.length === 0 ? (
            <p className="lista-vazia">Identifique o cliente no caixa (F8) para as compras aparecerem aqui.</p>
          ) : (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Venda</th>
                  <th>Pagamento</th>
                  <th className="num">Total</th>
                  <th className="num">Pontos</th>
                </tr>
              </thead>
              <tbody>
                {ficha.ultimas_compras.map((v) => (
                  <tr key={v.id} className={v.status === "cancelada" ? "inativo" : ""}>
                    <td>{data(v.finalizada_em)}</td>
                    <td>
                      nº {v.numero}
                      {v.status === "cancelada" && <span className="etiqueta">Cancelada</span>}
                      <small className="linha-detalhe">{v.itens} item(ns)</small>
                    </td>
                    <td>{v.formas.map((f) => NOMES_FORMA[f] ?? f).join(", ")}</td>
                    <td className="num">{reais(v.total)}</td>
                    <td className="num">
                      {v.pontos_ganhos > 0 && <span className="texto-ok">+{v.pontos_ganhos}</span>}
                      {v.pontos_resgatados > 0 && <span className="texto-erro"> −{v.pontos_resgatados}</span>}
                      {!v.pontos_ganhos && !v.pontos_resgatados && "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="cartao ficha-extrato">
        <div className="cartao-cabecalho">
          <h2>Extrato de pontos</h2>
          {ehGerente(sessao) && (
            <button type="button" className="botao-pequeno" onClick={() => setAjustando(true)}>
              Ajustar pontos
            </button>
          )}
        </div>
        {pontos.movimentos.length === 0 ? (
          <p className="lista-vazia">
            {pontos.ativo
              ? "Nenhum ponto ainda. O cliente ganha pontos quando é identificado no caixa."
              : "O programa de pontos está desligado. Ligue em Configurações gerais."}
          </p>
        ) : (
          <table className="tabela">
            <thead>
              <tr>
                <th>Data</th>
                <th>Movimento</th>
                <th>Detalhe</th>
                <th className="num">Pontos</th>
              </tr>
            </thead>
            <tbody>
              {pontos.movimentos.map((m) => (
                <tr key={m.id}>
                  <td>{data(m.criado_em)}</td>
                  <td>{NOMES_MOVIMENTO[m.tipo]}</td>
                  <td>{[m.venda_numero && `Venda nº ${m.venda_numero}`, m.observacao].filter(Boolean).join(" · ") || "-"}</td>
                  <td className={`num ${m.pontos > 0 ? "texto-ok" : "texto-erro"}`}>
                    {m.pontos > 0 ? "+" : "−"}
                    {Math.abs(m.pontos).toLocaleString("pt-BR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {cliente.observacoes && (
        <div className="cartao">
          <h2>Observações</h2>
          <p>{cliente.observacoes}</p>
        </div>
      )}

      {editando && (
        <FormularioCadastro
          titulo="Editar cliente"
          campos={camposCliente(convenios)}
          registro={cliente as unknown as Record<string, unknown>}
          aoFechar={() => setEditando(false)}
          aoSalvar={async (valores) => {
            await api(`/clientes/${cliente.id}`, { metodo: "PATCH", corpo: valores });
            setEditando(false);
            carregar();
          }}
        />
      )}
      {ajustando && (
        <AjustarPontos
          clienteId={cliente.id}
          aoFechar={() => setAjustando(false)}
          aoSalvar={() => {
            setAjustando(false);
            carregar();
          }}
        />
      )}
    </div>
  );
}

function AjustarPontos({ clienteId, aoFechar, aoSalvar }: { clienteId: string; aoFechar: () => void; aoSalvar: () => void }) {
  const [operacao, setOperacao] = useState<"somar" | "tirar">("somar");
  const [pontos, setPontos] = useState("");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    const valor = Number(pontos);
    if (!Number.isInteger(valor) || valor <= 0) return setErro("Informe um número inteiro de pontos");
    try {
      await api(`/clientes/${clienteId}/pontos/ajuste`, {
        corpo: { pontos: operacao === "somar" ? valor : -valor, observacao: motivo },
      });
      aoSalvar();
    } catch (e) {
      setErro(mensagem(e));
    }
  }

  return (
    <Janela titulo="Ajustar pontos" aoFechar={aoFechar}>
      <form className="campos" onSubmit={salvar}>
        <label>
          O que fazer
          <select value={operacao} onChange={(e) => setOperacao(e.target.value as "somar" | "tirar")}>
            <option value="somar">Dar pontos</option>
            <option value="tirar">Tirar pontos</option>
          </select>
        </label>
        <label>
          Pontos
          <input value={pontos} onChange={(e) => setPontos(e.target.value)} inputMode="numeric" required autoFocus />
        </label>
        <label className="largo">
          Motivo *
          <input
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="ex.: bônus de aniversário"
            required
            minLength={3}
          />
          <small>Fica registrado no extrato do cliente.</small>
        </label>
        {erro && <p className="erro largo">{erro}</p>}
        <div className="acoes largo direita">
          <button type="button" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit">Salvar</button>
        </div>
      </form>
    </Janela>
  );
}

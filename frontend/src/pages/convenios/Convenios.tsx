import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, baixar, mensagem } from "../../api/cliente";
import type { Convenio, ConvenioDetalhe } from "../../api/tipos";
import { FormularioCadastro, type Campo } from "../../components/Cadastro";
import Icone from "../../components/Icone";
import { data, reais } from "../../formato";

const CAMPOS: Campo[] = [
  { nome: "nome", rotulo: "Nome da empresa", obrigatorio: true, largo: true },
  { nome: "cnpj", rotulo: "CNPJ", inputMode: "numeric" },
  { nome: "contato", rotulo: "Contato no RH" },
  { nome: "telefone", rotulo: "Telefone", inputMode: "tel" },
  { nome: "email", rotulo: "E-mail para mandar a fatura", tipo: "email" },
  { nome: "desconto", rotulo: "Desconto para os funcionários (%)", inputMode: "numeric", dica: "0 se não tiver desconto" },
  {
    nome: "limite_padrao",
    rotulo: "Limite de cada funcionário (R$)",
    obrigatorio: true,
    inputMode: "numeric",
    dica: "Quanto pode comprar até o fechamento. Dá para mudar por funcionário.",
  },
  { nome: "dia_fechamento", rotulo: "Dia do fechamento", inputMode: "numeric", dica: "De 1 a 28" },
  { nome: "dias_para_pagar", rotulo: "Dias para a empresa pagar", inputMode: "numeric", dica: "Depois do fechamento" },
  { nome: "observacao", rotulo: "Observações", tipo: "area" },
  { nome: "ativo", rotulo: "Convênio ativo", tipo: "check", soNaEdicao: true },
];

function percentual(valor: string): string {
  return `${Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
}

export default function Convenios() {
  const { id } = useParams();
  return id ? <Detalhe id={id} /> : <Lista />;
}

function Lista() {
  const [convenios, setConvenios] = useState<Convenio[] | null>(null);
  const [inativos, setInativos] = useState(false);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState("");
  const navegar = useNavigate();

  function carregar() {
    api<Convenio[]>(`/convenios?incluir_inativos=${inativos}`)
      .then(setConvenios)
      .catch((e) => setErro(mensagem(e)));
  }
  useEffect(carregar, [inativos]);

  const prontos = convenios?.filter((c) => c.pronto_para_fechar) ?? [];

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Empresas</p>
          <h1>Convênios</h1>
          <p className="vazio">
            O funcionário da empresa compra no caixa e assina; no fim do mês a farmácia manda uma fatura só para a empresa,
            que desconta na folha.
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setNovo(true)}>
          <Icone nome="mais" /> Novo convênio
        </button>
      </div>
      {erro && <p className="erro">{erro}</p>}

      {prontos.length > 0 && (
        <div className="cartao aviso-convenio">
          <Icone nome="relogio" />
          <p>
            <strong>Hora de fechar:</strong> {prontos.map((c) => c.nome).join(", ")}. Abra o convênio e gere a cobrança
            do mês.
          </p>
        </div>
      )}

      <div className="cartao">
        <table className="tabela">
          <thead>
            <tr>
              <th>Empresa</th>
              <th className="num">Funcionários</th>
              <th className="num">Desconto</th>
              <th className="num">Limite</th>
              <th>Fecha dia</th>
              <th className="num">Comprado no mês</th>
              <th className="num">A receber</th>
            </tr>
          </thead>
          <tbody>
            {convenios?.map((c) => (
              <tr key={c.id} className="linha-clicavel" onClick={() => navegar(`/convenios/${c.id}`)}>
                <td>
                  <Link to={`/convenios/${c.id}`} className="link-forte">
                    {c.nome}
                  </Link>
                  {!c.ativo && <span className="etiqueta erro-etiqueta">Inativo</span>}
                  {c.pronto_para_fechar && <span className="etiqueta">Fechar</span>}
                </td>
                <td className="num">{c.funcionarios}</td>
                <td className="num">{Number(c.desconto) ? percentual(c.desconto) : "-"}</td>
                <td className="num">{reais(c.limite_padrao)}</td>
                <td>{c.dia_fechamento}</td>
                <td className="num">{reais(c.em_aberto)}</td>
                <td className="num">{Number(c.a_receber) ? reais(c.a_receber) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {convenios?.length === 0 && (
          <p className="lista-vazia">Nenhum convênio ainda. Cadastre a primeira empresa em "Novo convênio".</p>
        )}
        <label className="checkbox rodape">
          <input type="checkbox" checked={inativos} onChange={(e) => setInativos(e.target.checked)} /> Mostrar inativos
        </label>
      </div>

      {novo && (
        <FormularioCadastro
          titulo="Novo convênio"
          campos={CAMPOS}
          registro={{ dia_fechamento: 25, dias_para_pagar: 10, desconto: "0" }}
          aoFechar={() => setNovo(false)}
          aoSalvar={async (valores) => {
            const criado = await api<Convenio>("/convenios", { corpo: valores });
            setNovo(false);
            navegar(`/convenios/${criado.id}`);
          }}
        />
      )}
    </div>
  );
}

function Detalhe({ id }: { id: string }) {
  const [detalhe, setDetalhe] = useState<ConvenioDetalhe | null>(null);
  const [editando, setEditando] = useState(false);
  const [ate, setAte] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  function carregar() {
    api<ConvenioDetalhe>(`/convenios/${id}`)
      .then((d) => {
        setDetalhe(d);
        setAte((atual) => atual || d.convenio.fechamento);
      })
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }
  useEffect(carregar, [id]);

  async function acao(fazer: () => Promise<string | void>) {
    setOcupado(true);
    setAviso(null);
    try {
      const texto = await fazer();
      if (texto) setAviso({ tipo: "ok", texto });
      carregar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    } finally {
      setOcupado(false);
    }
  }

  if (!detalhe) return <div className="pagina">{aviso ? <p className="erro">{aviso.texto}</p> : <p className="vazio">Carregando...</p>}</div>;
  const { convenio, funcionarios, compras_abertas: abertas, faturas } = detalhe;
  const ateFechar = abertas.filter((c) => c.data <= ate);

  return (
    <div className="pagina">
      <p className="migalha">
        <Link to="/convenios">Convênios</Link> /
      </p>
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Convênio</p>
          <h1>
            {convenio.nome} {!convenio.ativo && <span className="etiqueta erro-etiqueta">Inativo</span>}
          </h1>
          <p className="vazio">
            {Number(convenio.desconto) ? `${percentual(convenio.desconto)} de desconto · ` : ""}
            limite de {reais(convenio.limite_padrao)} por funcionário · fecha todo dia {convenio.dia_fechamento} · a
            empresa paga em {convenio.dias_para_pagar} dias
            {convenio.contato && ` · ${convenio.contato}`}
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setEditando(true)}>
          Editar convênio
        </button>
      </div>

      <div className="indicadores indicadores-financeiro">
        <div className="cartao indicador">
          <small>Comprado desde o último fechamento</small>
          <strong>{reais(convenio.em_aberto)}</strong>
          <span>{abertas.length} compra(s)</span>
        </div>
        <div className="cartao indicador">
          <small>Faturas a receber</small>
          <strong>{reais(convenio.a_receber)}</strong>
          <span>{faturas.filter((f) => f.status === "aberta").length} em aberto</span>
        </div>
        <div className="cartao indicador">
          <small>Funcionários</small>
          <strong>{funcionarios.filter((f) => f.ativo).length}</strong>
          <span>com cadastro ativo</span>
        </div>
        <div className="cartao indicador">
          <small>Próximo fechamento</small>
          <strong>{proximoFechamento(convenio.dia_fechamento)}</strong>
          <span>{convenio.pronto_para_fechar ? "Tem compras para fechar" : "Nada para fechar ainda"}</span>
        </div>
      </div>

      {aviso && <p className={aviso.tipo}>{aviso.texto}</p>}

      <div className="cartao cartao-separado">
        <div className="cartao-cabecalho">
          <h2>Fechar o mês</h2>
          <small>gera a conta a receber da empresa</small>
        </div>
        <div className="barra filtros-relatorio">
          <label className="seletor-loja">
            Compras até
            <input type="date" value={ate} max={hojeIso()} onChange={(e) => setAte(e.target.value)} />
          </label>
          <button
            type="button"
            className="botao"
            disabled={ocupado || ateFechar.length === 0}
            onClick={() =>
              acao(async () => {
                const conta = await api<{ valor: string; vencimento: string }>(`/convenios/${id}/fechar`, {
                  corpo: { ate },
                });
                return `Fatura de ${reais(conta.valor)} gerada, vence em ${data(conta.vencimento)}. Está em Financeiro > A receber.`;
              })
            }
          >
            <Icone nome="recibo" />
            Fechar {ateFechar.length} compra(s) · {reais(ateFechar.reduce((s, c) => s + Number(c.valor), 0), false)}
          </button>
          <button
            type="button"
            className="botao-pequeno"
            disabled={abertas.length === 0}
            onClick={() => acao(() => baixar(`/convenios/${id}/extrato`))}
          >
            Planilha do que está em aberto
          </button>
        </div>
        <p className="nota">
          Mande a planilha da fatura para o RH: ela traz o total de cada funcionário para descontar na folha.
        </p>
      </div>

      <div className="ficha-colunas">
        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Funcionários</h2>
            <small>
              <Link to="/clientes">incluir pelo cadastro do cliente</Link>
            </small>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Matrícula</th>
                <th className="num">Usou</th>
                <th className="num">Pode usar</th>
              </tr>
            </thead>
            <tbody>
              {funcionarios.map((f) => (
                <tr key={f.cliente_id} className={f.ativo ? "" : "inativo"}>
                  <td>
                    <Link to={`/clientes/${f.cliente_id}`}>{f.nome}</Link>
                  </td>
                  <td>{f.matricula ?? "-"}</td>
                  <td className="num">{reais(f.usado)}</td>
                  <td className="num">
                    {reais(f.disponivel)}
                    <span className="livro-detalhe">de {reais(f.limite)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {funcionarios.length === 0 && (
            <p className="lista-vazia">
              Nenhum funcionário. No cadastro do cliente, escolha esta empresa no campo "Convênio".
            </p>
          )}
        </div>

        <div className="cartao">
          <div className="cartao-cabecalho">
            <h2>Compras ainda sem fatura</h2>
          </div>
          <table className="tabela">
            <thead>
              <tr>
                <th>Data</th>
                <th>Funcionário</th>
                <th>Venda</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              {abertas.map((c) => (
                <tr key={c.id}>
                  <td>{data(c.data)}</td>
                  <td>{c.nome}</td>
                  <td>nº {c.venda_numero}</td>
                  <td className="num">{reais(c.valor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {abertas.length === 0 && <p className="lista-vazia">Nenhuma compra desde o último fechamento.</p>}
        </div>
      </div>

      <div className="cartao cartao-separado">
        <div className="cartao-cabecalho">
          <h2>Faturas</h2>
          <small>
            <Link to="/financeiro/receber">receber em Financeiro</Link>
          </small>
        </div>
        <table className="tabela">
          <thead>
            <tr>
              <th>Fatura</th>
              <th className="num">Compras</th>
              <th className="num">Valor</th>
              <th>Vencimento</th>
              <th>Situação</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {faturas.map((f) => (
              <tr key={f.conta_id}>
                <td>{f.descricao}</td>
                <td className="num">{f.compras}</td>
                <td className="num">{reais(f.valor)}</td>
                <td>{data(f.vencimento)}</td>
                <td>
                  {f.status === "paga" ? (
                    <span className="etiqueta ok">Paga em {data(f.pago_em)}</span>
                  ) : f.vencida ? (
                    <span className="etiqueta erro-etiqueta">Vencida</span>
                  ) : (
                    <span className="etiqueta">A receber</span>
                  )}
                </td>
                <td className="num acoes-linha">
                  <button
                    type="button"
                    className="botao-pequeno"
                    onClick={() => acao(() => baixar(`/convenios/${id}/extrato?conta_id=${f.conta_id}`))}
                  >
                    Planilha
                  </button>
                  {f.status === "aberta" && (
                    <button
                      type="button"
                      className="botao-pequeno"
                      disabled={ocupado}
                      onClick={() =>
                        acao(async () => {
                          await api(`/convenios/faturas/${f.conta_id}/desfazer`, { metodo: "POST" });
                          return "Fatura desfeita. As compras voltaram para o próximo fechamento.";
                        })
                      }
                    >
                      Desfazer
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {faturas.length === 0 && <p className="lista-vazia">Nenhuma fatura ainda.</p>}
      </div>

      {editando && (
        <FormularioCadastro
          titulo={`Editar ${convenio.nome}`}
          campos={CAMPOS}
          registro={convenio as unknown as Record<string, unknown>}
          aoFechar={() => setEditando(false)}
          aoSalvar={async (valores) => {
            await api(`/convenios/${id}`, { metodo: "PATCH", corpo: valores });
            setEditando(false);
            carregar();
          }}
        />
      )}
    </div>
  );
}

function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function proximoFechamento(dia: number): string {
  const hoje = new Date();
  const alvo = new Date(hoje.getFullYear(), hoje.getMonth() + (hoje.getDate() > dia ? 1 : 0), dia);
  return alvo.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

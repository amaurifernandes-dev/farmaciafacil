import { useEffect, useState, type FormEvent } from "react";

import { api, baixar, ErroApi, mensagem } from "../../api/cliente";
import type { ConfiguracaoFiscal, FechamentoFiscal as Fechamento, LinhaCfop, Regime } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, reais } from "../../formato";
import { useLojas } from "../../lojas";

const NOMES_REGIME: Record<Regime, string> = {
  simples: "Simples Nacional",
  presumido: "Lucro presumido",
  real: "Lucro real",
};

const PADRAO: ConfiguracaoFiscal = {
  ambiente: "homologacao",
  emitir_automaticamente: true,
  cfop_padrao: "5102",
  icms_situacao_tributaria_padrao: "102",
  pis_cofins_situacao_tributaria_padrao: "49",
  regime: "simples",
  perfil_efd: "A",
  contador_nome: null,
  contador_cpf: null,
  contador_crc: null,
  contador_email: null,
};

/** Os últimos 12 meses, do mais recente ao mais antigo, como "2026-10". */
function meses(): { valor: string; nome: string }[] {
  const hoje = new Date();
  return Array.from({ length: 12 }, (_, i) => {
    const dia = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    const valor = `${dia.getFullYear()}-${String(dia.getMonth() + 1).padStart(2, "0")}`;
    const nome = dia.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    return { valor, nome: nome.charAt(0).toUpperCase() + nome.slice(1) + (i === 0 ? " (em andamento)" : "") };
  });
}

function r(valor: string | number): string {
  return reais(valor, false);
}

export default function FechamentoFiscal() {
  const lojas = useLojas();
  const opcoes = meses();
  // O fechamento é do mês que passou.
  const [mes, setMes] = useState(opcoes[1].valor);
  const [lojaId, setLojaId] = useState("");
  const [resumo, setResumo] = useState<Fechamento | null>(null);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  const filtro = `mes=${mes}${lojaId ? `&loja_id=${lojaId}` : ""}`;

  useEffect(() => {
    setResumo(null);
    api<Fechamento>(`/fiscal/fechamento?${filtro}`)
      .then((dados) => {
        setResumo(dados);
        setErro("");
      })
      .catch((e) => setErro(mensagem(e)));
  }, [filtro, versao]);

  useEffect(() => {
    if (!lojaId && lojas.length) setLojaId(lojas.find((l) => l.matriz)?.id ?? lojas[0].id);
  }, [lojas, lojaId]);

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">Impostos</p>
          <h1>Fechamento fiscal</h1>
          <p className="vazio">
            O que foi vendido e comprado no mês, o que falta acertar e o pacote para mandar ao contador.
          </p>
        </div>
      </div>

      <div className="barra filtros-relatorio">
        <label className="seletor-loja">
          Mês
          <select value={mes} onChange={(e) => setMes(e.target.value)}>
            {opcoes.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.nome}
              </option>
            ))}
          </select>
        </label>
        {lojas.length > 1 && <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} />}
      </div>

      {erro && <p className="erro">{erro}</p>}
      {!resumo && !erro && <p className="vazio">Carregando...</p>}
      {resumo && <Resumo resumo={resumo} filtro={filtro} />}

      <DadosFiscais aoSalvar={() => setVersao((v) => v + 1)} />
    </div>
  );
}

function Resumo({ resumo, filtro }: { resumo: Fechamento; filtro: string }) {
  const { saidas, entradas, pgdas } = resumo;
  const simples = resumo.regime === "simples";

  return (
    <>
      <Pendencias resumo={resumo} />

      <div className="indicadores indicadores-financeiro">
        <div className="cartao indicador">
          <small>Vendido no mês</small>
          <strong>{r(saidas.total_vendido)}</strong>
          <span>{saidas.vendas} venda(s)</span>
        </div>
        <div className="cartao indicador">
          <small>Com NFC-e autorizada</small>
          <strong>{r(saidas.valor_nfce)}</strong>
          <span>
            {saidas.nfce_autorizadas} nota(s)
            {saidas.nfce_canceladas > 0 && ` · ${saidas.nfce_canceladas} cancelada(s)`}
          </span>
        </div>
        <div className="cartao indicador">
          <small>Compras do mês</small>
          <strong>{r(entradas.valor_total)}</strong>
          <span>{entradas.notas} nota(s) de fornecedor</span>
        </div>
        <div className="cartao indicador">
          <small>ICMS nas compras</small>
          <strong>{r(entradas.icms)}</strong>
          <span>
            ST {r(entradas.icms_st)} · IPI {r(entradas.ipi)}
          </span>
        </div>
      </div>

      <div className="ficha-colunas">
        {simples ? (
          <div className="cartao">
            <div className="cartao-cabecalho">
              <h2>Receita para o PGDAS</h2>
              <small>Simples Nacional</small>
            </div>
            <p className="vazio">
              Remédio que já teve ICMS-ST ou PIS/COFINS monofásico paga menos imposto no Simples. Informe a receita
              separada assim no PGDAS-D.
            </p>
            <table className="tabela">
              <tbody>
                <tr>
                  <td>Sem ST e sem monofásico</td>
                  <td className="num">{r(pgdas.normal)}</td>
                </tr>
                <tr>
                  <td>Com ICMS-ST</td>
                  <td className="num">{r(pgdas.icms_st)}</td>
                </tr>
                <tr>
                  <td>Com PIS/COFINS monofásico</td>
                  <td className="num">{r(pgdas.monofasico)}</td>
                </tr>
                <tr>
                  <td>Com ICMS-ST e monofásico</td>
                  <td className="num">{r(pgdas.st_e_monofasico)}</td>
                </tr>
                <tr className="linha-total">
                  <td>Total</td>
                  <td className="num">{r(pgdas.total)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <TabelaCfop titulo="Vendas por CFOP" linhas={saidas.por_cfop} vazio="Nenhuma NFC-e autorizada no mês." />
        )}
        <TabelaCfop titulo="Compras por CFOP" linhas={entradas.por_cfop} vazio="Nenhuma nota de compra conferida no mês." />
      </div>

      <Contador resumo={resumo} filtro={filtro} />
    </>
  );
}

function Pendencias({ resumo }: { resumo: Fechamento }) {
  if (resumo.pendencias.length === 0) {
    return (
      <div className="cartao fechamento-ok">
        <Icone nome="entrada" />
        <div>
          <strong>Tudo certo para fechar o mês</strong>
          <p>
            Todas as vendas de {data(resumo.inicio)} a {data(resumo.fim)} têm NFC-e e as notas de compra foram
            conferidas.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <h2>Acertar antes de mandar ao contador</h2>
      </div>
      <ul className="avisos">
        {resumo.pendencias.map((p) => (
          <li key={p.tipo}>
            <span className="aviso-icone">
              <Icone nome="alerta" />
            </span>
            <div>
              <p className="texto-pendencia">{p.texto}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TabelaCfop({ titulo, linhas, vazio }: { titulo: string; linhas: LinhaCfop[]; vazio: string }) {
  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <h2>{titulo}</h2>
      </div>
      <table className="tabela">
        <thead>
          <tr>
            <th>CFOP</th>
            <th>CST</th>
            <th className="num">Valor</th>
            <th className="num">ICMS</th>
            <th className="num">ICMS ST</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={`${l.cfop}-${l.cst}`}>
              <td>{l.cfop}</td>
              <td>{l.cst}</td>
              <td className="num">{r(l.valor)}</td>
              <td className="num">{r(l.icms)}</td>
              <td className="num">{r(l.icms_st)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {linhas.length === 0 && <p className="lista-vazia">{vazio}</p>}
    </div>
  );
}

function Contador({ resumo, filtro }: { resumo: Fechamento; filtro: string }) {
  const [baixando, setBaixando] = useState("");
  const [erro, setErro] = useState("");

  async function baixarArquivo(tipo: "pacote" | "sped") {
    setBaixando(tipo);
    setErro("");
    try {
      await baixar(`/fiscal/${tipo}?${filtro}`);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setBaixando("");
    }
  }

  return (
    <div className="cartao cartao-separado">
      <div className="cartao-cabecalho">
        <h2>Mandar para o contador</h2>
        <small>
          {resumo.loja_nome} · {NOMES_REGIME[resumo.regime]}
        </small>
      </div>
      <p className="vazio">
        O pacote do mês é um arquivo ZIP com o resumo por CFOP, a lista das NFC-e com o link de cada XML, os XMLs das
        notas de compra{resumo.sped_disponivel ? " e o arquivo do SPED Fiscal" : " e a receita separada para o PGDAS"}.
        Mande por e-mail ao contador.
      </p>
      <div className="acoes">
        <button type="button" className="botao" disabled={!!baixando} onClick={() => baixarArquivo("pacote")}>
          <Icone nome="pacote" />
          {baixando === "pacote" ? "Preparando..." : "Baixar pacote do mês"}
        </button>
        {resumo.sped_disponivel && (
          <button type="button" className="botao-pequeno" disabled={!!baixando} onClick={() => baixarArquivo("sped")}>
            {baixando === "sped" ? "Preparando..." : "Só o SPED Fiscal (.txt)"}
          </button>
        )}
      </div>
      {resumo.sped_disponivel ? (
        <p className="nota">
          O SPED Fiscal (EFD ICMS/IPI) sai pronto para o contador abrir no programa da Receita (PVA), conferir e
          transmitir. A EFD Contribuições (PIS/COFINS) continua com o contador.
        </p>
      ) : (
        <p className="nota">
          No Simples Nacional a farmácia não entrega o SPED Fiscal. Se mudar de regime, altere nos dados fiscais abaixo.
        </p>
      )}
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}

function DadosFiscais({ aoSalvar }: { aoSalvar: () => void }) {
  const [config, setConfig] = useState<ConfiguracaoFiscal | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  useEffect(() => {
    api<ConfiguracaoFiscal>("/fiscal/configuracao")
      .then(setConfig)
      .catch((e) => {
        // Ainda não configurado: começa pelo padrão do Simples.
        if (e instanceof ErroApi && e.status === 404) setConfig(PADRAO);
        else setAviso({ tipo: "erro", texto: mensagem(e) });
      });
  }, []);

  function mudar<K extends keyof ConfiguracaoFiscal>(campo: K, valor: ConfiguracaoFiscal[K]) {
    setConfig((c) => (c ? { ...c, [campo]: valor } : c));
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!config) return;
    const ouNulo = (valor: string | null) => (valor ?? "").trim() || null;
    try {
      setConfig(
        await api<ConfiguracaoFiscal>("/fiscal/configuracao", {
          metodo: "PUT",
          corpo: {
            ...config,
            contador_nome: ouNulo(config.contador_nome),
            contador_cpf: ouNulo(config.contador_cpf),
            contador_crc: ouNulo(config.contador_crc),
            contador_email: ouNulo(config.contador_email),
          },
        }),
      );
      setAviso({ tipo: "ok", texto: "Dados fiscais salvos." });
      aoSalvar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (!config) return aviso ? <p className={aviso.tipo}>{aviso.texto}</p> : null;

  return (
    <form className="cartao cartao-separado" onSubmit={salvar}>
      <h2>Dados fiscais e contador</h2>
      <p className="vazio">O regime decide o que vai no fechamento. Na dúvida, pergunte ao contador.</p>
      <fieldset className="campos">
        <label>
          Regime tributário
          <select value={config.regime} onChange={(e) => mudar("regime", e.target.value as Regime)}>
            {Object.entries(NOMES_REGIME).map(([valor, nome]) => (
              <option key={valor} value={valor}>
                {nome}
              </option>
            ))}
          </select>
        </label>
        {config.regime !== "simples" && (
          <label>
            Perfil do SPED
            <select
              value={config.perfil_efd}
              onChange={(e) => mudar("perfil_efd", e.target.value as ConfiguracaoFiscal["perfil_efd"])}
            >
              <option value="A">Perfil A</option>
              <option value="B">Perfil B</option>
              <option value="C">Perfil C</option>
            </select>
            <small>Definido pela SEFAZ do estado. O mais comum é o A.</small>
          </label>
        )}
        <label>
          Nome do contador
          <input value={config.contador_nome ?? ""} onChange={(e) => mudar("contador_nome", e.target.value)} />
        </label>
        <label>
          CPF do contador
          <input
            inputMode="numeric"
            value={config.contador_cpf ?? ""}
            onChange={(e) => mudar("contador_cpf", e.target.value)}
          />
        </label>
        <label>
          CRC
          <input value={config.contador_crc ?? ""} onChange={(e) => mudar("contador_crc", e.target.value)} />
          <small>Registro no Conselho Regional de Contabilidade. Ex.: SP123456</small>
        </label>
        <label>
          E-mail do contador
          <input
            type="email"
            value={config.contador_email ?? ""}
            onChange={(e) => mudar("contador_email", e.target.value)}
          />
        </label>
        <div className="acoes largo">
          <button className="botao">Salvar</button>
          {aviso && <span className={aviso.tipo}>{aviso.texto}</span>}
        </div>
      </fieldset>
    </form>
  );
}

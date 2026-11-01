import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";

import { api, mensagem } from "../api/cliente";
import type { Licenca as DadosLicenca } from "../api/tipos";
import Icone from "../components/Icone";
import { data } from "../formato";
import { useInstalacao } from "../instalacao";
import { avisarLicenca, NOMES_PLANO } from "../licenca";
import { useSessao } from "../sessao";

const TITULOS: Record<string, string> = {
  sem_licenca: "Ative a licença",
  normal: "Licença em dia",
  avisando: "A licença vence logo",
  tolerancia: "Licença vencida, em tolerância",
  encerrada: "Licença encerrada",
  outro_servidor: "Licença de outro servidor",
  relogio: "Data do computador errada",
};

/**
 * Licença do FarmáciaFácil. `solta`: a página aberta sem o menu, para onde o sistema manda quando a licença
 * encerra. Instalado na farmácia ela abre sem login, porque é por ela que se ativa um servidor novo.
 */
export default function Licenca({ solta = false }: { solta?: boolean }) {
  const { sessao } = useSessao();
  const instalacao = useInstalacao();
  const [licenca, setLicenca] = useState<DadosLicenca | null>(null);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [chave, setChave] = useState("");
  const [codigo, setCodigo] = useState("");
  const [enviando, setEnviando] = useState<"chave" | "codigo" | "renovar" | null>(null);
  const [copiado, setCopiado] = useState(false);

  const naFarmacia = instalacao?.modo === "farmacia";
  const precisaLogin = instalacao && !naFarmacia && !sessao;

  useEffect(() => {
    if (!instalacao || precisaLogin) return;
    api<DadosLicenca>("/licenca")
      .then(setLicenca)
      .catch((e) => setErro(mensagem(e)));
  }, [instalacao, precisaLogin]);

  if (precisaLogin) return <Navigate to="/login" replace state={{ voltar: "/licenca" }} />;

  async function enviar(tipo: "chave" | "codigo" | "renovar", evento?: FormEvent) {
    evento?.preventDefault();
    setErro("");
    setOk("");
    setEnviando(tipo);
    try {
      const novo =
        tipo === "renovar"
          ? await api<DadosLicenca>("/licenca/renovar", { corpo: {} })
          : await api<DadosLicenca>("/licenca", { corpo: tipo === "chave" ? { chave_ativacao: chave } : { codigo } });
      setLicenca(novo);
      if (sessao) avisarLicenca(sessao.farmacia_id, novo);
      setChave("");
      setCodigo("");
      setOk(novo.situacao?.bloqueia ? novo.situacao.mensagem : "Pronto. A licença foi atualizada.");
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setEnviando(null);
    }
  }

  async function copiarServidor() {
    if (!licenca?.codigo_servidor) return;
    try {
      await navigator.clipboard.writeText(licenca.codigo_servidor);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1800);
    } catch {
      // sem permissão: o código está na tela para copiar à mão
    }
  }

  const situacao = licenca?.situacao;
  const dados = licenca?.licenca;
  const tom = !situacao ? "" : situacao.bloqueia ? "licenca-bloqueada" : situacao.estado === "normal" ? "licenca-ok" : "licenca-aviso";
  const podeTrocar = naFarmacia || sessao?.papel === "admin";

  return (
    <div className={solta ? "licenca-solta" : "pagina"}>
      {solta && (
        <p className="licenca-marca">
          <strong>FarmáciaFácil</strong>
        </p>
      )}
      {!solta && <p className="sobretitulo">Configurações</p>}
      <div className="pagina-titulo">
        <div>
          <h1>{situacao ? TITULOS[situacao.estado] : "Licença"}</h1>
          <p className="vazio">A licença diz até quando o sistema funciona, quantos usuários e caixas e quais funções.</p>
        </div>
      </div>

      {licenca && !licenca.exigida && (
        <p className="ok espaco-acima">Este sistema não confere licença.</p>
      )}

      {situacao && (
        <section className={`cartao licenca-situacao ${tom} espaco-acima`}>
          <Icone nome={situacao.bloqueia ? "alerta" : situacao.estado === "normal" ? "recibo" : "relogio"} />
          <div>
            <strong>{situacao.mensagem}</strong>
            {situacao.estado === "tolerancia" && (
              <p>Enquanto isso, tudo funciona normal. Renove para o aviso sumir.</p>
            )}
            {situacao.bloqueia && situacao.estado !== "relogio" && (
              <p>Ninguém consegue usar o sistema até a licença ser renovada. Os dados continuam guardados.</p>
            )}
          </div>
        </section>
      )}

      {dados && (
        <section className="cartao espaco-acima">
          <h2>Licença nº {dados.numero}</h2>
          <dl className="licenca-dados">
            <div><dt>Farmácia</dt><dd>{dados.nome}</dd></div>
            <div><dt>Plano</dt><dd>{NOMES_PLANO[dados.plano]}</dd></div>
            <div><dt>Começou em</dt><dd>{data(dados.inicio)}</dd></div>
            <div><dt>Vence em</dt><dd>{dados.vence ? data(dados.vence) : "Não vence"}</dd></div>
            <div><dt>Tolerância</dt><dd>{dados.tolerancia_dias === 1 ? "1 dia" : `${dados.tolerancia_dias} dias`}</dd></div>
            <div><dt>Usuários</dt><dd>{dados.max_usuarios ? `até ${dados.max_usuarios}` : "sem limite"}</dd></div>
            <div><dt>Caixas (PDVs)</dt><dd>{dados.max_caixas ? `até ${dados.max_caixas}` : "sem limite"}</dd></div>
            <div className="largo"><dt>Funções incluídas</dt><dd>{dados.modulos ? (dados.modulos.length ? dados.modulos.join(", ") : "só o básico") : "todas"}</dd></div>
          </dl>
          {licenca?.renova_sozinha && (
            <p className="nota">
              Renova sozinha pela internet a cada 6 horas.
              {licenca.ultimo_erro && ` Última tentativa: ${licenca.ultimo_erro}.`}
            </p>
          )}
          {licenca?.renova_sozinha && podeTrocar && (
            <button type="button" className="botao-contorno espaco-acima" disabled={enviando !== null} onClick={() => void enviar("renovar")}>
              {enviando === "renovar" ? "Buscando..." : "Buscar renovação agora"}
            </button>
          )}
        </section>
      )}

      {licenca?.codigo_servidor && (
        <section className="cartao espaco-acima">
          <h2>Código deste servidor</h2>
          <p className="vazio">Para ativar sem internet, leia este código para quem vendeu o sistema. Ele manda de volta o código da licença.</p>
          <div className="licenca-codigo-servidor">
            <span>{licenca.codigo_servidor}</span>
            <button type="button" className="botao-contorno" onClick={() => void copiarServidor()}>
              {copiado ? "Copiado" : "Copiar"}
            </button>
          </div>
        </section>
      )}

      {licenca?.exigida && podeTrocar && (
        <div className="licenca-formas espaco-acima">
          <form className="cartao" onSubmit={(e) => void enviar("chave", e)}>
            <h2>Com internet: chave de ativação</h2>
            <p className="vazio">Digite a chave de 25 letras e números. O servidor busca a licença e passa a renovar sozinho.</p>
            <label>
              Chave de ativação
              <input
                value={chave}
                onChange={(e) => setChave(e.target.value.toUpperCase())}
                placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
                autoComplete="off"
                spellCheck={false}
                className="licenca-chave"
              />
            </label>
            <button className="botao espaco-acima" disabled={enviando !== null || chave.replace(/[^A-Z0-9]/g, "").length !== 25}>
              {enviando === "chave" ? "Ativando..." : "Ativar"}
            </button>
          </form>
          <form className="cartao" onSubmit={(e) => void enviar("codigo", e)}>
            <h2>Sem internet: código da licença</h2>
            <p className="vazio">Cole o código inteiro que você recebeu (começa com FF1). Pode colar com espaços e quebras de linha.</p>
            <label>
              Código da licença
              <textarea value={codigo} onChange={(e) => setCodigo(e.target.value)} rows={4} spellCheck={false} className="licenca-texto" />
            </label>
            <button className="botao espaco-acima" disabled={enviando !== null || !codigo.trim()}>
              {enviando === "codigo" ? "Conferindo..." : "Instalar código"}
            </button>
          </form>
        </div>
      )}

      {erro && <p className="erro espaco-acima" role="alert">{erro}</p>}
      {ok && <p className={`${situacao?.bloqueia ? "erro" : "ok"} espaco-acima`} role="status">{ok}</p>}

      {solta && (
        <p className="espaco-acima">
          {situacao && !situacao.bloqueia ? (
            <Link to="/" className="botao">Voltar ao sistema</Link>
          ) : (
            <Link to={sessao ? "/" : "/login"} className="botao-contorno">
              {sessao ? "Tentar abrir o sistema" : "Ir para o login"}
            </Link>
          )}
        </p>
      )}
    </div>
  );
}

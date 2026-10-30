import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Configuracoes, Loja, ModoCaixa, Terminal } from "../../api/tipos";
import { ehAdmin, useSessao } from "../../sessao";

export default function Gerais() {
  const { sessao } = useSessao();
  const podeEditar = ehAdmin(sessao);
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [terminais, setTerminais] = useState<Terminal[]>([]);
  const [erro, setErro] = useState("");

  function carregar() {
    // A lista de PDVs é só para gerentes; os demais veem as lojas sem ela.
    Promise.all([api<Loja[]>("/lojas"), api<Terminal[]>("/terminais").catch(() => [])])
      .then(([l, t]) => {
        setLojas(l.filter((loja) => loja.ativo));
        setTerminais(t);
      })
      .catch((e) => setErro(mensagem(e)));
  }

  useEffect(carregar, []);

  return (
    <div className="pagina">
      <p className="sobretitulo">Configurações</p>
      <h1>Configurações gerais</h1>
      <p className="vazio">Como a farmácia recebe as vendas e as regras do dia a dia.</p>
      {erro && <p className="erro">{erro}</p>}
      {!podeEditar && <p className="nota">Só o administrador pode alterar estas configurações.</p>}

      <h2 className="secao">Como cada loja recebe as vendas?</h2>
      {lojas.map((loja) => (
        <ModoDaLoja
          key={loja.id}
          loja={loja}
          terminais={terminais.filter((t) => t.loja_id === loja.id && t.ativo)}
          podeEditar={podeEditar}
          aoSalvar={carregar}
        />
      ))}

      <div className="cartao explicacao">
        <h2>Como o sistema sabe qual computador é o caixa?</h2>
        <p>
          Pelo <strong>registro do computador</strong>, e não pelo IP. Em <Link to="/caixas">Caixas</Link>, um gerente
          abre o sistema no computador do caixa e clica em <em>Registrar este computador</em>. O sistema guarda uma
          chave secreta no navegador daquele computador, e a partir daí ele é reconhecido como "PDV 01", "PDV 02" etc.
        </p>
        <p>
          O IP não serve bem porque o sistema fica na internet: todos os computadores da loja chegam com o mesmo IP do
          roteador, e esse IP muda quando a internet cai e volta. Com o registro, trocar a internet não muda nada, e se
          um computador for trocado basta registrar o novo (o antigo perde o acesso de caixa na hora).
        </p>
      </div>

      <RegrasGerais podeEditar={podeEditar} />
    </div>
  );
}

function ModoDaLoja({
  loja,
  terminais,
  podeEditar,
  aoSalvar,
}: {
  loja: Loja;
  terminais: Terminal[];
  podeEditar: boolean;
  aoSalvar: () => void;
}) {
  const [modo, setModo] = useState<ModoCaixa>(loja.modo_caixa);
  const [central, setCentral] = useState(loja.terminal_central_id ?? "");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await api(`/lojas/${loja.id}`, {
        metodo: "PATCH",
        corpo: { modo_caixa: modo, ...(central ? { terminal_central_id: central } : {}) },
      });
      setAviso({ tipo: "ok", texto: "Configuração salva." });
      aoSalvar();
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  return (
    <form className="cartao modo-loja" onSubmit={salvar}>
      <h3>{loja.nome}</h3>
      <fieldset disabled={!podeEditar}>
        <label className={`opcao ${modo === "mono" ? "marcada" : ""}`}>
          <input type="radio" name={`modo-${loja.id}`} checked={modo === "mono"} onChange={() => setModo("mono")} />
          <span>
            <strong>Monocaixa</strong>
            <small>
              Os atendentes lançam pré-vendas em qualquer computador. Um PDV central recebe o pagamento, emite a NFC-e e
              imprime o cupom.
            </small>
          </span>
        </label>
        <label className={`opcao ${modo === "multi" ? "marcada" : ""}`}>
          <input type="radio" name={`modo-${loja.id}`} checked={modo === "multi"} onChange={() => setModo("multi")} />
          <span>
            <strong>Multicaixa</strong>
            <small>Cada PDV registrado abre o próprio caixa, recebe pagamentos e emite a NFC-e direto no balcão.</small>
          </span>
        </label>

        {modo === "mono" && (
          <label className="campo-central">
            PDV central (o único que recebe)
            {terminais.length > 0 ? (
              <select value={central} onChange={(e) => setCentral(e.target.value)}>
                {!central && <option value="">Escolha um PDV</option>}
                {terminais.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nome}
                  </option>
                ))}
              </select>
            ) : (
              <span className="nota">
                Nenhum PDV cadastrado nesta loja. Cadastre em <Link to="/caixas">Caixas</Link>.
              </span>
            )}
          </label>
        )}
        {modo === "multi" && (
          <p className="nota">
            {terminais.length} PDV(s) ativo(s) nesta loja. Cadastre mais em <Link to="/caixas">Caixas</Link>.
          </p>
        )}
        {podeEditar && (
          <div className="acoes">
            <button type="submit">Salvar</button>
            {aviso && <span className={aviso.tipo}>{aviso.texto}</span>}
          </div>
        )}
      </fieldset>
    </form>
  );
}

function RegrasGerais({ podeEditar }: { podeEditar: boolean }) {
  const [config, setConfig] = useState<Configuracoes | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  useEffect(() => {
    api<Configuracoes>("/configuracoes")
      .then(setConfig)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }, []);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!config) return;
    try {
      setConfig(
        await api<Configuracoes>("/configuracoes", {
          metodo: "PATCH",
          corpo: {
            desconto_maximo_caixa: String(config.desconto_maximo_caixa).replace(",", "."),
            dias_alerta_vencimento: Number(config.dias_alerta_vencimento),
            dias_prazo_padrao: Number(config.dias_prazo_padrao),
          },
        }),
      );
      setAviso({ tipo: "ok", texto: "Configurações salvas." });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (!config) return aviso ? <p className={aviso.tipo}>{aviso.texto}</p> : null;

  return (
    <form className="cartao" onSubmit={salvar}>
      <h2>Regras de venda e estoque</h2>
      <fieldset disabled={!podeEditar} className="campos">
        <label>
          Desconto máximo sem gerente (%)
          <input
            value={config.desconto_maximo_caixa}
            onChange={(e) => setConfig({ ...config, desconto_maximo_caixa: e.target.value })}
            inputMode="decimal"
          />
          <small>Acima disso, a venda precisa ser feita por um gerente ou administrador.</small>
        </label>
        <label>
          Avisar lotes que vencem em até (dias)
          <input
            type="number"
            min={1}
            max={365}
            value={config.dias_alerta_vencimento}
            onChange={(e) => setConfig({ ...config, dias_alerta_vencimento: Number(e.target.value) })}
          />
          <small>Usado no aviso da Visão geral.</small>
        </label>
        <label>
          Prazo da venda a prazo (dias)
          <input
            type="number"
            min={1}
            max={180}
            value={config.dias_prazo_padrao}
            onChange={(e) => setConfig({ ...config, dias_prazo_padrao: Number(e.target.value) })}
          />
          <small>Vencimento do fiado quando o caixa não escolhe outra data.</small>
        </label>
        {podeEditar && (
          <div className="acoes largo">
            <button type="submit">Salvar</button>
            {aviso && <span className={aviso.tipo}>{aviso.texto}</span>}
          </div>
        )}
      </fieldset>
    </form>
  );
}

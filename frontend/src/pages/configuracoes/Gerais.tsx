import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Configuracoes, Loja, ModoCaixa, Papel, Terminal } from "../../api/tipos";
import type { StatusAssistente } from "../../components/assistente/visivel";
import Icone from "../../components/Icone";
import { reais } from "../../formato";
import { useInstalacao } from "../../instalacao";
import { ehAdmin, NOMES_PAPEIS, useSessao } from "../../sessao";

export default function Gerais() {
  const { sessao } = useSessao();
  const podeEditar = ehAdmin(sessao);
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [terminais, setTerminais] = useState<Terminal[]>([]);
  const [erro, setErro] = useState("");
  const instalacao = useInstalacao();

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
      <AssistenteIA podeEditar={podeEditar} />
      <ProgramaDePontos podeEditar={podeEditar} />
      {instalacao?.loja_online && <LojaOnline podeEditar={podeEditar} lojas={lojas} />}
      {instalacao?.modo === "farmacia" && (
        <div className="cartao cartao-separado">
          <h2>Loja online</h2>
          <p className="vazio">
            Este sistema está instalado na farmácia, e não na internet, então a loja online e o Pix pelo site não
            aparecem. Os pedidos do WhatsApp e do telefone continuam na tela Pedidos.
          </p>
        </div>
      )}
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
            popular_validade_receita: Number(config.popular_validade_receita),
            popular_intervalo_dias: Number(config.popular_intervalo_dias),
            comissao_padrao: String(config.comissao_padrao).replace(",", "."),
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
        <label>
          Comissão padrão dos vendedores (%)
          <input
            value={config.comissao_padrao}
            onChange={(e) => setConfig({ ...config, comissao_padrao: e.target.value })}
            inputMode="decimal"
          />
          <small>Sobre o que cada um vendeu. No cadastro do produto dá para usar outra.</small>
        </label>
        <label>
          Farmácia Popular: a receita vale (dias)
          <input
            type="number"
            min={30}
            max={365}
            value={config.popular_validade_receita}
            onChange={(e) => setConfig({ ...config, popular_validade_receita: Number(e.target.value) })}
          />
          <small>Receita mais velha que isso não é aceita no caixa.</small>
        </label>
        <label>
          Farmácia Popular: dias até levar o mesmo remédio de novo
          <input
            type="number"
            min={0}
            max={90}
            value={config.popular_intervalo_dias}
            onChange={(e) => setConfig({ ...config, popular_intervalo_dias: Number(e.target.value) })}
          />
          <small>O caixa avisa antes do governo recusar. 0 deixa só o sistema do governo conferir.</small>
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

function ProgramaDePontos({ podeEditar }: { podeEditar: boolean }) {
  const [config, setConfig] = useState<Configuracoes | null>(null);
  const [validade, setValidade] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  function receber(dados: Configuracoes) {
    // "0.0500" -> "0,05": mais fácil de ler e de editar.
    const limpo = (valor: string) => String(Number(valor)).replace(".", ",");
    setConfig({ ...dados, pontos_por_real: limpo(dados.pontos_por_real), valor_ponto: limpo(dados.valor_ponto) });
    setValidade(dados.pontos_validade_meses == null ? "" : String(dados.pontos_validade_meses));
  }

  useEffect(() => {
    api<Configuracoes>("/configuracoes")
      .then(receber)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
  }, []);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!config) return;
    try {
      receber(
        await api<Configuracoes>("/configuracoes", {
          metodo: "PATCH",
          corpo: {
            fidelidade_ativa: config.fidelidade_ativa,
            pontos_por_real: String(config.pontos_por_real).replace(",", "."),
            valor_ponto: String(config.valor_ponto).replace(",", "."),
            pontos_minimo_resgate: Number(config.pontos_minimo_resgate),
            pontos_validade_meses: validade.trim() ? Number(validade) : null,
          },
        }),
      );
      setAviso({ tipo: "ok", texto: "Programa de pontos salvo." });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (!config) return null;

  // Exemplo em reais para o dono entender quanto devolve ao cliente.
  const porReal = Number(String(config.pontos_por_real).replace(",", ".")) || 0;
  const valorPonto = Number(String(config.valor_ponto).replace(",", ".")) || 0;
  const volta = porReal * valorPonto * 100;

  return (
    <form className="cartao cartao-separado" onSubmit={salvar}>
      <h2>Programa de pontos</h2>
      <p className="vazio">
        O cliente identificado no caixa ganha pontos a cada compra e troca por desconto numa próxima.
      </p>
      <fieldset disabled={!podeEditar} className="campos">
        <label className="checkbox caixa-marcacao largo">
          <input
            type="checkbox"
            checked={config.fidelidade_ativa}
            onChange={(e) => setConfig({ ...config, fidelidade_ativa: e.target.checked })}
          />
          <span>
            Usar o programa de pontos
            <small>Desligado, ninguém ganha nem troca pontos. Os saldos ficam guardados.</small>
          </span>
        </label>
        <label>
          Pontos por R$ 1,00 gasto
          <input
            value={config.pontos_por_real}
            onChange={(e) => setConfig({ ...config, pontos_por_real: e.target.value })}
            inputMode="decimal"
          />
        </label>
        <label>
          Quanto vale cada ponto (R$)
          <input
            value={config.valor_ponto}
            onChange={(e) => setConfig({ ...config, valor_ponto: e.target.value })}
            inputMode="decimal"
          />
        </label>
        <label>
          Mínimo de pontos para trocar
          <input
            type="number"
            min={1}
            value={config.pontos_minimo_resgate}
            onChange={(e) => setConfig({ ...config, pontos_minimo_resgate: Number(e.target.value) })}
          />
        </label>
        <label>
          Pontos expiram após (meses sem comprar)
          <input
            type="number"
            min={1}
            max={60}
            value={validade}
            onChange={(e) => setValidade(e.target.value)}
            placeholder="Não expiram"
          />
          <small>Deixe vazio para os pontos nunca expirarem.</small>
        </label>
        <p className="nota largo">
          Assim, uma compra de {reais(100, false)} dá {Math.floor(100 * porReal)} pontos, que valem{" "}
          {reais(Math.floor(100 * porReal) * valorPonto, false)} de desconto: o cliente recebe de volta{" "}
          {volta.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% do que gastou.
        </p>
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

/** Sugere o endereço da loja a partir do nome: "Farmácia Bem Estar" -> "farmacia-bem-estar". */
function sugerirEndereco(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

/** "8.5" (API) -> "8,50" para editar; "8,50" (digitado) -> "8.50". */
function emTexto(valor: string): string {
  return Number(valor).toFixed(2).replace(".", ",");
}

function paraApi(texto: string): string {
  return texto.replace(/\./g, "").replace(",", ".").trim() || "0";
}

function LojaOnline({ podeEditar, lojas }: { podeEditar: boolean; lojas: Loja[] }) {
  const [config, setConfig] = useState<Configuracoes | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  function receber(dados: Configuracoes) {
    const matriz = lojas.find((l) => l.matriz);
    setConfig({
      ...dados,
      loja_online_endereco: dados.loja_online_endereco ?? (matriz ? sugerirEndereco(matriz.nome_fantasia) : ""),
      entrega_minimo: emTexto(dados.entrega_minimo),
      entrega_taxa: emTexto(dados.entrega_taxa),
      entrega_gratis_acima: dados.entrega_gratis_acima === null ? "" : emTexto(dados.entrega_gratis_acima),
      entrega_bairros: dados.entrega_bairros.map((b) => ({ ...b, taxa: emTexto(b.taxa) })),
    });
  }

  useEffect(() => {
    api<Configuracoes>("/configuracoes")
      .then(receber)
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
    // Recarrega quando as lojas chegam, para sugerir o endereço pelo nome da matriz.
  }, [lojas.length]);

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!config) return;
    const ouNulo = (valor: string | null) => (valor ?? "").trim() || null;
    try {
      receber(
        await api<Configuracoes>("/configuracoes", {
          metodo: "PATCH",
          corpo: {
            loja_online_ativa: config.loja_online_ativa,
            loja_online_endereco: ouNulo(config.loja_online_endereco),
            loja_online_loja_id: config.loja_online_loja_id || null,
            loja_online_mensagem: ouNulo(config.loja_online_mensagem),
            whatsapp: ouNulo(config.whatsapp),
            entrega_ativa: config.entrega_ativa,
            entrega_minimo: paraApi(config.entrega_minimo),
            entrega_area: ouNulo(config.entrega_area),
            entrega_taxa: paraApi(config.entrega_taxa),
            entrega_gratis_acima: (config.entrega_gratis_acima ?? "").trim() ? paraApi(config.entrega_gratis_acima ?? "") : null,
            entrega_bairros: config.entrega_bairros
              .filter((b) => b.bairro.trim())
              .map((b) => ({ bairro: b.bairro.trim(), taxa: paraApi(b.taxa) })),
            pix_no_site: config.pix_no_site,
            pix_chave: ouNulo(config.pix_chave),
            pix_nome: ouNulo(config.pix_nome),
            pix_cidade: ouNulo(config.pix_cidade),
          },
        }),
      );
      setAviso({ tipo: "ok", texto: "Loja online salva." });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (!config) return null;
  const link = `${window.location.origin}/loja/${config.loja_online_endereco}`;

  return (
    <form className="cartao cartao-separado" onSubmit={salvar}>
      <h2>Loja online e WhatsApp</h2>
      <p className="vazio">
        Uma página da farmácia na internet: o cliente vê os produtos com preço e promoção, monta o pedido e escolhe
        retirar ou receber em casa. O pedido chega na tela Pedidos e, aceito, vira pré-venda para o caixa.
      </p>
      <fieldset disabled={!podeEditar} className="campos">
        <label className="checkbox caixa-marcacao largo">
          <input
            type="checkbox"
            checked={config.loja_online_ativa}
            onChange={(e) => setConfig({ ...config, loja_online_ativa: e.target.checked })}
          />
          <span>
            Loja online ligada
            <small>
              Só aparecem os produtos marcados "Aparece na loja online" que têm estoque. Remédio com receita fica de
              fora.
            </small>
          </span>
        </label>
        <label>
          Endereço da loja
          <input
            value={config.loja_online_endereco ?? ""}
            onChange={(e) => setConfig({ ...config, loja_online_endereco: e.target.value.toLowerCase() })}
            placeholder="farmacia-bem-estar"
          />
          <small>Letras, números e hífen. Fica assim: {link}</small>
        </label>
        <label>
          WhatsApp da farmácia
          <input
            value={config.whatsapp ?? ""}
            onChange={(e) => setConfig({ ...config, whatsapp: e.target.value })}
            inputMode="tel"
            placeholder="(11) 99999-8888"
          />
          <small>Aparece na loja com o botão "Falar no WhatsApp".</small>
        </label>
        {lojas.length > 1 && (
          <label>
            Estoque e pedidos da loja
            <select
              value={config.loja_online_loja_id ?? ""}
              onChange={(e) => setConfig({ ...config, loja_online_loja_id: e.target.value || null })}
            >
              <option value="">Matriz</option>
              {lojas
                .filter((l) => !l.matriz)
                .map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.nome}
                  </option>
                ))}
            </select>
          </label>
        )}
        <label className="largo">
          Recado no topo da loja
          <input
            value={config.loja_online_mensagem ?? ""}
            onChange={(e) => setConfig({ ...config, loja_online_mensagem: e.target.value })}
            maxLength={300}
            placeholder="ex.: Aberto de segunda a sábado, das 8h às 22h"
          />
        </label>
        <label className="checkbox caixa-marcacao largo">
          <input
            type="checkbox"
            checked={config.entrega_ativa}
            onChange={(e) => setConfig({ ...config, entrega_ativa: e.target.checked })}
          />
          <span>
            Fazer entrega
            <small>Desligado, o cliente só pode retirar na loja.</small>
          </span>
        </label>
        {config.entrega_ativa && (
          <>
            <label>
              Pedido mínimo para entrega (R$)
              <input
                value={config.entrega_minimo}
                onChange={(e) => setConfig({ ...config, entrega_minimo: e.target.value })}
                inputMode="decimal"
              />
            </label>
            <label>
              Onde entrega
              <input
                value={config.entrega_area ?? ""}
                onChange={(e) => setConfig({ ...config, entrega_area: e.target.value })}
                maxLength={200}
                placeholder="ex.: Centro, Jardim América e Vila Nova"
              />
            </label>
            <label>
              Taxa de entrega (R$)
              <input
                value={config.entrega_taxa}
                onChange={(e) => setConfig({ ...config, entrega_taxa: e.target.value })}
                inputMode="decimal"
              />
              <small>
                {config.entrega_bairros.length
                  ? "Vale para pedido do WhatsApp em bairro fora da lista."
                  : "A mesma para qualquer bairro. Para cobrar por bairro, use a lista abaixo."}
              </small>
            </label>
            <label>
              Entrega grátis a partir de (R$)
              <input
                value={config.entrega_gratis_acima ?? ""}
                onChange={(e) => setConfig({ ...config, entrega_gratis_acima: e.target.value })}
                inputMode="decimal"
                placeholder="vazio: sempre cobra"
              />
            </label>
            <div className="largo bairros-entrega">
              <span className="rotulo">Taxa por bairro</span>
              <small>Com a lista preenchida, o site só entrega nesses bairros e o cliente escolhe o dele.</small>
              {config.entrega_bairros.map((b, i) => (
                <div key={i} className="bairro-linha">
                  <input
                    aria-label="Bairro"
                    value={b.bairro}
                    placeholder="Bairro"
                    maxLength={60}
                    onChange={(e) => setConfig({ ...config, entrega_bairros: config.entrega_bairros.map((x, j) => (j === i ? { ...x, bairro: e.target.value } : x)) })}
                  />
                  <input
                    aria-label="Taxa"
                    value={b.taxa}
                    inputMode="decimal"
                    placeholder="0,00"
                    onChange={(e) => setConfig({ ...config, entrega_bairros: config.entrega_bairros.map((x, j) => (j === i ? { ...x, taxa: e.target.value } : x)) })}
                  />
                  <button
                    type="button"
                    className="botao-icone"
                    title="Tirar o bairro"
                    onClick={() => setConfig({ ...config, entrega_bairros: config.entrega_bairros.filter((_, j) => j !== i) })}
                  >
                    <Icone nome="x" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="botao-pequeno"
                onClick={() => setConfig({ ...config, entrega_bairros: [...config.entrega_bairros, { bairro: "", taxa: "" }] })}
              >
                <Icone nome="mais" /> Adicionar bairro
              </button>
            </div>
          </>
        )}
        <label className="checkbox caixa-marcacao largo">
          <input
            type="checkbox"
            checked={config.pix_no_site}
            onChange={(e) => setConfig({ ...config, pix_no_site: e.target.checked })}
          />
          <span>
            Receber Pix pelo site
            <small>
              O cliente paga na hora pelo QR Code, direto na conta da farmácia (sem taxa de banco intermediário). A
              equipe confere no extrato e marca "Pix recebido" em Pedidos.
            </small>
          </span>
        </label>
        <label>
          Chave Pix
          <input
            value={config.pix_chave ?? ""}
            onChange={(e) => setConfig({ ...config, pix_chave: e.target.value })}
            placeholder="CNPJ, e-mail, celular com +55 ou chave aleatória"
            maxLength={77}
          />
          <small>Também é usada no Pix dos pedidos do WhatsApp.</small>
        </label>
        <label>
          Nome de quem recebe
          <input
            value={config.pix_nome ?? ""}
            onChange={(e) => setConfig({ ...config, pix_nome: e.target.value })}
            maxLength={25}
            placeholder="como aparece no banco"
          />
        </label>
        <label>
          Cidade
          <input
            value={config.pix_cidade ?? ""}
            onChange={(e) => setConfig({ ...config, pix_cidade: e.target.value })}
            maxLength={15}
          />
        </label>
        {podeEditar && (
          <div className="acoes largo">
            <button type="submit">Salvar</button>
            {config.loja_online_ativa && config.loja_online_endereco && (
              <a href={`/loja/${config.loja_online_endereco}`} target="_blank" rel="noreferrer" className="botao-pequeno">
                Abrir a loja
              </a>
            )}
            {aviso && <span className={aviso.tipo}>{aviso.texto}</span>}
          </div>
        )}
      </fieldset>
    </form>
  );
}

const PAPEIS: Papel[] = ["admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque"];

/** Quem usa o assistente de IA e se a chave da Anthropic do servidor está funcionando. */
function AssistenteIA({ podeEditar }: { podeEditar: boolean }) {
  const [perfis, setPerfis] = useState<Papel[] | null>(null);
  const [status, setStatus] = useState<StatusAssistente | null>(null);
  const [teste, setTeste] = useState<{ ok: boolean; mensagem: string } | null>(null);
  const [testando, setTestando] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  useEffect(() => {
    api<Configuracoes>("/configuracoes")
      .then((c) => setPerfis(c.assistente_perfis))
      .catch((e) => setAviso({ tipo: "erro", texto: mensagem(e) }));
    api<StatusAssistente>("/assistente/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  async function testar() {
    setTestando(true);
    setTeste(null);
    try {
      setTeste(await api<{ ok: boolean; mensagem: string }>("/assistente/testar", { corpo: {} }));
    } catch (e) {
      setTeste({ ok: false, mensagem: mensagem(e) });
    } finally {
      setTestando(false);
    }
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!perfis) return;
    try {
      const salvo = await api<Configuracoes>("/configuracoes", { metodo: "PATCH", corpo: { assistente_perfis: perfis } });
      setPerfis(salvo.assistente_perfis);
      setAviso({
        tipo: "ok",
        texto: salvo.assistente_perfis.length ? "Pronto. Cada pessoa liga o assistente no botão do topo." : "Assistente desligado para todos.",
      });
    } catch (e) {
      setAviso({ tipo: "erro", texto: mensagem(e) });
    }
  }

  if (!perfis) return aviso ? <p className={aviso.tipo}>{aviso.texto}</p> : null;

  return (
    <form id="assistente" className="cartao cartao-separado" onSubmit={salvar}>
      <h2>Assistente de IA</h2>
      <p className="vazio">
        O assistente responde por texto ou voz, procura produtos, abre pré-venda, mostra números e monta pedidos. Ele começa
        escondido: cada pessoa mostra ou esconde no botão “Assistente IA”, no topo da tela.
      </p>
      <div className="ia-status">
        <span className={status?.ligado ? "etiqueta ok" : "etiqueta erro-etiqueta"}>
          {status === null ? "Verificando a chave..." : status.ligado ? "Chave da Anthropic no servidor" : "Falta a chave da Anthropic"}
        </span>
        {podeEditar && status?.ligado && (
          <button type="button" className="botao-pequeno" disabled={testando} onClick={() => void testar()}>
            {testando ? "Testando..." : "Testar chave"}
          </button>
        )}
        {teste && <span className={teste.ok ? "ok" : "erro"}>{teste.mensagem}</span>}
      </div>
      {status && !status.ligado && (
        <p className="nota">
          Para ligar, quem cuida do servidor coloca a chave criada em console.anthropic.com na variável ANTHROPIC_API_KEY e
          reinicia o sistema. O uso é cobrado pela Anthropic.
        </p>
      )}
      <fieldset disabled={!podeEditar} className="perfis-ia">
        <legend className="vazio">Quem pode usar</legend>
        {PAPEIS.map((papel) => (
          <label key={papel} className="checkbox caixa-marcacao">
            <input
              type="checkbox"
              checked={perfis.includes(papel)}
              onChange={(e) => setPerfis(e.target.checked ? [...perfis, papel] : perfis.filter((p) => p !== papel))}
            />
            <span>{NOMES_PAPEIS[papel]}</span>
          </label>
        ))}
      </fieldset>
      {podeEditar && (
        <div className="acoes">
          <button type="submit">Salvar</button>
          {aviso && <span className={aviso.tipo}>{aviso.texto}</span>}
        </div>
      )}
    </form>
  );
}

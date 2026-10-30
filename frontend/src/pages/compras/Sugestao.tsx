import { useEffect, useMemo, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { ItemSugestao, SugestaoCompras } from "../../api/tipos";
import Icone from "../../components/Icone";
import SeletorLoja from "../../components/SeletorLoja";
import { data, quantidade, reais } from "../../formato";
import { useLojas } from "../../lojas";

function melhorCusto(item: ItemSugestao): number | null {
  const custo = item.fornecedores[0]?.custo_unitario ?? item.ultimo_custo;
  return custo === null ? null : Number(custo);
}

/** O que comprar para cada loja, pelo ritmo de vendas e pelo estoque mínimo. */
export default function Sugestao() {
  const lojas = useLojas();
  const [lojaId, setLojaId] = useState("");
  const [historico, setHistorico] = useState(30);
  const [cobertura, setCobertura] = useState(15);
  const [sugestao, setSugestao] = useState<SugestaoCompras | null>(null);
  // Quantidade que a pessoa decidiu comprar (começa pela sugerida).
  const [comprar, setComprar] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!lojaId && lojas.length > 0) setLojaId(lojas[0].id);
  }, [lojas, lojaId]);

  useEffect(() => {
    if (!lojaId) return;
    setErro("");
    api<SugestaoCompras>(`/compras/sugestao?loja_id=${lojaId}&dias_historico=${historico}&dias_cobertura=${cobertura}`)
      .then((resposta) => {
        setSugestao(resposta);
        setComprar(Object.fromEntries(resposta.itens.map((i) => [i.produto_id, String(Number(i.sugerido))])));
      })
      .catch((e) => setErro(mensagem(e)));
  }, [lojaId, historico, cobertura]);

  const total = useMemo(
    () =>
      (sugestao?.itens ?? []).reduce((soma, item) => {
        const custo = melhorCusto(item);
        return soma + (custo ?? 0) * Number((comprar[item.produto_id] ?? "0").replace(",", "."));
      }, 0),
    [sugestao, comprar],
  );

  const nomeLoja = lojas.find((l) => l.id === lojaId)?.nome ?? "";

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Sugestão de compras</h1>
          <p className="vazio">
            Calculada pelas vendas recentes de cada produto. Nunca sugere menos que o estoque mínimo.
          </p>
        </div>
        <div className="acoes nao-imprimir">
          <button type="button" className="botao-secundario" onClick={() => window.print()}>
            <Icone nome="recibo" /> Imprimir pedido
          </button>
        </div>
      </div>

      <section className="cartao filtros-sugestao espaco-acima nao-imprimir">
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} rotulo="Comprar para" />
        <label>
          Olhar as vendas dos últimos
          <select value={historico} onChange={(e) => setHistorico(Number(e.target.value))}>
            <option value={15}>15 dias</option>
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </label>
        <label>
          Estoque para durar
          <select value={cobertura} onChange={(e) => setCobertura(Number(e.target.value))}>
            <option value={7}>7 dias</option>
            <option value={15}>15 dias</option>
            <option value={30}>30 dias</option>
            <option value={45}>45 dias</option>
          </select>
        </label>
      </section>
      {erro && <p className="erro">{erro}</p>}

      <p className="so-imprimir">
        Pedido de compra · {nomeLoja} · {data(new Date().toISOString())}
      </p>

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>{sugestao ? `${sugestao.itens.length} produto(s) para comprar` : "Calculando..."}</h2>
          <small>
            Total estimado: <strong>{reais(total, false)}</strong>
          </small>
        </div>
        {sugestao && sugestao.itens.length === 0 ? (
          <p className="lista-vazia">Nada para comprar agora. O estoque desta loja dá conta do período.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th className="num">Tem</th>
                  <th className="num">Vende por dia</th>
                  <th className="num">Dura</th>
                  <th>Melhor fornecedor</th>
                  <th className="num">Comprar</th>
                  <th className="num">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {sugestao?.itens.map((item) => {
                  const custo = melhorCusto(item);
                  const qtd = comprar[item.produto_id] ?? "0";
                  const [melhor, ...outros] = item.fornecedores;
                  const acabando = item.dias_de_estoque !== null && Number(item.dias_de_estoque) < 3;
                  return (
                    <tr key={item.produto_id}>
                      <td>
                        {item.nome} {item.apresentacao && <small>{item.apresentacao}</small>}
                        {item.dias_de_estoque === null && <small className="motivo"> · abaixo do mínimo</small>}
                        {Number(item.encomendas_abertas) > 0 && (
                          <small className="motivo"> · {quantidade(item.encomendas_abertas)} encomendada(s) por clientes</small>
                        )}
                        {Number(item.faltas_no_periodo) > 0 && (
                          <small className="motivo"> · faltou {quantidade(item.faltas_no_periodo)} no balcão</small>
                        )}
                      </td>
                      <td className="num">{quantidade(item.saldo)}</td>
                      <td className="num">{quantidade(item.media_diaria)}</td>
                      <td className={`num ${acabando ? "abaixo" : ""}`}>
                        {item.dias_de_estoque === null ? "-" : `${quantidade(item.dias_de_estoque)} dias`}
                      </td>
                      <td>
                        {melhor ? (
                          <>
                            {melhor.fornecedor_nome} <small>{reais(melhor.custo_unitario)}</small>
                            {outros.length > 0 && (
                              <small className="outros-fornecedores">
                                <br />
                                {outros
                                  .slice(0, 2)
                                  .map((f) => `${f.fornecedor_nome} ${reais(f.custo_unitario)}`)
                                  .join(" · ")}
                              </small>
                            )}
                          </>
                        ) : (
                          <small>sem compras registradas</small>
                        )}
                      </td>
                      <td className="num">
                        <input
                          className="quantidade"
                          value={qtd}
                          inputMode="numeric"
                          onChange={(e) => setComprar({ ...comprar, [item.produto_id]: e.target.value })}
                        />
                      </td>
                      <td className="num">{custo === null ? "-" : reais(custo * Number(qtd.replace(",", ".")), false)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <p className="nota nao-imprimir">
        O preço de cada fornecedor é o da última nota dele que entrou no sistema. Importe as notas pelo XML para a
        comparação ficar completa. O que faltou no balcão conta como venda, e as encomendas dos clientes entram por
        cima do estoque normal.
      </p>
    </div>
  );
}

import { useEffect, useState } from "react";

import { api, mensagem } from "../../api/cliente";
import type { Alertas as TipoAlertas, LoteComProduto } from "../../api/tipos";
import SeletorLoja from "../../components/SeletorLoja";
import { data, quantidade } from "../../formato";
import { useLojas } from "../../lojas";

export default function Alertas() {
  const lojas = useLojas();
  const [lojaId, setLojaId] = useState("");
  const [dias, setDias] = useState(90);
  const [alertas, setAlertas] = useState<TipoAlertas | null>(null);
  const [erro, setErro] = useState("");
  const variasLojas = lojas.length > 1;

  useEffect(() => {
    const loja = lojaId ? `&loja_id=${lojaId}` : "";
    api<TipoAlertas>(`/estoque/alertas?dias=${dias}${loja}`)
      .then(setAlertas)
      .catch((e) => setErro(mensagem(e)));
  }, [dias, lojaId]);

  if (erro) return <p className="erro">{erro}</p>;
  if (!alertas) return <p>Carregando...</p>;

  return (
    <div className="pagina">
      <div className="pagina-titulo">
        <div>
          <h1>Alertas de estoque</h1>
          <p className="vazio">Lotes vencidos, perto de vencer e produtos abaixo do mínimo em cada loja.</p>
        </div>
        <SeletorLoja lojas={lojas} valor={lojaId} aoMudar={setLojaId} todas="Todas as lojas" />
      </div>

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>Vencidos</h2>
          <small>{alertas.vencidos.length} lote(s)</small>
        </div>
        <TabelaLotes lotes={alertas.vencidos} variasLojas={variasLojas} />
      </section>

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>
            Vencendo em até{" "}
            <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
              <option value={30}>30</option>
              <option value={60}>60</option>
              <option value={90}>90</option>
            </select>{" "}
            dias
          </h2>
          <small>{alertas.vencendo.length} lote(s)</small>
        </div>
        <TabelaLotes lotes={alertas.vencendo} variasLojas={variasLojas} />
      </section>

      <section className="cartao espaco-acima">
        <div className="cartao-cabecalho">
          <h2>Abaixo do estoque mínimo</h2>
          <small>{alertas.abaixo_do_minimo.length} produto(s)</small>
        </div>
        {alertas.abaixo_do_minimo.length === 0 ? (
          <p className="lista-vazia">Tudo acima do mínimo.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Produto</th>
                  {variasLojas && <th>Loja</th>}
                  <th className="num">Saldo</th>
                  <th className="num">Mínimo</th>
                </tr>
              </thead>
              <tbody>
                {alertas.abaixo_do_minimo.map((p) => (
                  <tr key={`${p.produto_id}-${p.loja_id}`}>
                    <td>{p.nome}</td>
                    {variasLojas && <td>{p.loja_nome}</td>}
                    <td className="num">{quantidade(p.saldo)}</td>
                    <td className="num">{quantidade(p.estoque_minimo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function TabelaLotes({ lotes, variasLojas }: { lotes: LoteComProduto[]; variasLojas: boolean }) {
  if (lotes.length === 0) return <p className="lista-vazia">Nenhum lote.</p>;
  return (
    <div className="tabela-rolagem">
      <table className="tabela">
        <thead>
          <tr>
            <th>Produto</th>
            {variasLojas && <th>Loja</th>}
            <th>Lote</th>
            <th>Validade</th>
            <th className="num">Dias</th>
            <th className="num">Quantidade</th>
          </tr>
        </thead>
        <tbody>
          {lotes.map((l) => (
            <tr key={l.id}>
              <td>{l.produto_nome}</td>
              {variasLojas && <td>{l.loja_nome}</td>}
              <td>{l.numero_lote}</td>
              <td>{data(l.validade)}</td>
              <td className="num">{l.dias_para_vencer}</td>
              <td className="num">{quantidade(l.quantidade)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { Loja, VendaPopular } from "../../api/tipos";
import { data, quantidade, reais } from "../../formato";

function cpf(valor: string): string {
  return valor.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
}

function cnpj(valor: string): string {
  return valor.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

/** Comprovante da venda pela Farmácia Popular: o paciente assina e a farmácia guarda junto com a receita. */
export default function Comprovante() {
  const { vendaId } = useParams();
  const [venda, setVenda] = useState<VendaPopular | null>(null);
  const [loja, setLoja] = useState<Loja | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    Promise.all([api<VendaPopular>(`/popular/venda/${vendaId}`), api<Loja[]>("/lojas")])
      .then(([v, lojas]) => {
        setVenda(v);
        setLoja(lojas.find((l) => l.id === v.loja_id) ?? lojas.find((l) => l.matriz) ?? null);
      })
      .catch((e) => setErro(mensagem(e)));
  }, [vendaId]);

  if (erro) return <p className="erro comprovante">{erro}</p>;
  if (!venda) return <p className="vazio comprovante">Carregando...</p>;

  return (
    <div className="comprovante">
      <div className="nao-imprimir comprovante-acoes">
        <button type="button" className="botao" onClick={() => window.print()}>
          Imprimir
        </button>
        <span>Imprima, peça para o paciente assinar e guarde junto com a cópia da receita por 5 anos.</span>
      </div>

      <header>
        <strong>{loja?.nome_fantasia}</strong>
        {loja && (
          <small>
            {loja.razao_social} · CNPJ {cnpj(loja.cnpj)}
            {loja.endereco && ` · ${loja.endereco}`}
            {loja.cidade && ` · ${loja.cidade}/${loja.uf}`}
          </small>
        )}
        <h1>Farmácia Popular do Brasil</h1>
        <p>Comprovante de dispensação · venda nº {venda.numero} · {data(venda.data)}</p>
      </header>

      <dl>
        <dt>Autorização</dt>
        <dd>{venda.autorizacao}</dd>
        <dt>Paciente</dt>
        <dd>
          {venda.paciente_nome} · CPF {cpf(venda.paciente_cpf)}
        </dd>
        <dt>Receita</dt>
        <dd>
          CRM {venda.prescritor_crm}/{venda.prescritor_uf} · de {data(venda.receita_data)}
        </dd>
      </dl>

      <table>
        <thead>
          <tr>
            <th>Qtd</th>
            <th>Remédio</th>
            <th className="num">Preço</th>
            <th className="num">Governo paga</th>
          </tr>
        </thead>
        <tbody>
          {venda.itens.map((i) => (
            <tr key={i.produto_id}>
              <td>{quantidade(i.quantidade)}</td>
              <td>{i.descricao}</td>
              <td className="num">{reais(i.total)}</td>
              <td className="num">{reais(i.governo)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>Pago pelo Ministério da Saúde</td>
            <td className="num">{reais(venda.valor_governo)}</td>
          </tr>
          <tr>
            <td colSpan={3}>Pago pelo paciente nesta venda</td>
            <td className="num">{reais(venda.valor_paciente)}</td>
          </tr>
        </tfoot>
      </table>

      <p className="comprovante-declaracao">
        Declaro que recebi os medicamentos acima pelo Programa Farmácia Popular do Brasil, com receita médica em meu
        nome (ou em nome de quem represento).
      </p>

      <div className="assinatura">
        <span>Assinatura do paciente ou responsável</span>
      </div>
      <div className="assinatura assinatura-meia">
        <span>Nome legível</span>
      </div>
      <div className="assinatura assinatura-meia">
        <span>CPF de quem assinou</span>
      </div>
    </div>
  );
}

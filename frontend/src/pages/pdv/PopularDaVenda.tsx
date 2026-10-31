import { useState, type FormEvent } from "react";

import type { DadosPopular } from "../../api/tipos";
import { reais } from "../../formato";

interface Props {
  inicial?: DadosPopular;
  /** CPF já informado na venda (cliente identificado). */
  cpf?: string;
  nome?: string;
  /** Remédios do programa e quanto o governo paga de cada um, em centavos. */
  itens: { descricao: string; governo: number }[];
  totalVenda: number;
  aoSalvar: (dados: DadosPopular) => void;
  aoTirar?: () => void;
  aoVoltar: () => void;
}

const UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(" ");

function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Confere os dígitos do CPF, como o servidor. */
export function cpfValido(cpf: string): boolean {
  const d = cpf.replace(/\D/g, "");
  if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
  for (const tamanho of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < tamanho; i++) soma += Number(d[i]) * (tamanho + 1 - i);
    const digito = ((soma * 10) % 11) % 10;
    if (digito !== Number(d[tamanho])) return false;
  }
  return true;
}

/** Tela do PDV para a venda pela Farmácia Popular: paciente, receita e a autorização do governo. */
export default function PopularDaVenda({ inicial, cpf, nome, itens, totalVenda, aoSalvar, aoTirar, aoVoltar }: Props) {
  const [d, setD] = useState<DadosPopular>(
    inicial ?? {
      paciente_cpf: cpf ?? "",
      paciente_nome: nome ?? "",
      prescritor_crm: "",
      prescritor_uf: "SP",
      receita_data: hojeIso(),
      autorizacao: "",
    },
  );
  const [erro, setErro] = useState("");
  const governo = itens.reduce((soma, i) => soma + i.governo, 0);

  function campo<K extends keyof DadosPopular>(nome: K, valor: DadosPopular[K]) {
    setD((atual) => ({ ...atual, [nome]: valor }));
  }

  function salvar(evento: FormEvent) {
    evento.preventDefault();
    if (!cpfValido(d.paciente_cpf)) return setErro("CPF do paciente inválido");
    if (d.autorizacao.trim().length < 4) return setErro("Digite o número da autorização que o sistema do governo deu");
    aoSalvar({ ...d, paciente_cpf: d.paciente_cpf.replace(/\D/g, ""), autorizacao: d.autorizacao.trim() });
  }

  return (
    <form
      className="pdv-receita cartao"
      onSubmit={salvar}
      onKeyDown={(e) => {
        if (e.key === "Escape") aoVoltar();
      }}
    >
      <div className="cartao-cabecalho">
        <h2>Farmácia Popular</h2>
        <small>O governo paga parte dos remédios do programa</small>
      </div>

      {itens.length === 0 ? (
        <p className="erro">Nenhum remédio desta venda está na Farmácia Popular. Marque no cadastro do produto quanto o governo paga.</p>
      ) : (
        <div className="popular-conta">
          <table>
            <tbody>
              {itens.map((i) => (
                <tr key={i.descricao}>
                  <td>{i.descricao}</td>
                  <td className="num">governo paga {reais(i.governo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div>
            <span>Governo paga <strong>{reais(governo)}</strong></span>
            <span>Paciente paga <strong>{reais(Math.max(totalVenda - governo, 0))}</strong></span>
          </div>
        </div>
      )}

      <ol className="popular-passos">
        <li>Confira a receita e o documento com foto do paciente.</li>
        <li>No autorizador da Farmácia Popular (o sistema do governo), faça a venda com o CPF do paciente.</li>
        <li>Digite aqui o número da autorização que ele devolver.</li>
      </ol>

      <fieldset>
        <legend>Paciente</legend>
        <label>
          CPF *
          <input
            value={d.paciente_cpf}
            onChange={(e) => campo("paciente_cpf", e.target.value)}
            inputMode="numeric"
            required
            autoFocus={!d.paciente_cpf}
          />
        </label>
        <label className="largo">
          Nome *
          <input value={d.paciente_nome} onChange={(e) => campo("paciente_nome", e.target.value)} required minLength={3} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Receita</legend>
        <label>
          CRM do médico *
          <input value={d.prescritor_crm} onChange={(e) => campo("prescritor_crm", e.target.value)} required />
        </label>
        <label>
          UF
          <select value={d.prescritor_uf} onChange={(e) => campo("prescritor_uf", e.target.value)}>
            {UFS.map((uf) => (
              <option key={uf}>{uf}</option>
            ))}
          </select>
        </label>
        <label>
          Data da receita *
          <input
            type="date"
            value={d.receita_data}
            max={hojeIso()}
            onChange={(e) => campo("receita_data", e.target.value)}
            required
          />
        </label>
      </fieldset>

      <fieldset>
        <legend>Autorização do governo</legend>
        <label className="largo">
          Número da autorização *
          <input
            value={d.autorizacao}
            onChange={(e) => campo("autorizacao", e.target.value)}
            required
            autoFocus={!!d.paciente_cpf}
          />
        </label>
      </fieldset>

      {erro && <p className="erro">{erro}</p>}
      <div className="acoes">
        <button type="submit" disabled={itens.length === 0}>Guardar e ir para o pagamento (Enter)</button>
        <button type="button" onClick={aoVoltar}>
          Voltar (Esc)
        </button>
        {aoTirar && (
          <button type="button" className="perigo" onClick={aoTirar}>
            Não é pela Farmácia Popular
          </button>
        )}
      </div>
    </form>
  );
}

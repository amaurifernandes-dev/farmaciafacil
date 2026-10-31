import { useState, type FormEvent } from "react";

import type { Receita } from "../../api/tipos";
import { NOMES_RECEITUARIO } from "./carrinho";

interface Props {
  tipo: number;
  inicial?: Receita;
  remedios: string[];
  aoSalvar: (receita: Receita) => void;
  aoVoltar: () => void;
}

const UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(" ");

function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function vazia(tipo: number): Receita {
  return {
    tipo_receituario: tipo,
    numero_notificacao: null,
    data_prescricao: hojeIso(),
    prescritor_nome: "",
    prescritor_conselho: "CRM",
    prescritor_numero: "",
    prescritor_uf: "SP",
    uso_prolongado: false,
    comprador_nome: null,
    comprador_tipo_documento: 2,
    comprador_documento: null,
    comprador_orgao: "SSP",
    comprador_uf: "SP",
    paciente_nome: null,
    paciente_idade: null,
    paciente_unidade_idade: 1,
    paciente_sexo: null,
    cid: null,
  };
}

/** Tela do PDV para copiar a receita do remédio controlado (o que vai para o livro e para o SNGPC). */
export default function ReceitaDaVenda({ tipo, inicial, remedios, aoSalvar, aoVoltar }: Props) {
  const [r, setR] = useState<Receita>(inicial?.tipo_receituario === tipo ? inicial : vazia(tipo));
  const [erro, setErro] = useState("");
  const antibiotico = tipo === 5;
  const notificacao = [2, 3, 4].includes(tipo);

  function campo<K extends keyof Receita>(nome: K, valor: Receita[K]) {
    setR((atual) => ({ ...atual, [nome]: valor }));
  }

  const texto = (nome: keyof Receita) => ({
    value: (r[nome] as string | null) ?? "",
    onChange: (e: { target: { value: string } }) => campo(nome, (e.target.value || null) as never),
  });

  function salvar(evento: FormEvent) {
    evento.preventDefault();
    const validade = antibiotico ? 10 : 30;
    const limite = new Date(`${r.data_prescricao}T00:00:00`);
    limite.setDate(limite.getDate() + validade);
    if (limite < new Date(`${hojeIso()}T00:00:00`)) return setErro(`Receita vencida: vale ${validade} dias`);
    if (antibiotico && (r.paciente_idade === null || r.paciente_sexo === null)) {
      return setErro("Informe a idade e o sexo do paciente");
    }
    aoSalvar(r);
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
        <h2>{NOMES_RECEITUARIO[tipo]}</h2>
        <small>{remedios.join(", ")}</small>
      </div>
      <p className="vazio">
        {antibiotico
          ? "Copie da receita. Ela vale 10 dias e a farmácia fica com a 2ª via."
          : "Copie da receita e do documento de quem está comprando. Ela vale 30 dias e fica retida na farmácia."}
      </p>

      <fieldset>
        <legend>Receita</legend>
        {notificacao && (
          <label>
            Número da notificação *
            <input {...texto("numero_notificacao")} required autoFocus />
          </label>
        )}
        <label>
          Data da receita *
          <input
            type="date"
            value={r.data_prescricao}
            max={hojeIso()}
            onChange={(e) => campo("data_prescricao", e.target.value)}
            required
            autoFocus={!notificacao}
          />
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={r.uso_prolongado} onChange={(e) => campo("uso_prolongado", e.target.checked)} />
          Uso prolongado
        </label>
      </fieldset>

      <fieldset>
        <legend>Quem receitou</legend>
        <label className="largo">
          Nome *
          <input value={r.prescritor_nome} onChange={(e) => campo("prescritor_nome", e.target.value)} required minLength={3} />
        </label>
        <label>
          Conselho
          <select
            value={r.prescritor_conselho}
            onChange={(e) => campo("prescritor_conselho", e.target.value as Receita["prescritor_conselho"])}
          >
            <option value="CRM">CRM (médico)</option>
            <option value="CRO">CRO (dentista)</option>
            <option value="CRMV">CRMV (veterinário)</option>
            <option value="RMS">RMS</option>
            <option value="CRF">CRF</option>
          </select>
        </label>
        <label>
          Número *
          <input value={r.prescritor_numero} onChange={(e) => campo("prescritor_numero", e.target.value)} required />
        </label>
        <label>
          UF
          <select value={r.prescritor_uf} onChange={(e) => campo("prescritor_uf", e.target.value)}>
            {UFS.map((uf) => (
              <option key={uf}>{uf}</option>
            ))}
          </select>
        </label>
      </fieldset>

      {!antibiotico && (
        <fieldset>
          <legend>Quem está comprando</legend>
          <label className="largo">
            Nome *
            <input {...texto("comprador_nome")} required minLength={3} />
          </label>
          <label>
            RG *
            <input {...texto("comprador_documento")} required />
          </label>
          <label>
            Órgão
            <input {...texto("comprador_orgao")} required maxLength={10} />
          </label>
          <label>
            UF do RG
            <select value={r.comprador_uf ?? "SP"} onChange={(e) => campo("comprador_uf", e.target.value)}>
              {UFS.map((uf) => (
                <option key={uf}>{uf}</option>
              ))}
            </select>
          </label>
        </fieldset>
      )}

      <fieldset>
        <legend>Paciente {antibiotico ? "" : <small>(se não for quem compra)</small>}</legend>
        <label className="largo">
          Nome
          <input {...texto("paciente_nome")} />
        </label>
        <label>
          Idade {antibiotico && "*"}
          <span className="campo-junto">
            <input
              inputMode="numeric"
              value={r.paciente_idade ?? ""}
              onChange={(e) => campo("paciente_idade", e.target.value === "" ? null : Number(e.target.value.replace(/\D/g, "")))}
              required={antibiotico}
            />
            <select
              value={r.paciente_unidade_idade}
              onChange={(e) => campo("paciente_unidade_idade", Number(e.target.value) as 1 | 2)}
            >
              <option value={1}>anos</option>
              <option value={2}>meses</option>
            </select>
          </span>
        </label>
        <label>
          Sexo {antibiotico && "*"}
          <select
            value={r.paciente_sexo ?? ""}
            onChange={(e) => campo("paciente_sexo", e.target.value ? (Number(e.target.value) as 1 | 2) : null)}
            required={antibiotico}
          >
            <option value="">-</option>
            <option value={2}>Feminino</option>
            <option value={1}>Masculino</option>
          </select>
        </label>
      </fieldset>

      {erro && <p className="erro">{erro}</p>}
      <div className="acoes">
        <button type="submit">Guardar receita (Enter)</button>
        <button type="button" onClick={aoVoltar}>
          Voltar (Esc)
        </button>
      </div>
    </form>
  );
}

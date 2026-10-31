import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, mensagem } from "../../api/cliente";
import type { AtendimentoServico, Loja } from "../../api/tipos";
import { data, reais } from "../../formato";
import { idade, NOMES_FORMA } from "./campos";

const ROTULOS: Record<string, string> = {
  sistolica: "Pressão máxima (sistólica)",
  diastolica: "Pressão mínima (diastólica)",
  frequencia: "Frequência cardíaca",
  braco: "Braço",
  valor: "Glicemia capilar",
  jejum: "Em jejum",
  graus: "Temperatura",
  medicamento: "Medicamento",
  dose: "Dose",
  via: "Via de administração",
  local: "Local da aplicação",
  lote: "Lote",
  validade: "Validade",
  prescritor: "Prescritor",
  prescritor_crm: "CRM",
  prescritor_uf: "UF do CRM",
  receita_data: "Data da receita",
  descricao: "Descrição",
};

const UNIDADES: Record<string, string> = { sistolica: " mmHg", diastolica: " mmHg", frequencia: " bpm", valor: " mg/dL", graus: " °C" };

const REFERENCIAS: Record<string, string> = {
  pressao: "Referência para adultos: até 120 x 80 mmHg é ótima; a partir de 140 x 90 mmHg é considerada alta.",
  glicemia: "Referência: em jejum, de 70 a 99 mg/dL; fora do jejum, abaixo de 140 mg/dL (até 2 horas após comer).",
  temperatura: "Referência: de 35,5 a 37,7 °C. A partir de 37,8 °C é considerado febre.",
};

function valorDoCampo(chave: string, valor: string | number | boolean): string {
  if (typeof valor === "boolean") return valor ? "Sim" : "Não";
  if (chave === "validade" || chave === "receita_data") return data(String(valor));
  if (chave === "graus") return `${String(valor).replace(".", ",")}${UNIDADES[chave]}`;
  return `${valor}${UNIDADES[chave] ?? ""}`;
}

/** Declaração de Serviço Farmacêutico (RDC 44/2009, art. 81), para imprimir e entregar ao paciente. */
export default function Declaracao() {
  const { id } = useParams();
  const [atendimento, setAtendimento] = useState<AtendimentoServico | null>(null);
  const [loja, setLoja] = useState<Loja | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<AtendimentoServico>(`/servicos/atendimentos/${id}`)
      .then(async (a) => {
        setAtendimento(a);
        const lojas = await api<Loja[]>("/lojas");
        setLoja(lojas.find((l) => l.id === a.loja_id) ?? null);
      })
      .catch((e) => setErro(mensagem(e)));
  }, [id]);

  if (erro) return <p className="erro declaracao">{erro}</p>;
  if (!atendimento || !loja) return <p className="declaracao">Carregando...</p>;

  const a = atendimento;
  const anos = idade(a.paciente_nascimento);
  const quando = new Date(a.criado_em);
  const endereco = [loja.endereco, loja.bairro, loja.cidade && `${loja.cidade}/${loja.uf}`].filter(Boolean).join(", ");

  return (
    <div className="declaracao">
      <div className="nao-imprimir declaracao-topo">
        <button type="button" className="botao" onClick={() => window.print()}>
          Imprimir
        </button>
        <small>Imprima em duas vias: uma para o paciente e uma para a farmácia arquivar.</small>
      </div>

      <header className="declaracao-cabecalho">
        <div>
          <strong>{loja.nome_fantasia}</strong>
          <span>{loja.razao_social}</span>
          <span>CNPJ {loja.cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5")}</span>
          {endereco && <span>{endereco}</span>}
          {loja.telefone && <span>Telefone {loja.telefone}</span>}
        </div>
        <div className="declaracao-numero">
          <span>Nº {String(a.numero).padStart(6, "0")}</span>
          <span>
            {quando.toLocaleDateString("pt-BR")} às {quando.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
      </header>

      <h1>Declaração de Serviço Farmacêutico</h1>
      {a.status === "cancelado" && <p className="erro">ATENDIMENTO CANCELADO: {a.motivo_cancelamento}</p>}

      <section>
        <h2>Paciente</h2>
        <p>
          <strong>{a.paciente_nome}</strong>
          {a.paciente_cpf && <> · CPF {a.paciente_cpf.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4")}</>}
          {anos !== null && <> · {anos} anos</>}
        </p>
      </section>

      <section>
        <h2>Serviço prestado: {a.servico_nome}</h2>
        <table className="declaracao-tabela">
          <tbody>
            {Object.entries(a.resultados).map(([chave, valor]) => (
              <tr key={chave}>
                <th>{ROTULOS[chave] ?? chave}</th>
                <td>{valorDoCampo(chave, valor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {REFERENCIAS[a.tipo] && <p className="declaracao-ref">{REFERENCIAS[a.tipo]}</p>}
        {a.aviso && <p className="declaracao-aviso">{a.aviso.texto}</p>}
      </section>

      {a.orientacao && (
        <section>
          <h2>Orientação farmacêutica</h2>
          <p className="declaracao-orientacao">{a.orientacao}</p>
        </section>
      )}

      <p className="declaracao-legal">
        Este documento não tem valor de diagnóstico. Os valores medidos devem ser avaliados por um médico. Serviço prestado
        conforme a Resolução RDC nº 44/2009 da Anvisa.
        {Number(a.valor) > 0 ? ` Valor pago: ${reais(a.valor)} (${NOMES_FORMA[a.forma_pagamento]}).` : " Serviço prestado sem cobrança."}
      </p>

      <div className="declaracao-assinaturas">
        <div>
          <span className="linha-assinatura" />
          <strong>{a.farmaceutico}</strong>
          <span>Farmacêutico(a) · CRF {a.farmaceutico_crf ?? "não informado"}</span>
        </div>
        <div>
          <span className="linha-assinatura" />
          <strong>{a.paciente_nome}</strong>
          <span>Paciente ou responsável</span>
        </div>
      </div>
    </div>
  );
}

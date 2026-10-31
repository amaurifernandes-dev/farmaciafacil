import type { Andamento, SituacaoMeta } from "../../api/tipos";
import { reais } from "../../formato";

export const SITUACOES: Record<SituacaoMeta, { texto: string; classe: string }> = {
  batida: { texto: "Meta batida", classe: "ok" },
  no_ritmo: { texto: "No ritmo", classe: "ok" },
  abaixo: { texto: "Abaixo do ritmo", classe: "erro-etiqueta" },
  nao_batida: { texto: "Não bateu", classe: "erro-etiqueta" },
  nao_comecou: { texto: "Ainda não começou", classe: "etiqueta-neutra" },
  sem_meta: { texto: "Sem meta", classe: "etiqueta-neutra" },
};

export function pct(valor: string | number | null): string {
  return `${Number(valor ?? 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

/** Barra do quanto já vendeu da meta, com uma marca de onde devia estar hoje. */
export function BarraMeta({ andamento, grande = false }: { andamento: Andamento; grande?: boolean }) {
  if (!andamento.meta) return null;
  const meta = Number(andamento.meta);
  const feito = Math.min((Number(andamento.vendido) / meta) * 100, 100);
  const esperado = andamento.esperado_ate_hoje ? Math.min((Number(andamento.esperado_ate_hoje) / meta) * 100, 100) : null;
  return (
    <div
      className={`barra-meta ${grande ? "barra-meta-grande" : ""} barra-meta-${andamento.situacao}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(feito)}
      title={
        esperado !== null && andamento.situacao !== "batida"
          ? `Para estar no ritmo, hoje devia ter ${reais(andamento.esperado_ate_hoje ?? "0")}`
          : undefined
      }
    >
      <div className="barra-meta-feito" style={{ width: `${feito}%` }} />
      {esperado !== null && esperado > 0 && esperado < 100 && <div className="barra-meta-marca" style={{ left: `${esperado}%` }} />}
    </div>
  );
}

/** Frase curta do que fazer para bater a meta. */
export function Recado({ andamento, dias }: { andamento: Andamento; dias: number }) {
  const a = andamento;
  if (!a.meta) return null;
  if (a.situacao === "batida") {
    const passou = Number(a.vendido) - Number(a.meta);
    return <>Meta batida{passou > 0 ? `, ${reais(String(passou.toFixed(2)))} acima` : ""}. Parabéns!</>;
  }
  if (a.situacao === "nao_batida") return <>Faltaram {reais(a.falta ?? "0")} para a meta.</>;
  if (a.situacao === "nao_comecou") return <>Para bater, venda {reais(a.por_dia ?? "0")} por dia.</>;
  return (
    <>
      Faltam {reais(a.falta ?? "0")} em {dias} dia(s): {reais(a.por_dia ?? "0")} por dia.
      {a.projecao && <> No ritmo de hoje, fecha o mês com {reais(a.projecao)}.</>}
    </>
  );
}

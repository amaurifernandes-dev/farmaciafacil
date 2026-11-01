// Envia as vendas guardadas quando a internet volta. Cada venda leva a chave dela: se o envio
// cair no meio e for repetido, o servidor devolve a mesma venda em vez de criar outra.

import { api, ErroApi } from "../api/cliente";
import type { Venda } from "../api/tipos";
import { guardarVenda, tirarDaFila, vendasGuardadas, type VendaGuardada } from "./banco";
import { ehFalhaDeRede } from "./catalogo";

export interface ResultadoEnvio {
  enviadas: Venda[];
  /** Aberturas e fechamentos do caixa enviados. */
  caixa: number;
  comProblema: number;
  /** Parou porque a internet ainda não voltou. */
  semInternet: boolean;
}

let enviando = false;

export const ehVenda = (guardada: VendaGuardada) => (guardada.tipo ?? "venda") === "venda";

/** Conta ao servidor (painel do gerente) que este envio foi recusado. */
function avisarRecusa(guardada: VendaGuardada, motivo: string): Promise<unknown> {
  return enviar(
    {
      ...guardada,
      caminho: "/pdv/recusas",
      corpo: {
        chave: guardada.chave,
        tipo: guardada.tipo ?? "venda",
        offline_em: guardada.corpo.offline_em,
        total: (guardada.total_centavos / 100).toFixed(2),
        motivo,
        corpo: guardada.corpo,
      },
    },
  );
}

/** Vai no nome de quem fez (acesso guardado dela). Se esse acesso venceu, tenta com o login atual. */
async function enviar(guardada: VendaGuardada): Promise<unknown> {
  const caminho = guardada.caminho ?? "/vendas";
  if (guardada.token) {
    try {
      return await api<unknown>(caminho, { corpo: guardada.corpo, token: guardada.token });
    } catch (erro) {
      if (!(erro instanceof ErroApi && erro.status === 401)) throw erro;
    }
  }
  return api<unknown>(caminho, { corpo: guardada.corpo });
}

export async function enviarGuardadas(): Promise<ResultadoEnvio> {
  const resultado: ResultadoEnvio = { enviadas: [], caixa: 0, comProblema: 0, semInternet: false };
  if (enviando) return resultado;
  enviando = true;
  try {
    for (const guardada of await vendasGuardadas()) {
      if (guardada.problema) {
        resultado.comProblema += 1;
        continue;
      }
      try {
        // Na ordem em que aconteceu: abertura, vendas e fechamento do caixa.
        const resposta = await enviar(guardada);
        if (ehVenda(guardada)) resultado.enviadas.push(resposta as Venda);
        else resultado.caixa += 1;
        await tirarDaFila(guardada.chave);
      } catch (erro) {
        if (ehFalhaDeRede(erro)) {
          resultado.semInternet = true;
          break; // tenta de novo daqui a pouco, na mesma ordem
        }
        // O servidor recusou: fica guardada com o motivo, e o gerente fica sabendo pelo painel.
        const motivo = (erro as Error).message;
        await guardarVenda({ ...guardada, problema: motivo });
        await avisarRecusa(guardada, motivo).catch(() => undefined);
        resultado.comProblema += 1;
      }
    }
  } finally {
    enviando = false;
  }
  return resultado;
}

/** Tira o problema anotado para tentar enviar de novo (ex.: depois de abrir o caixa certo). */
export async function tentarDeNovo(chave: string): Promise<void> {
  const guardada = (await vendasGuardadas()).find((v) => v.chave === chave);
  if (guardada) await guardarVenda({ ...guardada, problema: undefined });
}

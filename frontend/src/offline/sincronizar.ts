// Envia as vendas guardadas quando a internet volta. Cada venda leva a chave dela: se o envio
// cair no meio e for repetido, o servidor devolve a mesma venda em vez de criar outra.

import { api } from "../api/cliente";
import type { Venda } from "../api/tipos";
import { guardarVenda, tirarDaFila, vendasGuardadas } from "./banco";
import { ehFalhaDeRede } from "./catalogo";

export interface ResultadoEnvio {
  enviadas: Venda[];
  comProblema: number;
  /** Parou porque a internet ainda não voltou. */
  semInternet: boolean;
}

let enviando = false;

export async function enviarGuardadas(): Promise<ResultadoEnvio> {
  const resultado: ResultadoEnvio = { enviadas: [], comProblema: 0, semInternet: false };
  if (enviando) return resultado;
  enviando = true;
  try {
    for (const guardada of await vendasGuardadas()) {
      if (guardada.problema) {
        resultado.comProblema += 1;
        continue;
      }
      try {
        resultado.enviadas.push(await api<Venda>("/vendas", { corpo: guardada.corpo }));
        await tirarDaFila(guardada.chave);
      } catch (erro) {
        if (ehFalhaDeRede(erro)) {
          resultado.semInternet = true;
          break; // tenta de novo daqui a pouco, na mesma ordem
        }
        // O servidor recusou: fica guardada com o motivo para o gerente ver.
        await guardarVenda({ ...guardada, problema: (erro as Error).message });
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

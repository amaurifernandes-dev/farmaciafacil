import { useEffect, useState } from "react";

import { api } from "./api/cliente";
import type { Sessao } from "./api/tipos";
import { useInstalacao } from "./instalacao";

/** Funções que o administrador pode desligar no Gerenciamento de telas (a mesma lista do servidor). */
export type Modulo =
  | "devolucoes"
  | "faltas"
  | "pedidos"
  | "loja_online"
  | "convenios"
  | "popular"
  | "controlados"
  | "servicos"
  | "comissoes"
  | "metas"
  | "promocoes"
  | "etiquetas";

export interface InfoModulo {
  id: Modulo;
  rotulo: string;
  descricao: string;
  /** Onde a função aparece, para o administrador saber o que some ao desligar. */
  aparece: string;
  /** Só liga se esta outra estiver ligada. */
  depende?: Modulo;
}

export const MODULOS: InfoModulo[] = [
  { id: "faltas", rotulo: "Faltas e encomendas", descricao: "Anotar o que o cliente pediu e não tinha, e avisar quando chegar", aparece: "menu, tela inicial e F1 no PDV" },
  { id: "devolucoes", rotulo: "Trocas e devoluções", descricao: "Devolver itens de uma venda e dar vale-troca", aparece: "menu, botão Devolver nas vendas e vale-troca no PDV" },
  { id: "pedidos", rotulo: "Pedidos e entregas", descricao: "Pedidos por WhatsApp, telefone e entrega em casa", aparece: "menu e tela inicial" },
  { id: "loja_online", rotulo: "Loja online", descricao: "Site da farmácia para o cliente pedir e pagar com Pix", aparece: "Configurações gerais e o site da farmácia", depende: "pedidos" },
  { id: "convenios", rotulo: "Convênios", descricao: "Empresas conveniadas, compras na conta da empresa e faturas", aparece: "menu, ficha do cliente e pagamento no PDV" },
  { id: "popular", rotulo: "Farmácia Popular", descricao: "Vendas do programa do governo e o que receber", aparece: "menu e pagamento no PDV" },
  { id: "controlados", rotulo: "Controlados (SNGPC)", descricao: "Livro de controlados e envio à Anvisa. A receita no PDV continua sendo pedida", aparece: "menu e tela inicial" },
  { id: "servicos", rotulo: "Serviços farmacêuticos", descricao: "Pressão, glicemia, injetáveis e declarações", aparece: "menu, tela inicial e ficha do cliente" },
  { id: "promocoes", rotulo: "Promoções", descricao: "Preços promocionais por período", aparece: "menu e tela inicial" },
  { id: "metas", rotulo: "Metas de vendas", descricao: "Metas do mês por loja e por vendedor", aparece: "menu, tela inicial e Comissões" },
  { id: "comissoes", rotulo: "Comissões", descricao: "Quanto cada vendedor ganhou (e “Minhas vendas” para a equipe)", aparece: "menu e tela inicial" },
  { id: "etiquetas", rotulo: "Etiquetas de preço", descricao: "Imprimir e trocar etiquetas de gôndola", aparece: "menu e tela inicial" },
];

const chave = (farmaciaId: string) => `ff.modulos.${farmaciaId}`;
const ouvintes = new Set<(lista: string[]) => void>();
let carregado: { farmacia: string; lista: Promise<string[]> } | null = null;

function guardado(farmaciaId: string): string[] {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave(farmaciaId)) ?? "[]");
    return Array.isArray(salvo) ? salvo : [];
  } catch {
    return [];
  }
}

function guardar(farmaciaId: string, lista: string[]) {
  try {
    localStorage.setItem(chave(farmaciaId), JSON.stringify(lista));
  } catch {
    // sem espaço: só não lembra para usar sem internet
  }
}

/** Pergunta uma vez por farmácia; sem internet, usa o que ficou guardado neste computador. */
function lerDesligados(sessao: Sessao): Promise<string[]> {
  if (carregado?.farmacia !== sessao.farmacia_id) {
    carregado = {
      farmacia: sessao.farmacia_id,
      lista: sessao.offline
        ? Promise.resolve(guardado(sessao.farmacia_id))
        : api<{ modulos_desligados?: string[]; modulos_fora_da_licenca?: string[] }>("/configuracoes")
            .then((c) => {
              // O que a licença não inclui fica desligado como o que o administrador desligou.
              const lista = [...(c.modulos_desligados ?? []), ...(c.modulos_fora_da_licenca ?? [])];
              guardar(sessao.farmacia_id, lista);
              return lista;
            })
            .catch(() => {
              carregado = null;
              return guardado(sessao.farmacia_id);
            }),
    };
  }
  return carregado.lista;
}

/** Depois de salvar no Gerenciamento de telas: atualiza o menu e as telas abertas na hora. */
export function avisarModulos(farmaciaId: string, lista: string[]) {
  carregado = { farmacia: farmaciaId, lista: Promise.resolve(lista) };
  guardar(farmaciaId, lista);
  ouvintes.forEach((ouvir) => ouvir(lista));
}

/** Se a função está ligada, considerando a que ela depende. */
export function estaLigado(desligados: readonly string[], modulo: Modulo): boolean {
  const info = MODULOS.find((m) => m.id === modulo);
  return !desligados.includes(modulo) && !(info?.depende && desligados.includes(info.depende));
}

export function useModulos(sessao: Sessao | null) {
  const instalacao = useInstalacao();
  const [desligados, setDesligados] = useState<string[]>(() => (sessao ? guardado(sessao.farmacia_id) : []));

  useEffect(() => {
    if (!sessao) return;
    let vivo = true;
    lerDesligados(sessao).then((lista) => vivo && setDesligados(lista));
    const ouvir = (lista: string[]) => vivo && setDesligados(lista);
    ouvintes.add(ouvir);
    return () => {
      vivo = false;
      ouvintes.delete(ouvir);
    };
  }, [sessao]);

  function ligado(modulo: Modulo): boolean {
    // Instalado na farmácia, a loja online não existe, mesmo ligada.
    if (modulo === "loja_online" && instalacao && !instalacao.loja_online) return false;
    return estaLigado(desligados, modulo);
  }

  return { desligados, ligado };
}

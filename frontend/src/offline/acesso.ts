// Login sem internet. Quando o operador entra com internet num PDV, o sistema guarda neste
// computador um acesso dele (vale 7 dias) cifrado com a própria senha (PBKDF2 + AES-GCM).
// Sem internet, a senha digitada só confere se conseguir decifrar esse acesso: a senha em si
// nunca fica guardada.

import type { Sessao } from "../api/tipos";
import { ACESSOS, operar } from "./banco";

export interface AcessoGuardado {
  email: string;
  nome: string;
  expira_em: string;
  guardado_em: string;
  sal: string;
  iv: string;
  cifra: string;
}

interface Conteudo {
  sessao: Sessao;
  token_offline: string;
}

const VOLTAS = 210_000;

const paraBase64 = (dados: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(dados instanceof Uint8Array ? dados : new Uint8Array(dados))));
const deBase64 = (texto: string) => Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));

async function chaveDaSenha(senha: string, sal: Uint8Array): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(senha), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: sal as BufferSource, iterations: VOLTAS },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function cifrar(email: string, senha: string, conteudo: Conteudo, expiraEm: string, agora = new Date()): Promise<AcessoGuardado> {
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const chave = await chaveDaSenha(senha, sal);
  const cifra = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv as BufferSource },
    chave,
    new TextEncoder().encode(JSON.stringify(conteudo)),
  );
  return {
    email: email.trim().toLowerCase(),
    nome: conteudo.sessao.nome,
    expira_em: expiraEm,
    guardado_em: agora.toISOString(),
    sal: paraBase64(sal),
    iv: paraBase64(iv),
    cifra: paraBase64(cifra),
  };
}

/** Decifra com a senha digitada. Senha errada: o AES-GCM recusa e devolve null. */
export async function decifrar(acesso: AcessoGuardado, senha: string): Promise<Conteudo | null> {
  try {
    const chave = await chaveDaSenha(senha, deBase64(acesso.sal));
    const claro = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: deBase64(acesso.iv) as BufferSource },
      chave,
      deBase64(acesso.cifra) as BufferSource,
    );
    return JSON.parse(new TextDecoder().decode(claro)) as Conteudo;
  } catch {
    return null;
  }
}

/** O token ainda vale? Lê a validade de dentro dele (sem conferir assinatura: isso é do servidor). */
export function tokenValido(token: string, agora = new Date()): boolean {
  try {
    const corpo = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof corpo.exp === "number" && corpo.exp * 1000 > agora.getTime() + 60_000;
  } catch {
    return false;
  }
}

/** A sessão para trabalhar sem internet: o login normal se ainda vale, senão o acesso offline. */
export function sessaoSemInternet(conteudo: Conteudo, agora = new Date()): Sessao {
  const normal = conteudo.sessao.access_token;
  return {
    ...conteudo.sessao,
    access_token: tokenValido(normal, agora) ? normal : conteudo.token_offline,
    token_offline: conteudo.token_offline,
    offline: true,
  };
}

export const guardarAcesso = (acesso: AcessoGuardado) => operar<void>(ACESSOS, "readwrite", (s) => s.put(acesso));

const lerAcesso = (email: string) =>
  operar<AcessoGuardado | undefined>(ACESSOS, "readonly", (s) => s.get(email.trim().toLowerCase()));

export const acessosGuardados = () =>
  operar<AcessoGuardado[]>(ACESSOS, "readonly", (s) => s.getAll()).catch(() => [] as AcessoGuardado[]);

export async function entrarSemInternet(email: string, senha: string, agora = new Date()): Promise<Sessao> {
  const acesso = await lerAcesso(email).catch(() => undefined);
  if (!acesso) {
    throw new Error("Sem internet. Este operador ainda não entrou neste caixa com internet, então não dá para conferir a senha aqui.");
  }
  if (new Date(acesso.expira_em) <= agora) {
    throw new Error("Sem internet. O acesso deste operador neste caixa venceu (vale 7 dias): entre com internet para renovar.");
  }
  const conteudo = await decifrar(acesso, senha);
  if (!conteudo) throw new Error("E-mail ou senha inválidos");
  return sessaoSemInternet(conteudo, agora);
}

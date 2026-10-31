import type { Sessao } from "./tipos";

const CHAVE_SESSAO = "ff.sessao";
const CHAVE_TERMINAL = "ff.terminal";

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

export function lerSessao(): Sessao | null {
  try {
    const bruto = localStorage.getItem(CHAVE_SESSAO);
    return bruto ? (JSON.parse(bruto) as Sessao) : null;
  } catch {
    return null;
  }
}

export function salvarSessao(sessao: Sessao | null) {
  if (sessao) localStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
  else localStorage.removeItem(CHAVE_SESSAO);
}

/**
 * Chave do PDV registrado neste computador. Fica no navegador, e não no
 * login, porque identifica a máquina e não a pessoa.
 */
export function lerChaveTerminal(): string | null {
  try {
    return localStorage.getItem(CHAVE_TERMINAL);
  } catch {
    return null;
  }
}

export function salvarChaveTerminal(chave: string | null) {
  if (chave) localStorage.setItem(CHAVE_TERMINAL, chave);
  else localStorage.removeItem(CHAVE_TERMINAL);
}

/** Tira a mensagem legível de um erro da API (FastAPI devolve `detail`). */
function mensagemDoErro(corpo: unknown, status: number): string {
  const detail = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // Erro de validação (422): mostra o primeiro campo com problema.
    const primeiro = detail[0] as { loc?: string[]; msg?: string };
    const campo = primeiro.loc?.slice(1).join(".");
    return campo ? `${campo}: ${primeiro.msg}` : (primeiro.msg ?? "Dados inválidos");
  }
  return `Erro ${status}`;
}

export async function api<T>(caminho: string, opcoes: { metodo?: string; corpo?: unknown } = {}): Promise<T> {
  const sessao = lerSessao();
  const terminal = lerChaveTerminal();
  const resposta = await fetch(`/api/v1${caminho}`, {
    method: opcoes.metodo ?? (opcoes.corpo === undefined ? "GET" : "POST"),
    headers: {
      "Content-Type": "application/json",
      ...(sessao ? { Authorization: `Bearer ${sessao.access_token}` } : {}),
      ...(terminal ? { "X-Terminal": terminal } : {}),
    },
    body: opcoes.corpo === undefined ? undefined : JSON.stringify(opcoes.corpo),
  });

  if (resposta.status === 401 && sessao) {
    // Token expirou: volta para o login.
    salvarSessao(null);
    window.location.assign("/login");
  }
  if (resposta.status === 204) return undefined as T;

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ErroApi(resposta.status, mensagemDoErro(corpo, resposta.status));
  return corpo as T;
}

/** Baixa um arquivo da API (ZIP, TXT) com o login e entrega ao navegador para salvar. */
export async function baixar(caminho: string): Promise<void> {
  const sessao = lerSessao();
  const resposta = await fetch(`/api/v1${caminho}`, {
    headers: sessao ? { Authorization: `Bearer ${sessao.access_token}` } : {},
  });
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new ErroApi(resposta.status, mensagemDoErro(corpo, resposta.status));
  }
  const nome = /filename="([^"]+)"/.exec(resposta.headers.get("Content-Disposition") ?? "")?.[1] ?? "arquivo";
  const url = URL.createObjectURL(await resposta.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.click();
  URL.revokeObjectURL(url);
}

export function mensagem(erro: unknown): string {
  return erro instanceof Error ? erro.message : String(erro);
}

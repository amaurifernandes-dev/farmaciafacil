/** Fala pelo microfone com o reconhecimento de voz do próprio navegador (Chrome e Edge). */

interface ResultadoFala {
  isFinal: boolean;
  0: { transcript: string };
}

interface EventoFala {
  resultIndex: number;
  results: ArrayLike<ResultadoFala>;
}

export interface Reconhecedor {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((evento: EventoFala) => void) | null;
  onerror: ((evento: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

type Construtor = new () => Reconhecedor;

function construtor(): Construtor | null {
  const w = window as unknown as { SpeechRecognition?: Construtor; webkitSpeechRecognition?: Construtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function temMicrofone(): boolean {
  return typeof window !== "undefined" && construtor() !== null;
}

/** Junta os pedaços reconhecidos até agora num texto só. */
export function textoDaFala(resultados: ArrayLike<ResultadoFala>): string {
  let texto = "";
  for (let i = 0; i < resultados.length; i++) texto += resultados[i][0].transcript;
  return texto.replace(/\s+/g, " ").trim();
}

export const ERROS_MICROFONE: Record<string, string> = {
  "not-allowed": "O navegador não deixou usar o microfone. Libere o microfone no cadeado ao lado do endereço.",
  "service-not-allowed": "O navegador não deixou usar o microfone. Libere o microfone no cadeado ao lado do endereço.",
  "no-speech": "Não ouvi nada. Clique no microfone e fale de novo.",
  "audio-capture": "Nenhum microfone encontrado neste computador.",
  network: "O reconhecimento de voz precisa de internet.",
};

/**
 * Escuta até a pessoa parar de falar. `aoOuvir` recebe o texto parcial enquanto ela fala;
 * `aoTerminar` recebe o texto final (vazio se não ouviu nada) ou a mensagem de erro.
 */
export function ouvir(aoOuvir: (texto: string) => void, aoTerminar: (texto: string, erro?: string) => void) {
  const Classe = construtor();
  if (!Classe) {
    aoTerminar("", "Este navegador não reconhece voz. Use o Chrome ou o Edge, ou digite.");
    return () => {};
  }
  const reconhecedor = new Classe();
  reconhecedor.lang = "pt-BR";
  reconhecedor.continuous = false;
  reconhecedor.interimResults = true;
  let texto = "";
  let erro: string | undefined;
  reconhecedor.onresult = (evento) => {
    texto = textoDaFala(evento.results);
    aoOuvir(texto);
  };
  reconhecedor.onerror = (evento) => {
    if (evento.error !== "aborted") erro = ERROS_MICROFONE[evento.error] ?? "O microfone falhou. Tente de novo.";
  };
  reconhecedor.onend = () => aoTerminar(texto, texto ? undefined : erro);
  reconhecedor.start();
  return () => reconhecedor.stop();
}

/** Lê a resposta em voz alta, se a pessoa ligou essa opção. */
export function falar(texto: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const fala = new SpeechSynthesisUtterance(texto);
  fala.lang = "pt-BR";
  window.speechSynthesis.speak(fala);
}

export function calar() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

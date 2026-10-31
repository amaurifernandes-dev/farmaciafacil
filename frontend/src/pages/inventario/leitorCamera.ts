/** Leitura de código de barras pela câmera do celular.
 *
 * Usa o leitor do próprio navegador quando existe (Chrome no Android) e, nos outros (iPhone),
 * carrega o ZXing só na hora de abrir a câmera.
 */

interface DetectorNativo {
  detect(fonte: HTMLVideoElement): Promise<{ rawValue: string }[]>;
}
interface ClasseDetector {
  new (opcoes: { formats: string[] }): DetectorNativo;
  getSupportedFormats(): Promise<string[]>;
}

const FORMATOS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

export type Parar = () => void;

async function nativo(video: HTMLVideoElement, aoLer: (codigo: string) => void): Promise<Parar | null> {
  const Detector = (window as unknown as { BarcodeDetector?: ClasseDetector }).BarcodeDetector;
  if (!Detector) return null;
  const suportados = await Detector.getSupportedFormats().catch(() => [] as string[]);
  const formatos = FORMATOS.filter((f) => suportados.includes(f));
  if (!formatos.includes("ean_13")) return null;
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  video.srcObject = stream;
  await video.play();
  const detector = new Detector({ formats: formatos });
  let ativo = true;
  const ciclo = async () => {
    while (ativo) {
      try {
        const achados = await detector.detect(video);
        if (achados[0]?.rawValue) aoLer(achados[0].rawValue);
      } catch {
        // quadro ainda sem imagem
      }
      await new Promise((r) => setTimeout(r, 200));
    }
  };
  void ciclo();
  return () => {
    ativo = false;
    stream.getTracks().forEach((t) => t.stop());
    video.srcObject = null;
  };
}

async function zxing(video: HTMLVideoElement, aoLer: (codigo: string) => void): Promise<Parar> {
  const [{ BrowserMultiFormatReader }, { BarcodeFormat, DecodeHintType }] = await Promise.all([
    import("@zxing/browser"),
    import("@zxing/library"),
  ]);
  const dicas = new Map();
  dicas.set(DecodeHintType.POSSIBLE_FORMATS, [
    BarcodeFormat.EAN_13,
    BarcodeFormat.EAN_8,
    BarcodeFormat.UPC_A,
    BarcodeFormat.UPC_E,
    BarcodeFormat.CODE_128,
  ]);
  const leitor = new BrowserMultiFormatReader(dicas);
  const controles = await leitor.decodeFromConstraints(
    { video: { facingMode: "environment" }, audio: false },
    video,
    (resultado) => {
      if (resultado) aoLer(resultado.getText());
    },
  );
  return () => controles.stop();
}

export async function abrirCamera(video: HTMLVideoElement, aoLer: (codigo: string) => void): Promise<Parar> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Este navegador não deixa usar a câmera. Abra pelo Chrome ou pelo Safari, num endereço https.");
  }
  try {
    return (await nativo(video, aoLer)) ?? (await zxing(video, aoLer));
  } catch (e) {
    const nome = (e as { name?: string }).name;
    if (nome === "NotAllowedError") throw new Error("Permita o uso da câmera para ler os códigos.");
    if (nome === "NotFoundError") throw new Error("Não achamos uma câmera neste aparelho.");
    throw e;
  }
}

/** Evita contar duas vezes a mesma caixa: o mesmo código lido de novo em menos de `ms` é ignorado. */
export function filtroRepetidas(ms = 1500, agora: () => number = Date.now) {
  let ultimo = "";
  let quando = 0;
  return (codigo: string): boolean => {
    const t = agora();
    if (codigo === ultimo && t - quando < ms) {
      quando = t;
      return false;
    }
    ultimo = codigo;
    quando = t;
    return true;
  };
}

/** Bipe curto e vibração para quem está contando saber que leu. */
export function avisarLeitura(ok: boolean) {
  try {
    navigator.vibrate?.(ok ? 60 : [80, 60, 80]);
    const Contexto = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Contexto) return;
    const ctx = new Contexto();
    const osc = ctx.createOscillator();
    const volume = ctx.createGain();
    osc.frequency.value = ok ? 1200 : 300;
    volume.gain.value = 0.08;
    osc.connect(volume).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + (ok ? 0.08 : 0.25));
    osc.onended = () => void ctx.close();
  } catch {
    // sem som, segue
  }
}

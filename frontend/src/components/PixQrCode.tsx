import { useMemo, useState } from "react";
import qrcode from "qrcode-generator";

/** QR Code do Pix e o código "copia e cola" com botão para copiar. */
export default function PixQrCode({ codigo, valor }: { codigo: string; valor: string }) {
  const [copiado, setCopiado] = useState(false);
  const imagem = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(codigo);
    qr.make();
    return qr.createDataURL(6, 2);
  }, [codigo]);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(codigo);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 3000);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <div className="vitrine-cartao vitrine-pix">
      <img src={imagem} alt="QR Code do Pix" />
      <div>
        <h2>Pague {valor} com Pix</h2>
        <p>Abra o app do banco, escolha pagar com Pix e aponte a câmera para o QR Code, ou copie o código abaixo.</p>
        <code>{codigo}</code>
        <button type="button" className="vitrine-botao" onClick={copiar}>
          {copiado ? "Código copiado" : "Copiar código Pix"}
        </button>
      </div>
    </div>
  );
}

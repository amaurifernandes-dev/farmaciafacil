// Ícones de traço no estilo Lucide, desenhados em 24x24.
const CAMINHOS = {
  painel: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  carrinho: "M3 3h2l2.4 12.2a2 2 0 0 0 2 1.8h8.2a2 2 0 0 0 2-1.6L21 8H6M9 21h.01M18 21h.01",
  caixa: "M2 7h20v12H2zM2 11h20M6 15h4",
  pacote: "M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
  entrada: "M12 3v12M7 10l5 5 5-5M4 21h16",
  alerta: "M12 3 2 20h20zM12 10v4M12 17h.01",
  mais: "M12 5v14M5 12h14",
  dinheiro: "M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  recibo: "M5 2h14v20l-3-2-2 2-2-2-2 2-2-2-3 2zM9 7h6M9 11h6M9 15h4",
  relogio: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  baixa: "M12 5v14M19 12l-7 7-7-7",
  subida: "M7 17 17 7M8 7h9v9",
  descida: "M7 7l10 10M17 8v9H8",
  seta: "M5 12h14M13 6l6 6-6 6",
  sair: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
} as const;

export type NomeIcone = keyof typeof CAMINHOS;

export default function Icone({ nome, tamanho = 18 }: { nome: NomeIcone; tamanho?: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={CAMINHOS[nome]} />
    </svg>
  );
}

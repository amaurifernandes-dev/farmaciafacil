// Código de barras EAN-13 / EAN-8 desenhado na hora, sem biblioteca.
// Devolve as barras como texto de 0 e 1 (cada caractere é um módulo; 1 = barra preta).

const L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"];
const R = L.map((c) => [...c].map((b) => (b === "1" ? "0" : "1")).join(""));
const G = R.map((c) => [...c].reverse().join(""));
// No EAN-13, o primeiro dígito não vira barras: ele escolhe o padrão (L ou G) dos 6 seguintes.
const PARIDADE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];

/** O dígito verificador está certo? (Mesma conta para EAN-8 e EAN-13.) */
export function eanValido(codigo: string): boolean {
  if (!/^(\d{8}|\d{13})$/.test(codigo)) return false;
  const digitos = [...codigo].map(Number);
  const verificador = digitos.pop() as number;
  const soma = digitos.reverse().reduce((total, d, i) => total + d * (i % 2 === 0 ? 3 : 1), 0);
  return (10 - (soma % 10)) % 10 === verificador;
}

/** Os módulos do código, ou null se não for um EAN-8 ou EAN-13 válido. */
export function barrasEan(codigo: string): string | null {
  if (!eanValido(codigo)) return null;
  const d = [...codigo].map(Number);
  if (d.length === 8) {
    return "101" + d.slice(0, 4).map((n) => L[n]).join("") + "01010" + d.slice(4).map((n) => R[n]).join("") + "101";
  }
  const paridade = PARIDADE[d[0]];
  const esquerda = d.slice(1, 7).map((n, i) => (paridade[i] === "L" ? L[n] : G[n])).join("");
  const direita = d.slice(7).map((n) => R[n]).join("");
  return "101" + esquerda + "01010" + direita + "101";
}

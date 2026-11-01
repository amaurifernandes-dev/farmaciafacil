import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { lerChaveTerminal, mensagem } from "../api/cliente";
import { acessosGuardados } from "../offline/acesso";
import { useSessao } from "../sessao";

export default function Login() {
  const { sessao, entrar } = useSessao();
  const voltar = (useLocation().state as { voltar?: string } | null)?.voltar;
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  // Num caixa sem internet: quem pode entrar (já entrou aqui com internet nos últimos 7 dias).
  const [semInternet, setSemInternet] = useState(!navigator.onLine);
  const [quemEntra, setQuemEntra] = useState<string[]>([]);

  useEffect(() => {
    if (!lerChaveTerminal()) return;
    const agora = new Date();
    acessosGuardados().then((lista) =>
      setQuemEntra(lista.filter((a) => new Date(a.expira_em) > agora).map((a) => a.nome)),
    );
    const caiu = () => setSemInternet(true);
    const voltou = () => setSemInternet(false);
    window.addEventListener("offline", caiu);
    window.addEventListener("online", voltou);
    return () => {
      window.removeEventListener("offline", caiu);
      window.removeEventListener("online", voltou);
    };
  }, []);

  if (sessao) return <Navigate to={voltar?.startsWith("/") && !voltar.startsWith("//") ? voltar : "/"} replace />;

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await entrar(email, senha);
    } catch (e) {
      setErro(mensagem(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="login" onSubmit={enviar}>
      <h1>FarmáciaFácil</h1>
      {semInternet && lerChaveTerminal() && (
        <p className="login-offline">
          Sem internet. Entra neste caixa quem já entrou aqui com internet nos últimos 7 dias
          {quemEntra.length > 0 ? `: ${quemEntra.join(", ")}.` : ". Ninguém ainda."}
        </p>
      )}
      <label>
        E-mail
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
      </label>
      <label>
        Senha
        <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required />
      </label>
      {erro && <p className="erro">{erro}</p>}
      <button type="submit" disabled={enviando}>
        {enviando ? "Entrando..." : "Entrar"}
      </button>
    </form>
  );
}

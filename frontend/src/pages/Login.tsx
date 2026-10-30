import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { mensagem } from "../api/cliente";
import { useSessao } from "../sessao";

export default function Login() {
  const { sessao, entrar } = useSessao();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (sessao) return <Navigate to="/" replace />;

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

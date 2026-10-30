import { Link } from "react-router-dom";

import Icone from "../../components/Icone";
import { CONFIGURACOES } from "../../components/Layout";
import { useSessao } from "../../sessao";

export default function ConfiguracoesInicio() {
  const { sessao } = useSessao();
  return (
    <div className="pagina">
      <p className="sobretitulo">Configurações</p>
      <h1>Cadastros e configurações</h1>
      <p className="vazio">Tudo o que organiza a sua farmácia, num lugar só.</p>
      <div className="grade-atalhos">
        {CONFIGURACOES.filter((item) => !item.pode || item.pode(sessao)).map((item) => (
          <Link key={item.para} to={item.para} className="cartao atalho-config">
            <span className="atalho-icone">
              <Icone nome={item.icone} />
            </span>
            <span>
              <strong>{item.rotulo}</strong>
              <small>{item.descricao}</small>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

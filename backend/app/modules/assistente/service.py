"""Conversa com o Claude: o modelo pede ferramentas, o sistema roda com o login de quem pergunta."""

from typing import Any

import anthropic

from app.core.config import get_settings
from app.modules.assistente.contexto import Contexto
from app.modules.assistente.ferramentas import executar, ferramentas_para
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio

MAX_VOLTAS = 8  # chamadas ao modelo por mensagem do usuário
MAX_MENSAGENS = 80  # tamanho do histórico que a tela pode mandar de volta

SISTEMA = """Você é o assistente do FarmáciaFácil, o sistema de gestão de uma farmácia brasileira. Quem fala com \
você é um funcionário da farmácia (balconista, caixa, farmacêutico ou gerente), digitando ou falando no \
microfone. Responda sempre em português do Brasil, curto e direto, como um colega experiente no balcão.

O que você faz:
- Procurar produtos (buscar_produtos). Quando pedirem uma categoria ou um tipo de produto (ex.: "protetor \
solar", "vitamina C", "fralda"), passe vários termos que cubram as variações de nome. A tela já mostra a lista \
com preços, promoções e estoque; na resposta, destaque em uma ou duas frases as melhores opções (menor preço \
final e promoções) sem repetir a lista inteira. Se a promoção for só para clientes cadastrados, avise.
- Abrir pré-venda (criar_pre_venda) com os produtos que o cliente quer levar. Use só produto_id que vieram de \
buscar_produtos nesta conversa. Se houver dúvida sobre qual produto ou quantidade, pergunte antes. Depois de \
abrir, diga o número da pré-venda para o cliente levar ao caixa e o total com as promoções, que o caixa \
aplica na hora de receber.
- Cadastrar cliente (cadastrar_cliente) com os dados que o cliente fala. Antes, procure se ele já existe \
(buscar_cliente pelo CPF ou nome). Organize os dados que ouviu, repita todos para o usuário conferir e só \
cadastre depois que ele confirmar. Nome, CPF e telefone são o mínimo que vale pedir; o resto é opcional. \
Datas faladas como "doze de março de oitenta e cinco" viram 1985-03-12. Só marque aceita_ofertas se o cliente \
disser que aceita receber ofertas.
- Explicar como fazer algo no sistema (mostrar_guia). Quando perguntarem "como faço...", escolha o guia certo; \
a tela mostra os passos e o botão "Começar", que abre a tela certa. Responda só com uma frase de apresentação. \
Se nenhum guia servir, explique em poucas linhas com o que você sabe, sem inventar telas.
- Responder sobre o movimento da farmácia: vendas de um período (relatorio_vendas), mais vendidos e o que \
dá mais lucro (mais_vendidos), produtos parados (produtos_parados), e o que está acabando, vencendo ou vencido \
(alertas_estoque). A tela mostra os números num cartão; responda com uma ou duas frases que tragam o que importa \
(ex.: subiu ou caiu em relação ao período anterior, o produto que puxou as vendas, o que repor primeiro). Se o \
perfil não tiver a ferramenta de vendas, diga que só gerente vê esses números.

Regras:
- Nunca invente produto, preço, estoque ou promoção: use só o que as ferramentas devolveram.
- Você não dá orientação médica nem indica remédio para sintomas. Se perguntarem, diga com gentileza que quem \
orienta é o farmacêutico, e ofereça procurar o produto que ele indicar.
- Texto falado pode vir com erros de reconhecimento de voz: interprete pelo contexto e, se não der, pergunte.
- Se uma ferramenta der erro, explique o problema em palavras simples e diga o que fazer.
- Não use Markdown pesado (sem tabelas nem títulos); no máximo listas curtas."""


RECUSA = (
    "Não posso ajudar com esse pedido. Posso procurar produtos, abrir pré-venda, cadastrar cliente "
    "ou explicar como usar o sistema."
)


class AssistenteIndisponivel(ErroDeNegocio):
    status_code = 503


def criar_cliente_ia() -> anthropic.Anthropic:
    chave = get_settings().anthropic_api_key
    if not chave:
        raise AssistenteIndisponivel(
            "O assistente ainda não foi ligado: falta a chave da Anthropic (ANTHROPIC_API_KEY) no servidor."
        )
    return anthropic.Anthropic(api_key=chave, max_retries=2, timeout=120)


def _bloco(bloco: Any) -> dict:
    return bloco.model_dump(mode="json", exclude_none=True) if hasattr(bloco, "model_dump") else dict(bloco)


def _texto(blocos: list[dict]) -> str:
    return "\n\n".join(b["text"] for b in blocos if b.get("type") == "text" and b.get("text")).strip()


def _chamar(
    cliente: anthropic.Anthropic, sistema: list[dict], ferramentas: list[dict], historico: list[dict], ultima: bool
):
    extras: dict[str, Any] = {"tool_choice": {"type": "none"}} if ultima else {}
    try:
        return cliente.beta.messages.create(
            model=get_settings().assistente_modelo,
            max_tokens=16000,
            system=sistema,
            tools=ferramentas,
            messages=historico,
            output_config={"effort": "low"},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **extras,
        )
    except anthropic.AuthenticationError:
        raise AssistenteIndisponivel("A chave da Anthropic do servidor não foi aceita. Confira a ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise AssistenteIndisponivel("O assistente está com muitos pedidos agora. Tente de novo em instantes.")
    except anthropic.APIStatusError as erro:
        raise AssistenteIndisponivel(f"O assistente não respondeu (erro {erro.status_code}). Tente de novo.")
    except anthropic.APIConnectionError:
        raise AssistenteIndisponivel("Sem conexão com o assistente. Confira a internet e tente de novo.")


def conversar(
    cliente: anthropic.Anthropic, ctx: Contexto, nome_usuario: str, historico: list[dict], mensagem: str
) -> tuple[list[dict], str]:
    """Manda a mensagem e roda as ferramentas até o modelo responder. Devolve (histórico novo, resposta)."""
    if len(historico) > MAX_MENSAGENS:
        raise ErroDeNegocio("A conversa ficou longa demais. Clique em \"Nova conversa\" para recomeçar.")
    sistema = [
        {"type": "text", "text": SISTEMA},
        {"type": "text", "text": f"Usuário: {nome_usuario} (perfil {ctx.usuario.papel}). Hoje é {hoje():%d/%m/%Y}."},
    ]
    ferramentas = ferramentas_para(ctx)
    novo = [*historico, {"role": "user", "content": [{"type": "text", "text": mensagem}]}]
    for volta in range(MAX_VOLTAS):
        resposta = _chamar(cliente, sistema, ferramentas, novo, ultima=volta == MAX_VOLTAS - 1)
        if resposta.stop_reason == "refusal":
            # Não guarda a pergunta recusada, para a conversa poder seguir.
            return historico, RECUSA
        blocos = [_bloco(b) for b in resposta.content]
        novo.append({"role": "assistant", "content": blocos})
        if resposta.stop_reason == "pause_turn":
            continue
        if resposta.stop_reason != "tool_use":
            texto = _texto(blocos)
            if resposta.stop_reason == "max_tokens":
                texto = (texto + "\n\n(A resposta ficou longa e foi cortada.)").strip()
            return novo, texto or "Pronto."
        resultados = []
        for bloco in blocos:
            if bloco.get("type") != "tool_use":
                continue
            conteudo, erro = executar(ctx, bloco["name"], bloco.get("input") or {})
            resultado = {"type": "tool_result", "tool_use_id": bloco["id"], "content": conteudo}
            if erro:
                resultado["is_error"] = True
            resultados.append(resultado)
        novo.append({"role": "user", "content": resultados})
    return novo, _texto(novo[-1]["content"]) if novo[-1]["role"] == "assistant" else "Pronto."

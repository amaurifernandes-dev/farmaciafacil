"""Provedores que transmitem a NFC-e à SEFAZ.

O resto do sistema só conhece `ProvedorFiscal` e `ResultadoNota`. Trocar a Focus NFe por
outro provedor é escrever outra classe com os mesmos três métodos.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.shared.datas import FUSO


@dataclass
class ResultadoNota:
    # Mesmos valores de STATUS_NOTA, mais "nao_encontrada" na consulta de uma referência que o provedor não tem.
    status: str
    mensagem: str | None = None
    status_sefaz: str | None = None
    numero: str | None = None
    serie: str | None = None
    chave: str | None = None
    url_xml: str | None = None
    url_danfe: str | None = None
    url_qrcode: str | None = None
    url_consulta: str | None = None
    url_xml_cancelamento: str | None = None


class ProvedorFiscal(Protocol):
    def emitir(self, ambiente: str, ref: str, nota: dict) -> ResultadoNota: ...

    def consultar(self, ambiente: str, ref: str) -> ResultadoNota: ...

    def cancelar(self, ambiente: str, ref: str, justificativa: str) -> ResultadoNota: ...


class FocusNFe:
    """Cliente da API v2 da Focus NFe. A emissão de NFC-e lá é síncrona."""

    HOSTS = {
        "homologacao": "https://homologacao.focusnfe.com.br",
        "producao": "https://api.focusnfe.com.br",
    }
    STATUS = {
        "autorizado": "autorizada",
        "erro_autorizacao": "rejeitada",
        "denegado": "rejeitada",
        "processando_autorizacao": "processando",
        "cancelado": "cancelada",
    }

    def __init__(self, tokens: dict[str, str], transport: httpx.BaseTransport | None = None, timeout: float = 30):
        self.tokens = tokens
        self.transport = transport
        self.timeout = timeout

    def _cliente(self, ambiente: str) -> httpx.Client:
        token = self.tokens.get(ambiente)
        if not token:
            raise ErroDeConfiguracao(f"Token da Focus NFe para {ambiente} não configurado")
        return httpx.Client(
            base_url=self.HOSTS[ambiente], auth=(token, ""), timeout=self.timeout, transport=self.transport
        )

    def _url(self, ambiente: str, caminho: str | None) -> str | None:
        # A Focus devolve os arquivos como caminho relativo ao host.
        if not caminho or caminho.startswith("http"):
            return caminho
        return self.HOSTS[ambiente] + caminho

    def _resultado(self, ambiente: str, corpo: dict) -> ResultadoNota:
        status_focus = corpo.get("status", "")
        return ResultadoNota(
            status=self.STATUS.get(status_focus, "erro"),
            mensagem=corpo.get("mensagem_sefaz") or corpo.get("mensagem") or status_focus or None,
            status_sefaz=corpo.get("status_sefaz"),
            numero=corpo.get("numero"),
            serie=corpo.get("serie"),
            chave=(corpo.get("chave_nfe") or "").removeprefix("NFe") or None,
            url_xml=self._url(ambiente, corpo.get("caminho_xml_nota_fiscal")),
            url_danfe=self._url(ambiente, corpo.get("caminho_danfe")),
            url_qrcode=corpo.get("qrcode_url"),
            url_consulta=corpo.get("url_consulta_nf"),
            url_xml_cancelamento=self._url(ambiente, corpo.get("caminho_xml_cancelamento")),
        )

    @staticmethod
    def _erro(resposta: httpx.Response) -> ResultadoNota:
        try:
            corpo = resposta.json()
        except ValueError:
            return ResultadoNota(status="erro", mensagem=f"Focus NFe respondeu {resposta.status_code}")
        mensagem = corpo.get("mensagem") or f"Focus NFe respondeu {resposta.status_code}"
        detalhes = [e.get("mensagem") for e in corpo.get("erros") or [] if e.get("mensagem")]
        if detalhes:
            mensagem = f"{mensagem}: {'; '.join(detalhes)}"
        if corpo.get("codigo") == "pending_operation":
            return ResultadoNota(status="processando", mensagem=mensagem)
        return ResultadoNota(status="erro", mensagem=mensagem[:500])

    def emitir(self, ambiente: str, ref: str, nota: dict) -> ResultadoNota:
        try:
            with self._cliente(ambiente) as cliente:
                resposta = cliente.post("/v2/nfce", params={"ref": ref}, json=nota)
        except httpx.ConnectError:
            return ResultadoNota(status="erro", mensagem="Não foi possível conectar à Focus NFe")
        except httpx.HTTPError:
            # Pode ter chegado lá: fica "processando" e a próxima tentativa consulta antes de reenviar.
            return ResultadoNota(status="processando", mensagem="Sem resposta da Focus NFe")
        if resposta.status_code == 422 and resposta.json().get("codigo") == "already_processed":
            return self.consultar(ambiente, ref)
        if resposta.status_code >= 500:
            return ResultadoNota(status="processando", mensagem=f"Focus NFe respondeu {resposta.status_code}")
        if resposta.status_code >= 400:
            return self._erro(resposta)
        return self._resultado(ambiente, resposta.json())

    def consultar(self, ambiente: str, ref: str) -> ResultadoNota:
        try:
            with self._cliente(ambiente) as cliente:
                resposta = cliente.get(f"/v2/nfce/{ref}")
        except httpx.HTTPError:
            return ResultadoNota(status="processando", mensagem="Sem resposta da Focus NFe")
        if resposta.status_code == 404:
            return ResultadoNota(status="nao_encontrada")
        if resposta.status_code >= 400:
            return self._erro(resposta)
        return self._resultado(ambiente, resposta.json())

    def cancelar(self, ambiente: str, ref: str, justificativa: str) -> ResultadoNota:
        try:
            with self._cliente(ambiente) as cliente:
                resposta = cliente.request("DELETE", f"/v2/nfce/{ref}", json={"justificativa": justificativa})
        except httpx.HTTPError:
            return ResultadoNota(status="erro", mensagem="Sem resposta da Focus NFe")
        if resposta.status_code >= 400:
            return self._erro(resposta)
        corpo = resposta.json()
        if corpo.get("status") != "cancelado":
            return ResultadoNota(status="erro", mensagem=corpo.get("mensagem_sefaz") or "Cancelamento recusado")
        return self._resultado(ambiente, corpo)


class ProvedorFalso:
    """Simula a SEFAZ em memória: autoriza tudo e numera em sequência. Só para desenvolvimento e testes."""

    def __init__(self):
        self.notas: dict[str, ResultadoNota] = {}
        self.enviadas: dict[str, dict] = {}
        self.proxima_resposta: ResultadoNota | None = None

    def emitir(self, ambiente: str, ref: str, nota: dict) -> ResultadoNota:
        self.enviadas[ref] = nota
        if self.proxima_resposta is not None:
            resultado, self.proxima_resposta = self.proxima_resposta, None
            if resultado.status != "erro":
                self.notas[ref] = resultado
            return resultado
        if ref in self.notas and self.notas[ref].status == "autorizada":
            return self.notas[ref]
        numero = str(len(self.notas) + 1)
        chave = datetime.now(FUSO).strftime("35%y%m") + nota["cnpj_emitente"] + "65001" + numero.zfill(9)
        chave = (chave + "0" * 44)[:44]
        self.notas[ref] = ResultadoNota(
            status="autorizada",
            mensagem="Autorizado o uso da NF-e",
            status_sefaz="100",
            numero=numero,
            serie="1",
            chave=chave,
            url_danfe=f"https://nfce.exemplo/{ref}.html",
            url_xml=f"https://nfce.exemplo/{ref}.xml",
        )
        return self.notas[ref]

    def consultar(self, ambiente: str, ref: str) -> ResultadoNota:
        return self.notas.get(ref) or ResultadoNota(status="nao_encontrada")

    def cancelar(self, ambiente: str, ref: str, justificativa: str) -> ResultadoNota:
        nota = self.notas.get(ref)
        if nota is None or nota.status != "autorizada":
            return ResultadoNota(status="erro", mensagem="Nota fiscal não autorizada")
        nota.status = "cancelada"
        nota.status_sefaz = "135"
        nota.mensagem = "Evento registrado e vinculado a NF-e"
        nota.url_xml_cancelamento = f"https://nfce.exemplo/{ref}-can.xml"
        return nota


class ErroDeConfiguracao(Exception):
    pass


_falso = ProvedorFalso()


def get_provedor() -> ProvedorFiscal | None:
    """Provedor configurado no ambiente, ou None se a emissão estiver desligada."""
    settings = get_settings()
    if settings.nfce_provedor == "focus":
        return FocusNFe(
            {"homologacao": settings.focus_nfe_token_homologacao, "producao": settings.focus_nfe_token_producao}
        )
    if settings.nfce_provedor == "falso":
        return _falso
    return None

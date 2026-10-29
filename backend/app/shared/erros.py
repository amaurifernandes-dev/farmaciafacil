from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErroDeNegocio(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao usuário."""

    status_code = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class NaoEncontrado(ErroDeNegocio):
    status_code = 404


class SemPermissao(ErroDeNegocio):
    status_code = 403


class Conflito(ErroDeNegocio):
    status_code = 409


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroDeNegocio)
    def _tratar(request: Request, erro: ErroDeNegocio) -> JSONResponse:
        return JSONResponse(status_code=erro.status_code, content={"detail": erro.mensagem})

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.vendas import service
from app.modules.vendas.schemas import (
    CaixaAbrir,
    CaixaFechar,
    CaixaSaida,
    ResumoCaixa,
    VendaCancelar,
    VendaCriar,
    VendaSaida,
)
from app.shared.erros import NaoEncontrado

caixas = APIRouter(prefix="/caixas", tags=["caixa"])
vendas = APIRouter(prefix="/vendas", tags=["vendas"])


@caixas.post("/abrir", status_code=status.HTTP_201_CREATED)
def abrir(db: DB, usuario: UsuarioAtual, dados: CaixaAbrir) -> CaixaSaida:
    return service.abrir_caixa(db, usuario.usuario_id, dados.valor_abertura)


@caixas.get("/atual")
def atual(db: DB, usuario: UsuarioAtual) -> ResumoCaixa:
    caixa = service.caixa_aberto(db, usuario.usuario_id)
    if caixa is None:
        raise NaoEncontrado("Nenhum caixa aberto")
    return service.resumo_caixa(db, caixa)


@caixas.get("/{caixa_id}")
def resumo(db: DB, _: Gerente, caixa_id: UUID) -> ResumoCaixa:
    return service.resumo_caixa(db, service.obter_caixa(db, caixa_id))


@caixas.post("/{caixa_id}/fechar")
def fechar(db: DB, usuario: UsuarioAtual, caixa_id: UUID, dados: CaixaFechar) -> ResumoCaixa:
    return service.fechar_caixa(db, usuario, caixa_id, dados.valor_fechamento_informado)


@vendas.post("", status_code=status.HTTP_201_CREATED)
def registrar(db: DB, usuario: UsuarioAtual, dados: VendaCriar, response: Response) -> VendaSaida:
    venda, criada = service.registrar_venda(db, usuario, dados)
    if not criada:
        response.status_code = status.HTTP_200_OK
    return venda


@vendas.get("")
def listar(
    db: DB,
    caixa_id: UUID | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[VendaSaida]:
    return service.listar_vendas(db, caixa_id, pagina, por_pagina)


@vendas.get("/{venda_id}")
def obter(db: DB, venda_id: UUID) -> VendaSaida:
    return service.obter_venda(db, venda_id)


@vendas.post("/{venda_id}/cancelar")
def cancelar(db: DB, usuario: Gerente, venda_id: UUID, dados: VendaCancelar) -> VendaSaida:
    return service.cancelar_venda(db, usuario, venda_id, dados.motivo)

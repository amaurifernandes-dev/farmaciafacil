from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.deps import DB, Atendimento, Gerente, UsuarioAtual
from app.modules.lojas.deps import TerminalAtual
from app.modules.fiscal import service as fiscal
from app.modules.fiscal.router import Provedor
from app.modules.vendas import service
from app.modules.vendas.schemas import (
    CaixaAbrir,
    CaixaFechar,
    CaixaSaida,
    MovimentoCriar,
    PreVendaCriar,
    PreVendaSaida,
    RelatorioCaixas,
    ResumoCaixa,
    VendaCancelar,
    VendaCriar,
    VendaSaida,
)
from app.shared.datas import hoje
from app.shared.erros import NaoEncontrado

caixas = APIRouter(prefix="/caixas", tags=["caixa"])
vendas = APIRouter(prefix="/vendas", tags=["vendas"])
pre_vendas = APIRouter(prefix="/pre-vendas", tags=["pré-vendas"])


@caixas.post("/abrir", status_code=status.HTTP_201_CREATED)
def abrir(db: DB, usuario: UsuarioAtual, terminal: TerminalAtual, dados: CaixaAbrir) -> CaixaSaida:
    """Abre o caixa do PDV identificado pelo cabeçalho X-Terminal."""
    return service.abrir_caixa(db, usuario, terminal, dados)


@caixas.get("/atual")
def atual(db: DB, usuario: UsuarioAtual, terminal: TerminalAtual) -> ResumoCaixa:
    """Caixa aberto neste PDV; sem PDV, o caixa aberto pelo usuário em qualquer PDV."""
    caixa = service.caixa_do_terminal(db, terminal) if terminal else service.caixa_do_usuario(db, usuario.usuario_id)
    if caixa is None:
        raise NaoEncontrado("Nenhum caixa aberto")
    return service.resumo_caixa(db, caixa)


@caixas.get("")
def listar(
    db: DB,
    _: Gerente,
    situacao: Literal["aberto", "fechado"] | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[ResumoCaixa]:
    return service.listar_caixas(db, situacao, pagina, por_pagina)


@caixas.get("/relatorio")
def relatorio(db: DB, _: Gerente, dia: date | None = None, loja_id: UUID | None = None) -> RelatorioCaixas:
    """Fechamento do dia: todos os caixas abertos na data, por forma de pagamento."""
    return service.relatorio_do_dia(db, dia or hoje(), loja_id)


@caixas.get("/{caixa_id}")
def resumo(db: DB, _: Gerente, caixa_id: UUID) -> ResumoCaixa:
    return service.resumo_caixa(db, service.obter_caixa(db, caixa_id))


@caixas.post("/{caixa_id}/fechar")
def fechar(db: DB, usuario: UsuarioAtual, caixa_id: UUID, dados: CaixaFechar) -> ResumoCaixa:
    return service.fechar_caixa(db, usuario, caixa_id, dados)


@caixas.post("/{caixa_id}/movimentos", status_code=status.HTTP_201_CREATED)
def movimento(db: DB, usuario: UsuarioAtual, caixa_id: UUID, dados: MovimentoCriar) -> ResumoCaixa:
    """Sangria ou suprimento: tira ou põe dinheiro na gaveta com o caixa aberto."""
    return service.lancar_movimento(db, usuario, caixa_id, dados)


@vendas.post("", status_code=status.HTTP_201_CREATED)
def registrar(
    db: DB, usuario: UsuarioAtual, terminal: TerminalAtual, provedor: Provedor, dados: VendaCriar, response: Response
) -> VendaSaida:
    venda, criada = service.registrar_venda(db, usuario, terminal, dados)
    if criada:
        # A venda já está gravada. Se a NFC-e falhar, o PDV mostra o aviso e dá para reenviar.
        fiscal.emitir_apos_venda(db, provedor, venda)
    else:
        response.status_code = status.HTTP_200_OK
    return venda


@vendas.get("")
def listar_vendas(
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
def cancelar(db: DB, usuario: Gerente, provedor: Provedor, venda_id: UUID, dados: VendaCancelar) -> VendaSaida:
    venda = service.obter_venda(db, venda_id)
    if venda.status != "cancelada":
        fiscal.cancelar_nfce(db, provedor, venda, dados.motivo)
    return service.cancelar_venda(db, usuario, venda_id, dados.motivo)


@pre_vendas.post("", status_code=status.HTTP_201_CREATED)
def criar_pre_venda(db: DB, usuario: Atendimento, terminal: TerminalAtual, dados: PreVendaCriar) -> PreVendaSaida:
    return service.saida_pre_venda(db, service.criar_pre_venda(db, usuario, terminal, dados))


@pre_vendas.get("")
def listar_pre_vendas(
    db: DB,
    situacao: Literal["aberta", "recebida", "cancelada"] | None = "aberta",
    loja_id: UUID | None = None,
) -> list[PreVendaSaida]:
    return [service.saida_pre_venda(db, p) for p in service.listar_pre_vendas(db, situacao, loja_id)]


@pre_vendas.get("/numero/{numero}")
def obter_pre_venda_pelo_numero(db: DB, numero: int) -> PreVendaSaida:
    return service.saida_pre_venda(db, service.pre_venda_pelo_numero(db, numero))


@pre_vendas.get("/{pre_venda_id}")
def obter_pre_venda(db: DB, pre_venda_id: UUID) -> PreVendaSaida:
    return service.saida_pre_venda(db, service.obter_pre_venda(db, pre_venda_id))


@pre_vendas.post("/{pre_venda_id}/cancelar")
def cancelar_pre_venda(db: DB, _: Atendimento, pre_venda_id: UUID) -> PreVendaSaida:
    return service.saida_pre_venda(db, service.cancelar_pre_venda(db, pre_venda_id))

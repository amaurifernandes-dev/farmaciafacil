from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Gerente, Operador, UsuarioAtual
from app.modules.financeiro import service
from app.modules.financeiro.models import CATEGORIAS
from app.modules.financeiro.schemas import (
    Categoria,
    Categorias,
    ContaAtualizar,
    ContaBaixar,
    ContaCriar,
    ContaSaida,
    CreditoCliente,
    FluxoCaixa,
    PaginaContas,
    Situacao,
    Tipo,
)
from app.modules.lojas.deps import TerminalAtual
from app.modules.vendas.service import caixa_do_terminal
from app.shared.datas import hoje
from app.shared.erros import SemPermissao

router = APIRouter(prefix="/financeiro", tags=["financeiro"])


@router.get("/categorias")
def categorias(_: UsuarioAtual) -> Categorias:
    return Categorias(
        **{tipo: [Categoria(id=c, nome=n) for c, n in itens.items()] for tipo, itens in CATEGORIAS.items()}
    )


@router.get("/contas")
def listar(
    db: DB,
    _: Gerente,
    tipo: Tipo,
    situacao: Situacao = "abertas",
    inicio: date | None = None,
    fim: date | None = None,
    busca: str | None = None,
    loja_id: UUID | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 100,
) -> PaginaContas:
    return service.listar(db, tipo, situacao, inicio, fim, busca, loja_id, pagina, por_pagina)


@router.post("/contas", status_code=status.HTTP_201_CREATED)
def criar(db: DB, usuario: Gerente, dados: ContaCriar) -> list[ContaSaida]:
    """Lança uma conta. Com várias parcelas, devolve uma conta por parcela."""
    return service.saidas(db, service.criar(db, usuario, dados))


@router.get("/contas/{conta_id}")
def obter(db: DB, _: Gerente, conta_id: UUID) -> ContaSaida:
    return service.saida(db, service.obter(db, conta_id))


@router.patch("/contas/{conta_id}")
def atualizar(db: DB, _: Gerente, conta_id: UUID, dados: ContaAtualizar) -> ContaSaida:
    return service.saida(db, service.atualizar(db, conta_id, dados))


@router.post("/contas/{conta_id}/baixar")
def baixar(db: DB, usuario: Operador, terminal: TerminalAtual, conta_id: UUID, dados: ContaBaixar) -> ContaSaida:
    """Paga ou recebe. O caixa pode receber fiado; pagar contas é só para gerentes."""
    conta = service.obter(db, conta_id)
    if conta.tipo == "pagar" and usuario.papel not in ("admin", "gerente"):
        raise SemPermissao("Só gerentes podem pagar contas")
    caixa = caixa_do_terminal(db, terminal) if terminal else None
    return service.saida(db, service.baixar(db, usuario, conta_id, dados, caixa))


@router.post("/contas/{conta_id}/estornar")
def estornar(db: DB, _: Gerente, conta_id: UUID) -> ContaSaida:
    return service.saida(db, service.estornar(db, conta_id))


@router.post("/contas/{conta_id}/cancelar")
def cancelar(db: DB, _: Gerente, conta_id: UUID) -> ContaSaida:
    return service.saida(db, service.cancelar(db, conta_id))


@router.get("/clientes/{cliente_id}/credito")
def credito(db: DB, _: Operador, cliente_id: UUID) -> CreditoCliente:
    """Limite, quanto o cliente deve e quanto ainda pode comprar a prazo."""
    return service.credito_do_cliente(db, cliente_id)


@router.get("/fluxo")
def fluxo(
    db: DB, _: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> FluxoCaixa:
    """Entradas e saídas por dia: o que já aconteceu e o que está para vencer. Padrão: 30 dias a partir de hoje."""
    inicio = inicio or hoje()
    return service.fluxo(db, inicio, fim or inicio + timedelta(days=29), loja_id)
